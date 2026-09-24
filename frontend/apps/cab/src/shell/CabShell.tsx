/**
 * The cab frame (F-CAB-01, 03; DESIGN §4 Cab grid, §10 StatusRail, ModeTransition, BottomNav,
 * PushToTalk). The rail is always on top; Working mode shows only the rail, the active task line
 * and alerts; Paused mode unlocks the screens and the bottom nav. Push-to-talk sits in the same
 * place in both modes. A lesson offered for this pause shows above the screen (F-LRN-03).
 *
 * The edge is the authority on who is signed in: once a snapshot says a different operator (or
 * nobody), the tablet returns to /start.
 */
import {
  BottomNav,
  ConditionGlyph,
  IdleGlyph,
  NetGlyph,
  PriorityGlyph,
  SensorGlyph,
  StatusRail,
  SystemState,
} from "@shiftmate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router";

import { useCabSocket } from "../live/socket";
import { type LiveState, useLive } from "../live/store";
import { flushPending } from "../offline/reports";
import { useCabConfig } from "../queries";
import { useSession } from "../session";
import { WorkingLine } from "../screens/MyShift";
import { LessonOfferCard } from "../screens/learn/Offer";
import { AlertBottom, AlertTop } from "./AlertLayer";
import { VoiceControl } from "../voice/VoiceControl";
import { railProps } from "./railProps";
import { useNow } from "./useNow";

export const TABS = ["/", "/safety", "/report", "/insights", "/learn"] as const;
const TAB_KEY: Record<(typeof TABS)[number], string> = {
  "/": "ui.nav.shift",
  "/safety": "ui.nav.safety",
  "/report": "ui.nav.report",
  "/insights": "ui.nav.day",
  "/learn": "ui.nav.learn",
};
const TAB_GLYPH = {
  "/": <ConditionGlyph condition="clock" size={44} />,
  "/safety": <PriorityGlyph priority="safe" size={44} />,
  "/report": <PriorityGlyph priority="P4" size={44} />,
  "/insights": <IdleGlyph reason="HABIT" size={44} />,
  "/learn": <SensorGlyph tier="standard" size={44} />,
};
const LOST_AFTER_MS = 3000;
const CAPTION_MS = 10_000; // a demo caption stays up this long

/**
 * The mode on screen. Going to Working is immediate (safety beats continuity), except that a
 * finger already down finishes its press first (DESIGN ModeTransition rules).
 */
export function useDisplayedMode(mode: LiveState["mode"]): LiveState["mode"] {
  const [shown, setShown] = useState(mode);
  const [pressing, setPressing] = useState(false);
  useEffect(() => {
    const down = () => setPressing(true);
    const up = () => setPressing(false);
    window.addEventListener("pointerdown", down);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => {
      window.removeEventListener("pointerdown", down);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
  }, []);
  // adjusting state while rendering (not in an effect), so the switch lands in the same frame
  if (mode !== shown && !(mode === "working" && pressing)) setShown(mode);
  return shown;
}

export function CabShell() {
  const { t, i18n } = useTranslation();
  const signedIn = useSession((s) => s.signedIn);
  const signOut = useSession((s) => s.signOut);
  const live = useLive();
  const config = useCabConfig();
  const now = useNow();
  const location = useLocation();
  const navigate = useNavigate();
  const mode = useDisplayedMode(live.mode);

  useCabSocket(signedIn?.machineId ?? null);

  // reports written while the gateway was unreachable go as soon as it answers again
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!live.connected) return;
    void flushPending().then((sent) => {
      if (sent === 0) return;
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
      void queryClient.invalidateQueries({ queryKey: ["pending-reports"] });
    });
  }, [live.connected, queryClient]);

  // the scenario's end of shift opens the operator's private My Day (PRD §9 last beat)
  const endShiftAt = live.endShiftAt;
  useEffect(() => {
    if (endShiftAt != null) void navigate("/insights");
  }, [endShiftAt, navigate]);

  const replaced = live.seq !== null && live.loaded && live.operatorId !== signedIn?.operatorId;
  const unloaded = live.seq !== null && !live.loaded;
  useEffect(() => {
    if (replaced || unloaded) signOut();
  }, [replaced, unloaded, signOut]);

  if (!signedIn || replaced || unloaded) return <Navigate to="/start" replace />;

  const rail = railProps({ ...live, mode }, t, now, signedIn.machineId);
  const lost = !live.connected && live.lastMessageAt != null && now - live.lastMessageAt > LOST_AFTER_MS;
  // Ask Cat (behind push-to-talk) is not a tab: no tab is marked while it is open; a lesson,
  // booking or progress page keeps Learn marked
  const current =
    TABS.find((tab) => tab === location.pathname || (tab !== "/" && location.pathname.startsWith(`${tab}/`))) ?? "";
  const working = mode === "working";
  // a report or question spoken while working opens its screen anyway: the operator asked for it
  // (voice stays available in Working mode, TRD §11.1); the nav stays hidden
  const byVoice = (location.pathname === "/report" || location.pathname === "/ask") && location.state != null;
  const caption = live.caption && now - live.caption.at < CAPTION_MS ? live.caption : null;

  return (
    <div data-mode={mode} className="flex h-screen flex-col overflow-hidden bg-ground text-ink">
      <StatusRail {...rail} />
      <div className="relative min-h-0 flex-1">
        <AlertTop timings={config.data?.alerts} />
        {caption && (
          <p
            role="status"
            data-testid="demo-caption"
            className="pointer-events-none absolute inset-x-0 bottom-4 z-(--sm-layer-p4) mx-auto w-fit max-w-[80%] rounded-control bg-selected px-6 py-3 text-center text-cab-label text-on-selected"
          >
            {caption.text[i18n.language] ?? caption.text.en}
          </p>
        )}
        <main className="h-full overflow-y-auto">
          {lost && (
            <div className="p-6 pb-0">
              <SystemState
                kind="stale"
                glyph={<NetGlyph state="offline" size={44} />}
                heading={t("ui.conn.lost")}
                text={t("ui.conn.lost_text")}
              />
            </div>
          )}
          {working && !byVoice ? (
            <WorkingLine />
          ) : (
            <div className="sm-rise-in">
              <LessonOfferCard />
              <Outlet />
            </div>
          )}
        </main>
        <AlertBottom />
      </div>
      {!working && (
        <BottomNav
          label={t("ui.nav.label")}
          current={current}
          onSelect={(id) => void navigate(id)}
          tabs={TABS.map((id) => ({ id, label: t(TAB_KEY[id]), glyph: TAB_GLYPH[id] }))}
          ptt={<span className="block h-34 w-34" />}
        />
      )}
      {/* push-to-talk: same place in both modes; hidden behind a P1 takeover (DESIGN) */}
      <VoiceControl hidden={live.alerts.current?.priority === "P1"} />
    </div>
  );
}
