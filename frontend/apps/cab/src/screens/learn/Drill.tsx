/**
 * The hazard drill (PRD F-LRN-04; DESIGN §10 DrillFrame; D-013, D-032). Site scenes appear one at
 * a time for a few seconds. If the scene is dangerous, tap STOP or say "Stop"; if it is safe,
 * wait. Each scene is scored as a right or wrong decision, with the time to stop. Results are
 * shown as facts ("5 of 7 right", "0.8 s"), never a single score, and saved to the operator's
 * progress. Runs only while the machine is parked (the cab hides it in Working mode).
 */
import type { Lesson } from "@shiftmate/contracts";
import { Button, DrillFrame, Illustration, PriorityGlyph } from "@shiftmate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api } from "../../api";
import { useSession } from "../../session";
import { type Listener, listen, speechSupport } from "../../voice/recognizer";
import { loc, seconds } from "./words";

export const SCENE_MS = 4000; // how long a scene stays up without a STOP
export const FEEDBACK_MS = 2500; // how long the verdict stays before the next scene

/** Words that count as "stop" when said, in any of the three languages (operators mix them). */
export const STOP_WORDS = ["stop", "रुको", "रुकें", "रोको", "स्टॉप", "நிறுத்து", "நில்லு", "ஸ்டாப்"];

export function heardStop(text: string): boolean {
  const s = text.toLowerCase();
  return STOP_WORDS.some((w) => s.includes(w));
}

type Answer = { hazard_id: string; reaction_ms: number | null; correct: boolean };

