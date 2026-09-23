/**
 * /_kitchen-sink (CLAUDE.md Phase 7): every @shiftmate/ui component in the chosen theme (Day,
 * Sunlight, Night) and language (en, hi, ta). Cab components sit in a 1280-wide cab frame, the
 * reference width they are designed for, so overflow shows up here first. All words come from
 * the i18n files; sample values are the demo's own (Ravi's shift).
 */
import { LANGUAGES, type Language } from "@shiftmate/i18n";
import {
  AlertBannerP2,
  AlertFeedP4,
  AlertStripP3,
  AlertTakeoverP1,
  AssistantAnswer,
  BadgeTarget,
  BeltGlyph,
  BookingSlot,
  BottomNav,
  Button,
  ChecklistItem,
  CoachingNote,
  ConditionGlyph,
  ConditionsSummary,
  DemoBar,
  DrillFrame,
  FleetTile,
  IdleGlyph,
  type IdleReason,
  IdleSegmentRow,
  LargeToggle,
  LessonCard,
  LoadBlocks,
  MachineGlyph,
  type MachineState,
  MapLegend,
  MapSymbol,
  NarratedCardPlayer,
  NetGlyph,
  type NetState,
  PinPad,
  PriorityGlyph,
  ProximityGlyph,
  type ProximityTier,
  PushToTalk,
  QueuePip,
  QuizOption,
  RangeBar,
  Reach,
  ReasonChip,
  ReportDraftCard,
  RiskContributions,
  SegmentedControl,
  SensorGlyph,
  SkillLadder,
  SourceChip,
  Sparkline,
  StaleMark,
  StatusRail,
  SyncState,
  SystemState,
  TaskRow,
  type Theme,
  THEMES,
  TimeSplit,
  TranscriptSheet,
} from "@shiftmate/ui";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

const noop = () => {};
const MACHINE_STATES: MachineState[] = ["working", "idle", "travel", "off"];
const IDLE: IdleReason[] = [
  "WAITING_FOR_TRUCK",
  "WARM_UP",
  "SCHEDULED_BREAK",
  "UNATTENDED_RUNNING",
  "HABIT",
  "UNKNOWN",
];
const TIERS: ProximityTier[] = ["clear", "caution", "danger", "critical"];
const NETS: NetState[] = ["online", "offline", "waiting", "syncing", "synced"];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="flex flex-col gap-6 border-t-4 border-line pt-6">
      <h2 id={`${id}-h`} className="text-con-title">{title}</h2>
      {children}
    </section>
  );
}

/** The cab's reference canvas: 1280 px wide (DESIGN §4), on the cab ground. */
function CabFrame({ children, gap = true }: { children: ReactNode; gap?: boolean }) {
  return (
    <div data-frame="cab" className={`relative flex w-320 flex-col bg-ground ${gap ? "gap-6 p-6" : ""}`}>
      {children}
    </div>
  );
}

