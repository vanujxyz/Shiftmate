"""Edge Gateway FastAPI app (TRD §9.1): the machine-side server the cab talks to.

One process hosts the live simulated site and the focus machine's runtime. A clock task advances
the world `speed` seconds per real second while the scenario plays, then pumps what happened to
the WebSocket channels (`edge/channels.py`). A second task syncs the outbox and fetches newer
estimation models from the fleet (`edge/sync.py`). Endpoints and sockets are `async`, so
everything runs on one event loop and never sees the world half-updated.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time as _time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect

from shiftmate import __version__
from shiftmate.assistant.provider import AssistantProvider, llm_from_settings
from shiftmate.assistant.service import Assistant
from shiftmate.config_loader import ShiftMateConfig, load_config
from shiftmate.edge.channels import Feeds, Subscriber, cab_channel, site_channel
from shiftmate.edge.live import SCENARIO_DIR, Scenario, ScenarioPlayer
from shiftmate.edge.resources import EdgeResources
from shiftmate.edge.services import (
    build_insights,
    build_profile,
    build_progress,
    build_shift,
    training_slots,
)
from shiftmate.edge.store import EdgeStore
from shiftmate.edge.sync import SyncWorker
from shiftmate.engines.reports import auto_fill
from shiftmate.engines.safety import SafetyEngine
from shiftmate.schema import HealthResponse
from shiftmate.schema.api import (
    AckRequest,
    AlertTimings,
    AskRequest,
    AskResponse,
    BeatView,
    BookingRequest,
    CabConfig,
    CameraProtocolRun,
    CameraReading,
    CameraSettings,
    Capability,
    CaptionsRequest,
    ChecklistItemView,
    ChecklistResult,
    ChecklistSubmit,
    DemoState,
    DrillResultRequest,
    InsightsResponse,
    IntentRequest,
    IntentResponse,
    LessonCompleteRequest,
    LessonSummary,
    MachineInfo,
    NetworkRequest,
    OperatorProfile,
    Recommendation,
    ReportContextModel,
    ReportParseRequest,
    ReportParseResponse,
    ReportSaveRequest,
    SavedReport,
    ScenarioInfo,
    ScenarioLoadRequest,
    SeekRequest,
    SessionResponse,
    ShiftResponse,
    SignInRequest,
    SiteLayout,
    SpeedRequest,
    SyncStatus,
    TaskEstimate,
    TrainingProgress,
)
from shiftmate.schema.config import Lesson
from shiftmate.schema.enums import EventType, Language, ReportType, SensorTier
from shiftmate.schema.events import ReportDraft
from shiftmate.schema.reference import Machine
from shiftmate.schema.training import TrainingSlot
from shiftmate.settings import Settings, get_settings
from shiftmate.util.api import install_common
from shiftmate.util.ids import uuid7_from

log = logging.getLogger(__name__)
CLOCK_PERIOD_S = 0.1


@dataclass
class EdgeContext:
    cfg: ShiftMateConfig
    resources: EdgeResources
    store: EdgeStore
    player: ScenarioPlayer
    feeds: Feeds | None = None
    sync: SyncWorker | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def site(self):
        if self.player.site is None:
            raise HTTPException(409, "No scenario is loaded.")
        return self.player.site

    def wall(self) -> float:
        return _time.monotonic()


def camera_protocol_path(settings: Settings) -> Path:
    """Where camera protocol sessions are kept (read by `shiftmate eval camera`)."""
    return settings.resolve(settings.data_dir) / "eval" / "camera_protocol.jsonl"


def pin_for(operator_id: str) -> str:
    """Demo PINs: the operator number (OP1001 → 1001). Not a security measure (PRD §3 non-goals)."""
    return operator_id.removeprefix("OP")


def create_app(
    cfg: ShiftMateConfig | None = None,
    history_dir: Path | None = None,
    models_dir: Path | None = None,
    db_path: Path | None = None,
    scenario: str | None = "ravi_shift",
    autorun: bool = True,
    cache_dir: Path | None = None,
    fleet_url: str | None = None,
    fleet_transport: httpx.AsyncBaseTransport | None = None,
    assistant: Assistant | None = None,
) -> FastAPI:
    """Build the app. `autorun=False` (tests) leaves the clock and sync loops off."""
    settings = get_settings()
    cfg = cfg or load_config()
    data_dir = settings.resolve(settings.data_dir)
    history_dir = history_dir or data_dir / "history"
    models_dir = models_dir or settings.resolve(settings.models_dir)
    cache_dir = cache_dir or data_dir / "edge" / "models"
    resources = EdgeResources.load(cfg, history_dir, models_dir, cache_dir)
    store = EdgeStore(db_path if db_path is not None else data_dir / "edge" / "edge.db")
    player = ScenarioPlayer(cfg, resources, store)
    ctx = EdgeContext(cfg, resources, store, player)
    provider = AssistantProvider(cfg, models_dir, llm_from_settings(cfg, settings))
    ctx.extra["get_assistant"] = (lambda: assistant) if assistant is not None else provider.get
    # beside the edge database, so a test's temporary gateway keeps its own sessions
    ctx.extra["camera_protocol_path"] = (
        camera_protocol_path(settings)
        if db_path is None
        else db_path.parent / "eval" / "camera_protocol.jsonl"
    )
    ctx.feeds = Feeds(ctx)
    ctx.sync = SyncWorker(ctx, fleet_url or settings.fleet_url, cache_dir, fleet_transport)
    if scenario:
        player.load(scenario)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        tasks = []
        if autorun:
            tasks = [asyncio.create_task(_clock(ctx)), asyncio.create_task(ctx.sync.run())]
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(title="ShiftMate Edge Gateway", version=__version__, lifespan=lifespan)
    app.state.ctx = ctx
    install_common(app)
    _routes(app, ctx)
    return app


async def _clock(ctx: EdgeContext) -> None:
    """Advance the world while the scenario plays (speed × real time)."""
    last = _time.monotonic()
    while True:
        await asyncio.sleep(CLOCK_PERIOD_S)
        now = _time.monotonic()
        try:
            ctx.player.tick_wall(now - last, now)
            ctx.feeds.pump(now)
        except Exception:  # keep the clock alive; the error is logged for the demo operator
            log.exception("clock step failed")
        last = now


async def _serve_socket(ctx: EdgeContext, ws: WebSocket, channel: str, first: dict) -> None:
    """Send a channel to one socket: a snapshot first, then every message in order."""
    await ws.accept()
    hub = ctx.feeds.hub
    sub: Subscriber = hub.subscribe(channel)
    site = ctx.player.site
    hub.publish(
        channel,
        "snapshot",
        first,
        site.now if site else None,
        machine_id=channel.removeprefix("cab:") if channel.startswith("cab:") else None,
        site_id=site.site.site_id if site else None,
        only=sub,
    )

    async def reader() -> None:  # clients only send pings; reading also notices a disconnect
        while True:
            await ws.receive_text()

    read_task = asyncio.create_task(reader())
    try:
        while True:
            get = asyncio.create_task(sub.queue.get())
            done, _ = await asyncio.wait({get, read_task}, return_when=asyncio.FIRST_COMPLETED)
            if read_task in done:
                get.cancel()
                break
            await ws.send_json(get.result())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        read_task.cancel()
        hub.unsubscribe(channel, sub)


# --- helpers ------------------------------------------------------------------------------------


def machine_info(ctx: EdgeContext, machine: Machine, focus: bool) -> MachineInfo:
    signals = ctx.cfg.sensor_tiers.signals_for(machine.sensor_tier)
    engine = SafetyEngine(ctx.cfg.safety_rules, signals, ctx.cfg.alert_policy.default_cooldown_s)
    extra = set()
    if focus and ctx.player.site and ctx.player.site.runtime.camera_active(ctx.wall()):
        extra.add("proximity_m")
    caps = []
    for rule in ctx.cfg.safety_rules.rules:
        enabled = engine.enabled(rule, extra)
        missing = [s for s in rule.requires_signals if s not in signals | extra]
        caps.append(
            Capability(
                id=rule.id,
                enabled=enabled,
                reason=f"needs {', '.join(missing)}" if missing else None,
            )
        )
    features = {
        name: ctx.cfg.sensor_tiers.feature_enabled(name, machine.sensor_tier)
        for name in ctx.cfg.sensor_tiers.feature_availability
    }
    return MachineInfo(
        machine=machine,
        focus=focus,
        capabilities=caps,
        features=features,
        low_confidence=machine.sensor_tier == SensorTier.BASIC,
    )


def lesson_summary(
    ctx: EdgeContext, lesson: Lesson, operator_id: str | None = None
) -> LessonSummary:
    done = False
    if operator_id:
        done = any(c["lesson_id"] == lesson.id for c in ctx.store.list_completions(operator_id))
    return LessonSummary(
        id=lesson.id,
        title=lesson.title.model_dump(),
        format=lesson.format.value,
        duration_s=lesson.duration_s,
        triggers=lesson.triggers,
        completed=done,
        art=lesson.art or (lesson.cards[0].illustration if lesson.cards else None),
    )


def require_operator(ctx: EdgeContext, operator_id: str) -> None:
    if ctx.resources.operator_row(operator_id) is None:
        raise HTTPException(404, f"Unknown operator {operator_id}.")


def _routes(app: FastAPI, ctx: EdgeContext) -> None:
    cfg = ctx.cfg

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        site = ctx.player.site
        return HealthResponse(
            service="edge",
            status="ok",
            version=__version__,
            sim_clock=site.now.isoformat() if site else None,
            network_online=ctx.player.online,
        )

    # --- machines and session ---------------------------------------------------------------
    @app.get("/machines", response_model=list[MachineInfo])
    async def machines() -> list[MachineInfo]:
        site = ctx.site
        return [
            machine_info(ctx, a.machine, a.machine.machine_id == site.focus_id)
            for a in site.world.agents.values()
        ]

    @app.get("/machines/{machine_id}", response_model=MachineInfo)
    async def machine(machine_id: str) -> MachineInfo:
        agent = ctx.site.world.agents.get(machine_id)
        if agent is None:
            raise HTTPException(404, f"Unknown machine {machine_id}.")
        return machine_info(ctx, agent.machine, machine_id == ctx.site.focus_id)

    @app.post("/session/sign-in", response_model=SessionResponse)
    async def sign_in(body: SignInRequest) -> SessionResponse:
        site = ctx.site
        require_operator(ctx, body.operator_id)
        if body.machine_id != site.focus_id:
            raise HTTPException(409, f"This tablet is on {site.focus_id}.")
        badge_ok = body.badge == f"SHIFTMATE:{body.operator_id}"
        if not badge_ok and body.pin != pin_for(body.operator_id):
            raise HTTPException(401, "That PIN didn't match.")
        site.runtime.sign_in(body.operator_id, body.language, site.now)
        site.runtime.note_shift_conditions(site.world.conditions(site.now))
        profile = build_profile(cfg, ctx.resources, ctx.store, body.operator_id, body.language)
        assert profile is not None
        return SessionResponse(
            profile=profile,
            machine=machine_info(ctx, site.world.agents[site.focus_id].machine, True),
            shift=build_shift(cfg, ctx.resources, site),
        )

    @app.post("/session/sign-out")
    async def sign_out() -> dict[str, bool]:
        ctx.site.runtime.sign_out()
        return {"ok": True}

    @app.get("/operators/{operator_id}/profile", response_model=OperatorProfile)
    async def profile(operator_id: str) -> OperatorProfile:
        p = build_profile(cfg, ctx.resources, ctx.store, operator_id)
        if p is None:
            raise HTTPException(404, f"Unknown operator {operator_id}.")
        return p

    @app.get("/operators/{operator_id}/shift", response_model=ShiftResponse)
    async def shift(operator_id: str, date: str | None = None) -> ShiftResponse:
        site = ctx.site
        require_operator(ctx, operator_id)
        plan = site.world.agents[site.focus_id].plan
        on_machine = {
            site.runtime.operator_id,
            plan.operator_id if plan else None,
            site.scenario.operator,
        }
        if operator_id not in on_machine:
            raise HTTPException(404, f"{operator_id} has no shift on {site.focus_id} today.")
        if date and date != site.scenario.date.isoformat():
            raise HTTPException(404, "Only today's shift is planned on this machine.")
        return build_shift(cfg, ctx.resources, site)

    @app.get("/tasks/{task_id}/estimate", response_model=TaskEstimate)
    async def task_estimate(task_id: str) -> TaskEstimate:
        for t in build_shift(cfg, ctx.resources, ctx.site).tasks:
            if t.task.task_id == task_id:
                if t.estimate is None:
                    raise HTTPException(404, "This task has no estimate (done, or no model yet).")
                return t.estimate
        raise HTTPException(404, f"Unknown task {task_id}.")

    @app.get("/cab/config", response_model=CabConfig)
    async def cab_config() -> CabConfig:
        """What the cab needs from config: alert sound/speech timing and the checklist."""
        ap = cfg.alert_policy
        return CabConfig(
            alerts=AlertTimings(
                p1_speech_repeat_s=ap.p1_speech_repeat_s,
                p2_tone_repeat_s=ap.p2_tone_repeat_s,
                reduced_p1_repeat_s=ap.reduced_p1_repeat_s,
                p3_snooze_min=ap.p3_snooze_min,
                paused_idle_seconds=ap.paused_definition.idle_seconds,
            ),
            checklist=[
                ChecklistItemView(id=i.id, text=i.text.model_dump(), illustration=i.illustration)
                for i in cfg.checklist.items
            ],
            checklist_voice={
                k: {lang.value: words for lang, words in getattr(cfg.checklist.voice, k).items()}
                for k in ("ok", "problem", "all_ok")
            },
            camera=CameraSettings(
                **cfg.edge.camera.detect.model_dump(),
                protocol_distances_m=cfg.edge.camera.protocol_distances_m,
                protocol_readings=cfg.edge.camera.protocol_readings,
            ),
            languages=list(Language),
        )

    @app.post("/checklist", response_model=ChecklistResult)
    async def checklist(body: ChecklistSubmit) -> ChecklistResult:
        site = ctx.site
        items = {i.id: i for i in cfg.checklist.items}
        unknown = [a.item_id for a in body.answers if a.item_id not in items]
        if unknown:
            raise HTTPException(422, f"Unknown checklist items: {unknown}")
        rt = site.runtime
        rt.record(
            EventType.CHECKLIST,
            site.now,
            "walkaround",
            {"answers": [a.model_dump() for a in body.answers]},
        )
        report_ids = []
        for a in body.answers:
            if a.ok:
                continue
            text = items[a.item_id].text.get(rt.language)
            draft = ReportDraft(
                type=ReportType.EQUIPMENT_PROBLEM,
                severity="medium",
                summary_en=items[a.item_id].text.en,
                summary_local=a.note or text,
                people_involved=False,
                injury=False,
                parser="checklist",
            )
            report_ids.append(_save_report(ctx, draft, None, transcript=a.note))
        return ChecklistResult(saved=True, problems=len(report_ids), report_ids=report_ids)

    @app.post("/alerts/{alert_id}/ack")
    async def ack(alert_id: str, body: AckRequest | None = None) -> dict[str, Any]:
        rt = ctx.site.runtime
        if rt.pipeline.alerts is None:
            raise HTTPException(409, "No alert policy on this machine.")
        out = rt.pipeline.alerts.acknowledge(alert_id, ctx.site.now, (body or AckRequest()).action)
        if not out.messages and not out.events:
            raise HTTPException(404, f"No active alert {alert_id}.")
        for ev in out.events:
            rt._record_event(ev, rt.last_tick or {})
        rt.messages.extend(out.messages)
        return {"ok": True, "messages": out.messages}

    # --- reports ------------------------------------------------------------------------------
    def report_context(language: Language) -> ReportContextModel:
        site = ctx.site
        rt = site.runtime
        tick = rt.last_tick or {}
        c = auto_fill(
            ts=site.now,
            machine_id=site.focus_id,
            operator_id=rt.operator_id,
            site_id=site.site.site_id,
            layout=site.site.layout,
            x_m=float(tick.get("x_m", 0.0)),
            y_m=float(tick.get("y_m", 0.0)),
            task_id=tick.get("task_id"),
            weather={
                k: tick.get(k)
                for k in (
                    "heat_index_c",
                    "ambient_temp_c",
                    "precipitation_mm_h",
                    "ground_condition",
                    "is_night",
                )
            },
            risk_score=rt.last_step.risk.score if rt.last_step else None,
            language=language,
        )
        return ReportContextModel(**c.model_dump())

    @app.post("/reports/parse", response_model=ReportParseResponse)
    async def reports_parse(body: ReportParseRequest) -> ReportParseResponse:
        helper = await asyncio.to_thread(ctx.extra["get_assistant"])
        draft, mode = await asyncio.to_thread(helper.parse_report, body.transcript, body.language)
        return ReportParseResponse(draft=draft, context=report_context(body.language), mode=mode)

    @app.post("/reports", response_model=SavedReport)
    async def reports_save(body: ReportSaveRequest) -> SavedReport:
        context = body.context or report_context(ctx.site.runtime.language)
        report_id = _save_report(ctx, body.draft, context, body.transcript)
        saved = ctx.store.list_reports(limit=50)
        row = next(r for r in saved if r["report_id"] == report_id)
        return SavedReport(
            report_id=report_id,
            ts=row["ts"],
            draft=body.draft,
            context=ReportContextModel(**row["context"]),
            synced=row["synced"],
        )

    @app.get("/reports", response_model=list[SavedReport])
    async def reports_list(operator_id: str | None = None) -> list[SavedReport]:
        return [
            SavedReport(
                report_id=r["report_id"],
                ts=r["ts"],
                draft=ReportDraft(**r["draft"]),
                context=ReportContextModel(**r["context"]),
                synced=r["synced"],
            )
            for r in ctx.store.list_reports(operator_id)
        ]

    # --- insights -----------------------------------------------------------------------------
    @app.get("/insights/{operator_id}", response_model=InsightsResponse)
    async def insights(
        operator_id: str, range: str = Query("shift", pattern="^(shift|week)$")
    ) -> InsightsResponse:  # noqa: A002
        site = ctx.site
        if operator_id != site.runtime.operator_id:
            raise HTTPException(403, "My Day is private to the signed-in operator (P-01).")
        return build_insights(cfg, ctx.resources, site, ctx.store, operator_id, range)

    # --- learning ------------------------------------------------------------------------------
    @app.get("/lessons", response_model=list[LessonSummary])
    async def lessons(operator_id: str | None = None) -> list[LessonSummary]:
        return [lesson_summary(ctx, lesson, operator_id) for lesson in cfg.lessons.lessons]

    @app.get("/lessons/recommended", response_model=list[Recommendation])
    async def lessons_recommended(operator_id: str) -> list[Recommendation]:
        site = ctx.site
        rt = site.runtime
        if operator_id != rt.operator_id:
            raise HTTPException(403, "Recommendations are private to the signed-in operator.")
        recs = rt.recommendations(site.now)
        return [
            Recommendation(
                lesson=lesson_summary(ctx, cfg.lessons.lesson(r.lesson_id), operator_id),
                score=r.score,
                because=r.triggers,
            )
            for r in recs
        ]

    @app.get("/lessons/{lesson_id}", response_model=Lesson)
    async def lesson(lesson_id: str, lang: Language | None = None) -> Lesson:
        try:
            return cfg.lessons.lesson(lesson_id)
        except KeyError as exc:
            raise HTTPException(404, f"Unknown lesson {lesson_id}.") from exc

    @app.post("/lessons/{lesson_id}/complete")
    async def lesson_complete(lesson_id: str, body: LessonCompleteRequest) -> dict[str, Any]:
        try:
            cfg.lessons.lesson(lesson_id)
        except KeyError as exc:
            raise HTTPException(404, f"Unknown lesson {lesson_id}.") from exc
        site = ctx.site
        ctx.store.add_completion(
            body.operator_id, lesson_id, site.now, body.score, body.duration_s, body.language.value
        )
        site.runtime.record(
            EventType.LESSON_COMPLETED,
            site.now,
            lesson_id,
            {"score": body.score, "duration_s": body.duration_s, "language": body.language.value},
        )
        return {"ok": True}

    @app.post("/drills/results")
    async def drill_results(body: DrillResultRequest) -> dict[str, Any]:
        site = ctx.site
        lesson = next(
            (x for x in cfg.lessons.lessons if x.id == body.drill_id and x.format.value == "drill"),
            None,
        )
        if lesson is None:
            raise HTTPException(404, f"Unknown drill {body.drill_id}.")
        correct = sum(1 for h in body.hazards if h.correct)
        score = correct / len(body.hazards) if body.hazards else 0.0
        reactions = [h.reaction_ms for h in body.hazards if h.reaction_ms is not None and h.correct]
        data = {
            "hazards": [h.model_dump() for h in body.hazards],
            "correct": correct,
            "total": len(body.hazards),
            "mean_reaction_ms": round(sum(reactions) / len(reactions)) if reactions else None,
        }
        ctx.store.add_drill(body.operator_id, body.drill_id, site.now, score, data)
        site.runtime.record(
            EventType.DRILL_RESULT, site.now, body.drill_id, {**data, "score": score}
        )
        return {"ok": True, "score": score, **data}

    @app.get("/training/slots", response_model=list[TrainingSlot])
    async def slots(site_id: str | None = None) -> list[TrainingSlot]:
        site = ctx.site
        sid = site_id or site.site.site_id
        if sid not in cfg.sites:
            raise HTTPException(404, f"Unknown site {sid}.")
        start = site.local(cfg.sites[sid].shift.start)
        ctx.store.upsert_slots(sid, training_slots(cfg, sid, start))
        return [
            TrainingSlot(
                slot_id=s["slot_id"],
                dealer_centre=s["dealer_centre"],
                site_id=s["site_id"],
                start=s["start"],
                topic=s["topic"],
                seats_left=s["seats_left"],
            )
            for s in ctx.store.list_slots(sid)
        ]

    @app.get("/training/progress", response_model=TrainingProgress)
    async def progress(operator_id: str) -> TrainingProgress:
        site = ctx.site
        if operator_id != site.runtime.operator_id:
            raise HTTPException(403, "Training progress is private to the signed-in operator.")
        return build_progress(cfg, ctx.resources, ctx.store, site, operator_id)

    @app.post("/training/bookings")
    async def bookings(body: BookingRequest) -> dict[str, Any]:
        site = ctx.site
        booking_id = uuid7_from(site.now, site.runtime.rng)
        if not ctx.store.book(booking_id, body.operator_id, body.slot_id, site.now):
            raise HTTPException(409, "That session is full or does not exist.")
        site.runtime.record(EventType.BOOKING, site.now, body.slot_id, {"booking_id": booking_id})
        return {"ok": True, "booking_id": booking_id}

    # --- assistant (the full assistant arrives in milestone 14) --------------------------------
    @app.post("/assistant/ask", response_model=AskResponse)
    async def ask(body: AskRequest) -> AskResponse:
        helper = await asyncio.to_thread(ctx.extra["get_assistant"])
        machine_type = None
        site = ctx.player.site
        if site is not None:
            machine_type = site.world.agents[site.focus_id].machine.machine_type.value
        return await asyncio.to_thread(helper.ask, body.question, body.language, machine_type)

    @app.post("/assistant/intent", response_model=IntentResponse)
    async def intent(body: IntentRequest) -> IntentResponse:
        helper = await asyncio.to_thread(ctx.extra["get_assistant"])
        return await asyncio.to_thread(helper.classify, body.utterance, body.language)

    # --- camera and sync ------------------------------------------------------------------------
    @app.post("/proximity/camera")
    async def camera(body: CameraReading) -> dict[str, Any]:
        site = ctx.site
        if body.machine_id != site.focus_id:
            raise HTTPException(404, f"No camera runtime for {body.machine_id}.")
        site.runtime.camera_reading(body.distance_m, body.confidence, body.bearing_deg, ctx.wall())
        return {"ok": True}

    @app.post("/eval/camera-protocol")
    async def camera_protocol(body: CameraProtocolRun) -> dict[str, int]:
        """Store a camera protocol session (TRD §12) for `shiftmate eval camera`."""
        path: Path = ctx.extra["camera_protocol_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {"saved_at": datetime.now(UTC).isoformat(timespec="seconds"), **body.model_dump()}
        with path.open("a", encoding="utf-8") as f:
            print(json.dumps(row), file=f)
        return {"saved": len(body.readings)}

    @app.get("/sync/status", response_model=SyncStatus)
    async def sync_status() -> SyncStatus:
        st = ctx.sync.status_payload()
        res = ctx.resources
        return SyncStatus(
            online=st["online"],
            outbox_size=st["outbox_size"],
            last_sync=st["last_sync"],
            last_error=st["last_error"],
            estimation_model=res.estimation.version if res.estimation else None,
            estimation_source=res.estimation_source,
        )

    # --- live channels (TRD §9.1) -------------------------------------------------------------
    @app.websocket("/ws/cab/{machine_id}")
    async def ws_cab(ws: WebSocket, machine_id: str) -> None:
        site = ctx.player.site
        if site is None or machine_id != site.focus_id:
            await ws.close(code=4404, reason=f"No live runtime for {machine_id}.")
            return
        await _serve_socket(ctx, ws, cab_channel(machine_id), ctx.feeds.cab_snapshot())

    @app.websocket("/ws/site/{site_id}")
    async def ws_site(ws: WebSocket, site_id: str) -> None:
        site = ctx.player.site
        if site is None or site_id != site.site.site_id:
            await ws.close(code=4404, reason=f"Site {site_id} is not running here.")
            return
        await _serve_socket(ctx, ws, site_channel(site_id), ctx.feeds.site_snapshot())

    # --- demo control ---------------------------------------------------------------------------
    def demo_state() -> DemoState:
        p = ctx.player
        s = p.scenario
        return DemoState(
            scenario=s.name if s else None,
            site_id=s.site_id if s else None,
            focus_machine=s.focus_machine if s else None,
            sim_time=p.site.now if p.site else None,
            playing=p.playing,
            speed=p.speed,
            waiting_for=p.waiting_for,
            online=p.online,
            captions=p.captions,
            beats=[
                BeatView(
                    id=b.id,
                    at=b.at.strftime("%H:%M"),
                    action=b.action,
                    caption=b.caption,
                    done=b.id in p.fired,
                )
                for b in (s.beats if s else [])
            ],
            signed_in=p.site.runtime.operator_id if p.site else None,
        )

    @app.get("/site/layout", response_model=SiteLayout)
    async def site_layout() -> SiteLayout:
        site = ctx.site
        return SiteLayout(
            site_id=site.site.site_id,
            name=site.site.name,
            timezone=site.site.timezone,
            focus_machine=site.focus_id,
            layout=site.site.layout,
        )

    @app.get("/demo/scenarios", response_model=list[ScenarioInfo])
    async def demo_scenarios() -> list[ScenarioInfo]:
        return [
            ScenarioInfo(
                name=sc.name, title=sc.title, site_id=sc.site_id, focus_machine=sc.focus_machine
            )
            for sc in (Scenario.load(p.stem) for p in sorted(SCENARIO_DIR.glob("*.yaml")))
        ]

    @app.get("/demo/state", response_model=DemoState)
    async def demo_get() -> DemoState:
        return demo_state()

    @app.post("/demo/scenario/load", response_model=DemoState)
    async def demo_load(body: ScenarioLoadRequest) -> DemoState:
        try:
            ctx.player.load(body.name)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        ctx.feeds.pump(ctx.wall())
        return demo_state()

    @app.post("/demo/play", response_model=DemoState)
    async def demo_play() -> DemoState:
        ctx.site  # noqa: B018 (raises 409 when nothing is loaded)
        ctx.player.continue_()
        ctx.player.playing = True
        return demo_state()

    @app.post("/demo/pause", response_model=DemoState)
    async def demo_pause() -> DemoState:
        ctx.player.playing = False
        return demo_state()

    @app.post("/demo/speed", response_model=DemoState)
    async def demo_speed(body: SpeedRequest) -> DemoState:
        ctx.player.speed = body.x
        return demo_state()

    @app.post("/demo/seek", response_model=DemoState)
    async def demo_seek(body: SeekRequest) -> DemoState:
        ctx.site  # noqa: B018
        try:
            ctx.player.seek(body.beat_id)
        except KeyError as exc:
            raise HTTPException(404, f"Unknown beat {body.beat_id}.") from exc
        ctx.feeds.pump(ctx.wall())
        return demo_state()

    @app.post("/demo/network", response_model=DemoState)
    async def demo_network(body: NetworkRequest) -> DemoState:
        ctx.site  # noqa: B018
        ctx.player.set_network(body.online)
        ctx.sync.publish_status(force=True)
        ctx.feeds.pump(ctx.wall())
        return demo_state()

    @app.post("/demo/captions", response_model=DemoState)
    async def demo_captions(body: CaptionsRequest) -> DemoState:
        ctx.player.captions = body.on
        return demo_state()


def _save_report(
    ctx: EdgeContext, draft: ReportDraft, context: ReportContextModel | None, transcript: str | None
) -> str:
    site = ctx.site
    rt = site.runtime
    if context is None:
        tick = rt.last_tick or {}
        c = auto_fill(
            ts=site.now,
            machine_id=site.focus_id,
            operator_id=rt.operator_id,
            site_id=site.site.site_id,
            layout=site.site.layout,
            x_m=float(tick.get("x_m", 0.0)),
            y_m=float(tick.get("y_m", 0.0)),
            task_id=tick.get("task_id"),
            weather={},
            risk_score=None,
            language=rt.language,
        )
        context = ReportContextModel(**c.model_dump())
    report_id = uuid7_from(site.now, rt.rng)
    data = {
        "draft": draft.model_dump(mode="json"),
        "context": context.model_dump(mode="json"),
        "transcript": transcript,
        "ts": site.now.isoformat(),
    }
    ctx.store.add_report(report_id, site.now, rt.operator_id, site.focus_id, data)
    kind = EventType(draft.type.value)  # incident | near_miss | equipment_problem
    rt.record(
        kind,
        site.now,
        draft.type.value,
        {"report_id": report_id, "severity": draft.severity.value},
        shared=draft.type in (ReportType.INCIDENT, ReportType.NEAR_MISS),
    )
    if draft.type == ReportType.NEAR_MISS:
        rt.pipeline.near_misses_24h += 1
    rt.pipeline.intervals.record_report(draft.type.value)
    rt.reports_saved += 1
    return report_id