export function Drill({ lesson }: { lesson: Lesson }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const language = useSession((s) => s.language);
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  const scenes = lesson.hazards ?? [];
  const [phase, setPhase] = useState<"intro" | "scene" | "feedback" | "done">("intro");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [saved, setSaved] = useState<"ok" | "failed" | null>(null);
  const shownAt = useRef(0);
  const open = useRef(false);
  const listener = useRef<Listener | null>(null);
  const running = useRef(false);
  const onStopRef = useRef<() => void>(() => undefined);

  const startListening = () => {
    const Ctor = speechSupport();
    if (!Ctor) return;
    running.current = true;
    const go = () => {
      listener.current = listen(
        Ctor,
        language,
        (h) => {
          if (heardStop(`${h.final} ${h.pending}`)) onStopRef.current();
        },
        () => {
          if (running.current) go(); // the browser ends recognition after silence: listen again
        },
        () => {
          running.current = false;
        },
      );
    };
    go();
  };
  const stopListening = () => {
    running.current = false;
    listener.current?.abort();
    listener.current = null;
  };
  const decide = (reactionMs: number | null) => {
    if (!open.current) return;
    open.current = false;
    const scene = scenes[index]!;
    const stopped = reactionMs != null;
    setAnswers((a) => [...a, { hazard_id: scene.id, reaction_ms: reactionMs, correct: scene.is_hazard === stopped }]);
    setPhase("feedback");
  };
  const onStop = () => decide(Math.round(performance.now() - shownAt.current));

  useEffect(() => {
    onStopRef.current = onStop;
  });

  const next = () => {
    if (index + 1 < scenes.length) {
      setIndex(index + 1);
      setPhase("scene");
    } else {
      setPhase("done");
      stopListening();
    }
  };
  const decideRef = useRef(decide);
  const nextRef = useRef(next);
  useEffect(() => {
    decideRef.current = decide;
    nextRef.current = next;
  });

  // a scene: mark when it appeared, and move on by itself if nobody stops
  useEffect(() => {
    if (phase === "scene") {
      shownAt.current = performance.now();
      open.current = true;
      const id = window.setTimeout(() => decideRef.current(null), SCENE_MS);
      return () => window.clearTimeout(id);
    }
    if (phase === "feedback") {
      const id = window.setTimeout(() => nextRef.current(), FEEDBACK_MS);
      return () => window.clearTimeout(id);
    }
  }, [phase, index]);

  // results are saved once, when the last scene is decided
  const total = answers.length;
  useEffect(() => {
    if (phase !== "done" || !operatorId || total !== scenes.length) return;
    let live = true;
    api
      .drillResult({ operator_id: operatorId, drill_id: lesson.id, hazards: answers })
      .then(() => {
        if (!live) return;
        setSaved("ok");
        void queryClient.invalidateQueries({ queryKey: ["progress"] });
      })
      .catch(() => live && setSaved("failed"));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, at the end
  }, [phase, total]);

  useEffect(() => () => stopListening(), []);

  const start = () => {
    setAnswers([]);
    setSaved(null);
    setIndex(0);
    setPhase("scene");
    startListening();
  };

  if (phase === "intro") {
    return (
      <div className="flex flex-col gap-5 p-6 pb-28">
        <h1 className="text-cab-heading">{loc(lesson.title, language)}</h1>
        <div className="sm-heavy flex h-82 items-center justify-center rounded-bezel bg-surface-sunk p-4">
          <Illustration name={lesson.art ?? "drill-intro"} className="max-h-full" />
        </div>
        <p className="text-cab-body">{t("ui.learn.drill_intro")}</p>
        <p className="text-cab-meta text-ink-2">{t("ui.learn.paused_only")}</p>
        <div className="flex flex-wrap gap-4">
          <Button size="xl" onClick={start}>{t("ui.learn.drill_start")}</Button>
          <Button variant="quiet" onClick={() => void navigate("/learn")}>{t("ui.learn.back")}</Button>
        </div>
      </div>
    );
  }

  if (phase === "done") {
    const right = answers.filter((a) => a.correct).length;
    const stops = answers.filter((a) => a.correct && a.reaction_ms != null).map((a) => a.reaction_ms!);
    const mean = stops.length ? stops.reduce((a, b) => a + b, 0) / stops.length : null;
    return (
      <div className="flex flex-col gap-5 p-6 pb-28">
        <h1 className="text-cab-heading">{t("ui.learn.drill_done")}</h1>
        <section className="sm-heavy flex flex-col gap-2 bg-surface p-6">
          <p className="sm-num text-cab-title">{t("ui.learn.drill_decisions", { right, total: answers.length })}</p>
          {mean != null && <p className="sm-num text-cab-body">{t("ui.learn.drill_reaction", { seconds: seconds(mean) })}</p>}
        </section>
        <ul className="flex flex-col">
          {answers.map((a, i) => (
            <li key={a.hazard_id} className="sm-rule-soft-b flex items-center gap-4 py-3">
              <PriorityGlyph priority={a.correct ? "safe" : "P3"} size={40} />
              <span className="flex-1 text-cab-body">{loc(scenes[i]?.text, language)}</span>
              <span className="text-cab-label">{a.correct
                  ? t("ui.learn.drill_right")
                  : scenes[i]?.is_hazard
                    ? t("ui.learn.drill_wrong")
                    : t("ui.learn.drill_not_needed")}</span>
            </li>
          ))}
        </ul>
        {saved === "ok" && <p className="text-cab-body">{t("ui.learn.saved")}</p>}
        {saved === "failed" && <p className="text-cab-body">{t("ui.learn.save_failed")}</p>}
        <div className="flex flex-wrap gap-4">
          <Button size="xl" onClick={start}>{t("ui.learn.drill_again")}</Button>
          <Button variant="secondary" onClick={() => void navigate("/learn")}>{t("ui.learn.back")}</Button>
        </div>
      </div>
    );
  }

  const scene = scenes[index]!;
  const last = answers[answers.length - 1];
  let verdict: string | null = null;
  if (phase === "feedback" && last) {
    verdict = scene.is_hazard
      ? last.correct
        ? t("ui.learn.drill_stopped", { seconds: seconds(last.reaction_ms ?? 0) })
        : t("ui.learn.drill_missed")
      : last.correct
        ? t("ui.learn.drill_safe_waited")
        : t("ui.learn.drill_safe_stopped");
  }
  return (
    <div className="flex flex-col gap-4 p-6 pb-28">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-cab-heading">{loc(lesson.title, language)}</h1>
        <p className="sm-num text-cab-label">{t("ui.learn.drill_scene", { n: index + 1, total: scenes.length })}</p>
      </div>
      <DrillFrame
        scene={<Illustration name={scene.scene} label={t("ui.learn.drill_scene", { n: index + 1, total: scenes.length })} />}
        markers={[]}
        stopLabel={t("ui.learn.drill_stop")}
        onStop={phase === "scene" ? onStop : () => undefined}
        pausedNote={speechSupport() ? t("ui.learn.drill_voice") : undefined}
      />
      <p className="min-h-16 text-cab-title" role="status">
        {verdict && (
          <>
            {verdict} <span className="text-cab-body text-ink-2">{loc(scene.text, language)}</span>
          </>
        )}
      </p>
    </div>
  );
}