export function KitchenSink() {
  const { t, i18n } = useTranslation();
  const [theme, setTheme] = useState<Theme>("day");
  const lang = (i18n.language as Language) ?? "en";
  const [toggle, setToggle] = useState(true);
  const [pin, setPin] = useState(2);
  const [check, setCheck] = useState<"ok" | "problem" | null>("ok");
  const [narration, setNarration] = useState<Language>("ta");

  const names = {
    WORKING: t("ui.machine.working"),
    OFF: t("ui.machine.off"),
    ...Object.fromEntries(IDLE.map((r) => [r, t(`idle.${r}`)])),
  } as Record<"WORKING" | "OFF" | IdleReason, string>;
  const langOptions = LANGUAGES.map((l) => ({ value: l, label: t(`ui.lang.${l}`), lang: l }));
  const tabs = [
    { id: "shift", label: t("ui.nav.shift"), glyph: <ConditionGlyph condition="clock" size={44} /> },
    { id: "safety", label: t("ui.nav.safety"), glyph: <ProximityGlyph tier="clear" size={44} /> },
    { id: "report", label: t("ui.nav.report"), glyph: <PriorityGlyph priority="P4" size={44} /> },
    { id: "day", label: t("ui.nav.day"), glyph: <IdleGlyph reason="SCHEDULED_BREAK" size={44} /> },
    { id: "learn", label: t("ui.nav.learn"), glyph: <SensorGlyph tier="advanced" size={44} /> },
  ];
  const range = (likely: number, low: number, high: number, confidence?: "low") => (
    <RangeBar likely={likely} low={low} high={high} confidence={confidence}
      label={t("ui.task.estimate_sr")} lowNote={t("ui.task.low_confidence")} />
  );

  return (
    <div data-theme={theme} lang={lang} className="sm-root min-h-screen p-8">
      <header className="sticky top-0 z-(--sm-layer-p1) flex flex-wrap items-center gap-6 border-b-4 border-line bg-ground pb-4">
        <h1 className="text-con-display">{t("ui.ks.title")}</h1>
        <SegmentedControl dense label={t("ui.theme.label")} value={theme} onChange={setTheme}
          options={THEMES.map((th) => ({ value: th, label: t(`ui.theme.${th}`) }))} />
        <SegmentedControl dense label={t("ui.lang.label")} value={lang}
          onChange={(l) => void i18n.changeLanguage(l)} options={langOptions} />
        <p className="text-con-body text-ink-2">{t("ui.ks.intro")}</p>
      </header>

      <main className="flex flex-col gap-12 pt-8">
        <Section id="glyphs" title={t("ui.ks.glyphs")}>
          <div className="flex flex-wrap gap-6">
            {MACHINE_STATES.map((s) => (
              <figure key={s} className="flex flex-col items-center gap-2 text-con-meta">
                <MachineGlyph state={s} size={48} label={t(`ui.machine.${s}`)} />
                <figcaption>{t(`ui.machine.${s}`)}</figcaption>
              </figure>
            ))}
            {IDLE.map((r) => (
              <figure key={r} className="flex flex-col items-center gap-2 text-con-meta">
                <IdleGlyph reason={r} size={48} label={t(`idle.${r}`)} />
                <figcaption>{t(`idle.${r}`)}</figcaption>
              </figure>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-6">
            {TIERS.map((tier) => <ProximityGlyph key={tier} tier={tier} size={48} />)}
            <BeltGlyph fastened size={48} label={t("ui.rail.belt_on")} />
            <BeltGlyph fastened={false} size={48} label={t("ui.rail.belt_off")} />
            {NETS.map((n) => <NetGlyph key={n} state={n} size={48} />)}
            <SensorGlyph tier="basic" size={48} />
            <SensorGlyph tier="standard" size={48} />
            <SensorGlyph tier="advanced" size={48} />
            {(["P1", "P2", "P3", "P4", "safe"] as const).map((p) => <PriorityGlyph key={p} priority={p} size={48} />)}
            {(["heat", "rain", "wet-ground", "dark", "fatigue", "clock"] as const).map((c) => (
              <ConditionGlyph key={c} condition={c} size={48} />
            ))}
          </div>
          <div className="flex items-end gap-6">
            <MachineGlyph state="working" size={32} />
            <MachineGlyph state="working" size={72} />
            <MachineGlyph state="working" size={160} />
          </div>
        </Section>

        <Section id="reach" title={t("ui.ks.reach")}>
          <div className="flex flex-wrap items-end gap-8">
            <Reach tier="clear" size={84} label={t("ui.rail.prox_clear_label")} />
            <Reach tier="caution" bearing={135} size={148} label={t("ui.rail.prox_caution_label")} />
            <Reach tier="danger" bearing={250} boomAngle={30} size={230} label={t("ui.p2.person")} />
            <Reach tier="critical" bearing={180} boomAngle={160} size={230} label={t("alert.proximity_critical.title")} />
            <Reach tier="clear" noSensing size={148} label={t("ui.rail.no_sensing")} />
          </div>
        </Section>

        <Section id="rail" title={t("ui.ks.rail")}>
          <CabFrame gap={false}>
            <StatusRail
              mode="paused"
              proximity={{ tier: "clear", word: t("ui.rail.clear"), label: t("ui.rail.prox_clear_label") }}
              risk={{ band: "amber", word: t("ui.rail.risk_raised"), reason: t("ui.cond.heat"), label: t("ui.rail.risk_label") }}
              belt={{ fastened: true, word: t("ui.rail.belt_on") }}
              machine={{ id: "EXC001", state: "idle", word: t("ui.machine.idle") }}
              queue={{ priority: "P3", count: 1, label: t("ui.rail.queue_label") }}
              sync={{ state: "waiting", words: t("ui.sync.waiting", { count: 3 }), label: t("ui.sync.waiting", { count: 3 }) }}
              clock="10:42"
            />
          </CabFrame>
          <CabFrame gap={false}>
            <StatusRail
              mode="working"
              proximity={{ tier: "caution", bearing: 135, word: t("ui.rail.one_near"), label: t("ui.rail.prox_caution_label"), stale: t("ui.stale", { seconds: 40 }), staleShort: "40 s" }}
              risk={{ band: "red", word: t("ui.rail.risk_high"), label: t("ui.rail.risk_high") }}
              belt={{ fastened: false, word: t("ui.rail.belt_off") }}
              sync={{ state: "synced", label: t("ui.sync.synced_at", { time: "10:42" }) }}
              clock="10:42"
            />
          </CabFrame>
          <CabFrame gap={false}>
            <StatusRail
              mode="paused"
              proximity={{ tier: "clear", noSensing: true, word: t("ui.rail.no_sensing"), label: t("ui.rail.no_sensing") }}
              risk={{ band: "green", word: t("ui.rail.risk_low"), label: t("ui.rail.risk_low") }}
              belt={null}
              machine={{ id: "WHL014", state: "working", word: t("ui.machine.working") }}
              sync={{ state: "offline", words: t("ui.sync.offline"), label: t("ui.sync.offline") }}
              clock="06:15"
            />
          </CabFrame>
          <CabFrame gap={false}>
            <BottomNav tabs={tabs} current="shift" onSelect={noop} label={t("ui.nav.label")}
              ptt={<PushToTalk state="idle" label={t("ui.ptt.idle")} />} />
          </CabFrame>
        </Section>

        <Section id="alerts" title={t("ui.ks.alerts")}>
          <AlertTakeoverP1
            inline
            command={t("ui.p1.person_command")}
            situation={t("alert.proximity_critical.title")}
            instruction={t("alert.proximity_critical.action")}
            where={t("ui.p1.person_where")}
            cause={<Reach tier="critical" bearing={200} boomAngle={170} size={460} label={t("alert.proximity_critical.title")} />}
            ackLabel={t("ui.btn.stopped")}
            onAck={noop}
            queueLine={t("ui.p1.queue_one")}
            queuePriority="P2"
          />
          <AlertTakeoverP1
            inline
            command={t("ui.p1.person_command")}
            situation={t("alert.seatbelt_moving.title")}
            instruction={t("alert.seatbelt_moving.action")}
            cause={<BeltGlyph fastened={false} size={300} label={t("ui.rail.belt_off")} />}
            ackLabel={t("ui.btn.stopped")}
            onAck={noop}
          />
          <CabFrame>
            <AlertBannerP2 inline situation={t("ui.p2.person")} detail={t("alert.proximity_danger.action")}
              seenLabel={t("ui.btn.seen")} onSeen={noop} />
            <AlertStripP3 inline text={t("ui.p3.heat")} actionLabel={t("ui.btn.later")} onAction={noop} />
            <AlertFeedP4 label={t("ui.ks.alerts")} items={[
              { id: "a", title: t("alert.risk_band_raised.title"), meta: "10:45", unread: true },
              { id: "b", title: t("alert.fatigue_warn.title"), meta: "10:30" },
            ]} />
            <QueuePip priority="P2" count={1} label={t("ui.rail.queue_label")} />
          </CabFrame>
        </Section>

        <Section id="tasks" title={t("ui.ks.tasks")}>
          <CabFrame>
            <div className="flex gap-6">
              <div className="flex min-w-0 flex-1 flex-col">
                <TaskRow number={1} status="active" nowLabel={t("ui.task.now")} title={t("ui.ks.task_load")}
                  where={t("ui.ks.where_load")} zone="LOAD-A"
                  reasons={<>
                    <ReasonChip glyph={<IdleGlyph reason="WAITING_FOR_TRUCK" size={32} />} text={t("idle.WAITING_FOR_TRUCK")} />
                    <LoadBlocks done={7} total={18} label={t("ui.task.loads", { done: 7, total: 18 })} />
                  </>}
                  range={range(65, 55, 85)} />
                <TaskRow number={2} status="next" title={t("ui.ks.task_trench")} where={t("ui.ks.where_trench")} zone="DIG-A"
                  reasons={<ReasonChip glyph={<ConditionGlyph condition="wet-ground" size={32} />} text={t("ui.ks.reason_wet")} adds />}
                  range={range(130, 100, 170, "low")} />
                <TaskRow number={3} status="done" title={t("ui.ks.task_backfill")} where={t("ui.ks.where_backfill")} zone="DIG-A" actual="1 h 02 m" />
                <div className="bg-surface p-4">
                  <RangeBar confidence="unknown" label={t("ui.task.unknown")} unknownText={t("ui.task.unknown")} />
                </div>
              </div>
              <div className="w-100 shrink-0">
                <ConditionsSummary
                  heading={t("ui.task.likely_finish")}
                  finish="15:10 – 15:55"
                  note={t("ui.task.finish_note")}
                  rows={[
                    { glyph: <ConditionGlyph condition="heat" size={44} />, label: t("ui.cond.heat"), value: "45 °C" },
                    { glyph: <ConditionGlyph condition="wet-ground" size={44} />, label: t("ui.cond.wet"), value: t("ui.cond.wet_value") },
                    { glyph: <ConditionGlyph condition="fatigue" size={44} />, label: t("ui.cond.fatigue"), value: "3 h 10 m" },
                  ]}
                  risk={{ band: "amber", sentence: t("ui.cond.risk_sentence"), label: t("ui.rail.risk_label") }}
                />
              </div>
            </div>
            <RiskContributions rows={[
              { glyph: <ConditionGlyph condition="heat" size={32} />, factor: `${t("ui.cond.heat")} 45 °C`, share: 0.5 },
              { glyph: <ConditionGlyph condition="fatigue" size={32} />, factor: t("ui.cond.fatigue"), share: 0.3 },
              { glyph: <ConditionGlyph condition="wet-ground" size={32} />, factor: t("ui.cond.wet"), share: 0.2 },
            ]} />
          </CabFrame>
        </Section>

        <Section id="controls" title={t("ui.ks.controls")}>
          <CabFrame>
            <div className="flex flex-wrap items-center gap-4">
              <Button>{t("ui.btn.start")}</Button>
              <Button variant="secondary">{t("ui.btn.later")}</Button>
              <Button variant="quiet">{t("ui.btn.not_now")}</Button>
              <Button variant="danger-quiet">{t("ui.btn.delete_draft")}</Button>
              <Button disabled>{t("ui.btn.not_now")}</Button>
              <Button loading>{t("ui.btn.send_report")}</Button>
              <Button size="xl">{t("ui.btn.send_report")}</Button>
            </div>
            <LargeToggle on={toggle} onChange={setToggle} label={t("ui.toggle.read_aloud")}
              onText={t("ui.toggle.on")} offText={t("ui.toggle.off")} />
            <SegmentedControl label={t("ui.lang.segment_label")} value={narration} onChange={setNarration} options={langOptions} />
            <ChecklistItem text={t("ui.ks.checklist_item")} answer={check} onAnswer={setCheck}
              okLabel={t("ui.btn.ok")} problemLabel={t("ui.btn.problem")} />
            <div className="flex flex-wrap items-start gap-12">
              <PinPad entered={pin} onDigit={() => setPin((p) => Math.min(4, p + 1))} onBackspace={() => setPin((p) => Math.max(0, p - 1))}
                label={t("ui.pin.progress", { entered: pin })} backspaceLabel={t("ui.pin.backspace")} error={t("ui.pin.wrong")} />
              <BadgeTarget title={t("ui.badge.title")} hint={t("ui.badge.hint")} />
              <div className="flex gap-8">
                <PushToTalk state="idle" label={t("ui.ptt.idle")} />
                <PushToTalk state="listening" label={t("ui.ptt.listening")} />
              </div>
            </div>
          </CabFrame>
        </Section>

        <Section id="insights" title={t("ui.ks.insights")}>
          <CabFrame>
            <TimeSplit
              summary={t("ui.coach.split_summary")}
              names={names}
              axis={["07:00", "09:00", "11:00", "13:00", "15:00"]}
              segments={[
                { kind: "WARM_UP", minutes: 8 }, { kind: "WORKING", minutes: 70 },
                { kind: "WAITING_FOR_TRUCK", minutes: 20 }, { kind: "WORKING", minutes: 90 },
                { kind: "SCHEDULED_BREAK", minutes: 15 }, { kind: "WORKING", minutes: 60 },
                { kind: "UNATTENDED_RUNNING", minutes: 6 }, { kind: "HABIT", minutes: 12 },
                { kind: "WORKING", minutes: 50 }, { kind: "UNKNOWN", minutes: 9 }, { kind: "OFF", minutes: 30 },
              ]}
            />
            <div>
              <IdleSegmentRow reason="WAITING_FOR_TRUCK" name={t("idle.WAITING_FOR_TRUCK")} why={t("ui.coach.idle_why_truck")} minutes={30} />
              <IdleSegmentRow reason="UNATTENDED_RUNNING" name={t("idle.UNATTENDED_RUNNING")} why={t("ui.coach.idle_why_cab")} minutes={10} />
              <IdleSegmentRow reason="UNKNOWN" name={t("idle.UNKNOWN")} why={t("ui.coach.idle_why_unknown")} minutes={9} />
            </div>
            <div className="grid grid-cols-2 gap-6">
              <CoachingNote kind="went-well" heading={t("ui.coach.went_well")} text={t("ui.coach.went_well_text")} />
              <CoachingNote kind="idea" heading={t("ui.coach.idea")} text={t("ui.learn.lesson_sentence")}
                action={<Button variant="secondary">{t("ui.btn.start")}</Button>} />
            </div>
          </CabFrame>
        </Section>

        <Section id="learn" title={t("ui.ks.learn")}>
          <CabFrame>
            <LessonCard status={t("ui.learn.recommended")} title={t("ui.learn.lesson_sentence")}
              meta={t("ui.learn.minutes", { minutes: 2 })} art={<MachineGlyph state="working" size={72} />} />
            <NarratedCardPlayer
              diagram={<Reach tier="clear" size={230} label={t("ui.learn.lesson_sentence")} />}
              sentence={t("ui.learn.lesson_sentence")} fact={t("ui.learn.lesson_fact")}
              card={2} cards={5} progressLabel={t("ui.learn.progress", { card: 2, cards: 5 })}
              playing playLabel={t("ui.btn.play")} pauseLabel={t("ui.btn.pause")} againLabel={t("ui.btn.again")}
              onPlayPause={noop} onAgain={noop}
              language={<SegmentedControl label={t("ui.lang.segment_label")} value={narration} onChange={setNarration} options={langOptions} />}
            />
            <QuizOption letter="A" text={t("ui.learn.quiz_right")} state="right" explanation={t("ui.learn.quiz_why")} />
            <QuizOption letter="B" text={t("ui.learn.quiz_wrong")} state="wrong" />
            <DrillFrame
              pausedNote={t("ui.learn.paused_only")}
              scene={<div className="flex h-full items-center justify-center"><MachineGlyph state="idle" size={160} /></div>}
              markers={[
                { id: "a", x: 30, y: 40, found: true, label: t("ui.learn.hazard") },
                { id: "b", x: 70, y: 60, found: false, label: t("ui.learn.hazard") },
              ]}
              stopLabel={t("ui.btn.stop_drill")} onStop={noop}
            />
            <div className="grid grid-cols-3 gap-4">
              <BookingSlot day={t("ui.learn.slot_day")} time="09:00" who={t("ui.learn.slot_who")} where={t("ui.learn.slot_where")} state="open" fullLabel={t("ui.learn.full")} />
              <BookingSlot day={t("ui.learn.slot_day")} time="11:00" who={t("ui.learn.slot_who")} where={t("ui.learn.slot_where")} state="selected" fullLabel={t("ui.learn.full")} />
              <BookingSlot day={t("ui.learn.slot_day")} time="14:00" who={t("ui.learn.slot_who")} where={t("ui.learn.slot_where")} state="full" fullLabel={t("ui.learn.full")} />
            </div>
            <SkillLadder name={t("ui.learn.skill")} level={3} levels={5} next={t("ui.learn.skill_next")}
              label={t("ui.learn.skill_label", { level: 3, levels: 5 })} />
          </CabFrame>
        </Section>

        <Section id="voice" title={t("ui.ks.voice")}>
          <CabFrame>
            <TranscriptSheet inline stateWord={t("ui.ptt.listening")} finalText={t("ui.report.sample_what")}
              pendingText="LOAD-A" helper={t("ui.ptt.helper")} level={0.6} />
            <TranscriptSheet inline stateWord={t("ui.ptt.idle")} finalText="" error={t("ui.ptt.error")} />
            <AssistantAnswer question={t("ui.ask.you_asked", { question: t("ui.ask.sample_question") })}
              answer={t("ui.ask.sample_answer")}
              sources={<SourceChip title={t("ui.ask.sample_source")} section={t("ui.ask.sample_section")} />}
              actions={<Button variant="secondary">{t("ui.btn.read_again")}</Button>} />
            <AssistantAnswer offlineTag={t("ui.ask.offline_tag")}
              question={t("ui.ask.you_asked", { question: t("ui.ask.sample_question") })}
              answer={t("ui.ask.sample_answer")}
              sources={<SourceChip offline title={t("ui.ask.sample_source")} section={t("ui.ask.sample_section")} />} />
            <AssistantAnswer unknown question={t("ui.ask.you_asked", { question: t("ui.ask.sample_question") })}
              answer={t("ui.ask.dont_know")} />
          </CabFrame>
        </Section>

        <Section id="states" title={t("ui.ks.states")}>
          <CabFrame>
            <SystemState kind="empty" glyph={<ConditionGlyph condition="clock" size={72} />}
              heading={t("ui.state.empty_title")} text={t("ui.state.empty_text")} />
            <SystemState kind="offline" glyph={<NetGlyph state="offline" size={72} />}
              heading={t("ui.sync.offline")} text={t("ui.state.offline_text", { count: 3 })} />
            <SystemState kind="stale" glyph={<ProximityGlyph tier="clear" size={72} />}
              heading={t("ui.state.stale_title")} text={t("ui.state.stale_text")} />
            <SystemState kind="error" heading={t("ui.state.error_title")} text={t("ui.state.error_text")}
              action={<Button variant="secondary">{t("ui.btn.again")}</Button>} />
            <div className="flex flex-wrap items-center gap-8">
              <SyncState state="waiting" words={t("ui.sync.waiting", { count: 3 })} label={t("ui.sync.waiting", { count: 3 })} />
              <SyncState state="synced" label={t("ui.sync.synced_at", { time: "10:42" })} />
              <StaleMark text={t("ui.stale", { seconds: 40 })} />
            </div>
            <ReportDraftCard
              offlineTag={t("ui.report.offline_tag")}
              fields={[
                { key: "type", name: t("ui.report.type"), value: t("ui.report.near_miss") },
                { key: "where", name: t("ui.report.where_when"), value: "LOAD-A · 12:10" },
                { key: "what", name: t("ui.report.what"), value: t("ui.report.sample_what"), unsure: t("ui.report.check") },
                { key: "people", name: t("ui.report.people"), value: t("ui.report.people_one") },
              ]}
              editLabel={t("ui.btn.edit")} sendLabel={t("ui.btn.send_offline")} deleteLabel={t("ui.btn.delete_draft")}
              onEdit={noop} onSend={noop} onDelete={noop}
            />
          </CabFrame>
        </Section>

        <Section id="console" title={t("ui.ks.console")}>
          <DemoBar label={t("ui.demo.label")}>
            <Button size="console" variant="secondary">{t("ui.btn.play")}</Button>
            <Button size="console" variant="secondary">{t("ui.btn.pause")}</Button>
          </DemoBar>
          <div className="flex flex-wrap items-start gap-6">
            <MapLegend title={t("ui.legend.title")} items={[
              { symbol: <MapSymbol kind="machine" />, label: t("ui.legend.machine") },
              { symbol: <MapSymbol kind="rings" />, label: t("ui.legend.rings") },
              { symbol: <MapSymbol kind="truck" />, label: t("ui.legend.truck") },
              { symbol: <MapSymbol kind="worker" />, label: t("ui.legend.worker") },
              { symbol: <MapSymbol kind="zone" />, label: t("ui.legend.zone") },
            ]} />
            <div className="w-80">
              <FleetTile country="IN" localTime="10:42" name="Chennai Outer Ring Road — Package 3"
                active={t("ui.fleet.active", { active: 12, total: 24 })}
                bands={{ green: 14, amber: 8, red: 2 }} bandsLabel={t("ui.fleet.bands", { green: 14, amber: 8, red: 2 })}
                condition={`${t("ui.cond.heat")} 45 °C`} />
            </div>
            <Sparkline values={[3900, 4100, 3800, 4300, 4082, 4200, 3950, 4082]}
              lastLabel={t("ui.fleet.spark_last", { value: "4,082" })} peakLabel={t("ui.fleet.spark_peak", { value: "4,300" })}
              label={t("ui.fleet.spark_label")} />
          </div>
        </Section>
      </main>
    </div>
  );
}
