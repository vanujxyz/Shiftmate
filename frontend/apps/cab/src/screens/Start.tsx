/**
 * Start of shift (F-START-01…04): choose the language (each in its own script), sign in with the
 * badge QR or the 4-digit PIN (demo PIN = operator number), then the walkaround checklist with an
 * explicit OK / Problem per item. Problems become reports on the edge (ChecklistResult).
 */
import type { ChecklistResult, Language } from "@shiftmate/contracts";
import {
  BadgeTarget,
  Button,
  ChecklistItem,
  PinPad,
  SegmentedControl,
  SystemState,
} from "@shiftmate/ui";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api, EdgeError } from "../api";
import { useLive } from "../live/store";
import { speak } from "../live/audio";
import { useCabConfig } from "../queries";
import { useSession } from "../session";
import { checklistAnswer } from "../voice/commands";
import { listen, speechSupport } from "../voice/recognizer";
import { BadgeScanner, cameraAvailable, operatorFromBadge } from "./BadgeScanner";

type Step = "language" | "badge" | "pin" | "checklist" | "problems";
const LANGS: Language[] = ["en", "hi", "ta"];
const PIN_LENGTH = 4;

export function Start() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const session = useSession();
  const resetLive = useLive((s) => s.reset);
  const [step, setStep] = useState<Step>("language");
  const [pin, setPinState] = useState("");
  // The digits typed so far, read synchronously: two quick taps can land before a re-render.
  const pinRef = useRef("");
  const setPin = (value: string) => {
    pinRef.current = value;
    setPinState(value);
  };
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState<Record<string, "ok" | "problem">>({});
  const [result, setResult] = useState<ChecklistResult | null>(null);

  const demo = useQuery({
    queryKey: ["demo-state"],
    queryFn: api.demoState,
    retry: false,
    refetchInterval: (q) => (q.state.data?.focus_machine ? false : 3000),
  });
  const config = useCabConfig();
  const machineId = demo.data?.focus_machine ?? null;

  const chooseLanguage = (lang: Language) => {
    session.setLanguage(lang);
    void i18n.changeLanguage(lang);
  };

  const signIn = async (operatorId: string, how: { pin?: string; badge?: string }) => {
    if (!machineId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.signIn({ operator_id: operatorId, machine_id: machineId, language: session.language, ...how });
      resetLive();
      session.signIn({ operatorId, machineId, name: res.profile.operator.name });
      setAnswers({});
      setStep("checklist");
    } catch (e) {
      // An unknown operator reads the same as a wrong PIN: the pad never says which one it was.
      const wrong = e instanceof EdgeError && (e.status === 401 || e.status === 404);
      setError(wrong ? t(how.badge ? "ui.start.badge_unknown" : "ui.pin.wrong") : t("ui.start.failed"));
      if (how.badge && wrong) setStep("pin");
    } finally {
      setBusy(false);
      setPin("");
    }
  };

  const onDigit = (d: string) => {
    if (busy || pinRef.current.length >= PIN_LENGTH) return;
    const next = pinRef.current + d;
    setPin(next);
    setError(null);
    if (next.length === PIN_LENGTH) void signIn(`OP${next}`, { pin: next });
  };

  const onBadge = (text: string) => {
    const operatorId = operatorFromBadge(text);
    if (!operatorId) {
      setError(t("ui.start.badge_unknown"));
      setStep("pin");
      return;
    }
    void signIn(operatorId, { badge: text });
  };

  const items = config.data?.checklist ?? [];
  const left = items.filter((i) => !answers[i.id]).length;
  const itemText = (i: (typeof items)[number]) => i.text[session.language] ?? i.text.en ?? i.id;

  // answering by voice (F-START-04): the item is read out, then "OK", "Problem" or "All OK"
  const [voiceState, setVoiceState] = useState<"off" | "listening">("off");
  const voiceAnswer = () => {
    const Ctor = speechSupport();
    const next = items.find((i) => !answers[i.id]);
    if (!next) return;
    if (!Ctor) {
      setError(t("ui.voice.not_supported"));
      return;
    }
    setError(null);
    speak(itemText(next), i18n.language, session.language === "en" ? itemText(next) : "");
    setVoiceState("listening");
    listen(
      Ctor,
      session.language,
      () => undefined,
      (heard) => {
        setVoiceState("off");
        const a = checklistAnswer(heard, config.data?.checklist_voice);
        if (a === "all_ok") {
          const rest = items.filter((i) => !answers[i.id]);
          // read the remaining items back, then answer them all OK (DESIGN ChecklistItem)
          const list = rest.map(itemText).join(". ");
          speak(list, i18n.language, session.language === "en" ? list : "");
          setAnswers((s) => Object.fromEntries(items.map((i) => [i.id, s[i.id] ?? "ok"])));
        } else if (a) {
          setAnswers((s) => ({ ...s, [next.id]: a }));
        } else {
          setError(t("ui.ptt.error"));
        }
      },
      () => {
        setVoiceState("off");
        setError(t("ui.ptt.error"));
      },
    );
  };
  const submitChecklist = async () => {
    const signedIn = useSession.getState().signedIn;
    if (!signedIn) return;
    setBusy(true);
    try {
      const res = await api.checklist({
        operator_id: signedIn.operatorId,
        machine_id: signedIn.machineId,
        answers: items.map((i) => ({ item_id: i.id, ok: answers[i.id] === "ok" })),
      });
      if (res.problems > 0) {
        setResult(res);
        setStep("problems");
      } else {
        void navigate("/");
      }
    } catch {
      setError(t("ui.start.failed"));
    } finally {
      setBusy(false);
    }
  };

  // The edge's state, said in the operator's language: the language choice always comes first.
  let edgeState = null;
  if (demo.isError) {
    edgeState = (
      <SystemState
        kind="error"
        heading={t("ui.health.edge_down")}
        text={t("ui.start.edge_down_text")}
        action={<Button variant="secondary" onClick={() => void demo.refetch()}>{t("ui.start.retry")}</Button>}
      />
    );
  } else if (demo.isPending) {
    edgeState = <p className="text-cab-body">{t("ui.health.checking")}</p>;
  } else if (!machineId) {
    edgeState = <SystemState kind="empty" heading={t("ui.start.not_ready_title")} text={t("ui.start.not_ready_text")} />;
  }

  let body;
  if (step === "language" || edgeState) {
    body = (
      <div className="flex flex-col items-start gap-8">
        <h2 className="text-cab-heading">{t("ui.start.language")}</h2>
        <SegmentedControl<Language>
          label={t("ui.lang.label")}
          value={session.language}
          onChange={chooseLanguage}
          options={LANGS.map((l) => ({ value: l, label: t(`ui.lang.${l}`), lang: l }))}
        />
        {edgeState ?? (
          <Button size="xl" onClick={() => setStep(cameraAvailable() ? "badge" : "pin")}>
            {t("ui.start.next")}
          </Button>
        )}
      </div>
    );
  } else if (step === "badge") {
    body = (
      <div className="flex flex-wrap items-start gap-10">
        <BadgeTarget title={t("ui.badge.title")} hint={t("ui.badge.hint")}>
          <BadgeScanner
            label={t("ui.badge.title")}
            onRead={onBadge}
            onNoCamera={() => {
              setError(t("ui.start.camera_off"));
              setStep("pin");
            }}
          />
        </BadgeTarget>
        <div className="flex flex-col gap-4">
          {busy && <p className="text-cab-body">{t("ui.start.signing_in")}</p>}
          <Button variant="secondary" onClick={() => setStep("pin")}>{t("ui.start.use_pin")}</Button>
          <Button variant="quiet" onClick={() => setStep("language")}>{t("ui.start.back")}</Button>
        </div>
      </div>
    );
  } else if (step === "pin") {
    body = (
      <div className="flex flex-wrap items-start gap-10">
        <div className="flex flex-col items-center gap-4">
          <h2 className="text-cab-heading">{t("ui.start.pin_title")}</h2>
          <PinPad
            length={PIN_LENGTH}
            entered={pin.length}
            onDigit={onDigit}
            onBackspace={() => setPin(pinRef.current.slice(0, -1))}
            label={t("ui.pin.progress", { entered: pin.length })}
            backspaceLabel={t("ui.pin.backspace")}
            error={error ?? undefined}
          />
        </div>
        <div className="flex flex-col gap-4">
          {busy && <p className="text-cab-body">{t("ui.start.signing_in")}</p>}
          {cameraAvailable() && (
            <Button variant="secondary" onClick={() => { setError(null); setStep("badge"); }}>
              {t("ui.start.use_badge")}
            </Button>
          )}
          <Button variant="quiet" onClick={() => setStep("language")}>{t("ui.start.back")}</Button>
        </div>
      </div>
    );
  } else if (step === "checklist") {
    body = (
      <div className="flex flex-col gap-4">
        <h2 className="text-cab-heading">{t("ui.start.welcome", { name: session.signedIn?.name ?? "" })}</h2>
        <p className="text-cab-label">{t("ui.start.checklist_title")}</p>
        <p className="text-cab-meta text-ink-2">{t("ui.start.checklist_hint")}</p>
        <p className="text-cab-meta text-ink-2">{t("ui.voice.checklist_hint")}</p>
        <div className="flex flex-col">
          {items.map((i) => (
            <ChecklistItem
              key={i.id}
              text={itemText(i)}
              answer={answers[i.id] ?? null}
              onAnswer={(a) => setAnswers((s) => ({ ...s, [i.id]: a }))}
              okLabel={t("ui.btn.ok")}
              problemLabel={t("ui.btn.problem")}
            />
          ))}
        </div>
        {error && <p className="text-cab-body">{error}</p>}
        <div className="flex flex-wrap items-center gap-6 pb-8">
          <Button variant="secondary" disabled={left === 0 || voiceState === "listening"} onClick={voiceAnswer}>
            {voiceState === "listening" ? t("ui.ptt.listening") : t("ui.voice.checklist_button")}
          </Button>
          <Button
            variant="secondary"
            disabled={left === 0}
            onClick={() =>
              setAnswers((s) => Object.fromEntries(items.map((i) => [i.id, s[i.id] ?? "ok"])))
            }
          >
            {t("ui.start.all_ok")}
          </Button>
          <Button size="xl" disabled={left > 0 || items.length === 0} loading={busy} onClick={() => void submitChecklist()}>
            {t("ui.start.begin")}
          </Button>
          {left > 0 && <p className="text-cab-meta text-ink-2">{t("ui.start.checklist_left", { count: left })}</p>}
        </div>
      </div>
    );
  } else {
    body = (
      <div className="flex flex-col items-start gap-6">
        <SystemState
          kind="empty"
          heading={t("ui.start.checklist_title")}
          text={t("ui.start.problems_saved", { count: result?.problems ?? 0 })}
        />
        <Button size="xl" onClick={() => void navigate("/")}>{t("ui.start.begin")}</Button>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-ground px-12 py-10 text-ink">
      <header className="mb-8 flex flex-wrap items-baseline justify-between gap-6">
        <h1 className="text-cab-title">{t("ui.start.title")}</h1>
        {machineId && <p className="sm-decal text-cab-label">{t("ui.start.machine", { id: machineId })}</p>}
      </header>
      {body}
    </main>
  );
}
