/**
 * Ask Cat (F-ASK-01…06; TRD §11.2 /ask). Speak through push-to-talk (the answer is read aloud),
 * type a question, or tap an example. Answers come only from the manuals on this machine: online answers show
 * their sources; offline answers are the manual's own passage, labelled as such; when the manuals
 * have no answer, the assistant says so and does not guess. The sample-content banner is always
 * shown (TRD §10.1).
 */
import type { AskResponse } from "@shiftmate/contracts";
import { AssistantAnswer, Button, SourceChip } from "@shiftmate/ui";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";

import { api } from "../api";
import { speak } from "../live/audio";
import { useSession } from "../session";

export function answerText(t: (k: string) => string, r: AskResponse): string {
  if (r.answer) return r.answer;
  return r.notice_key ? t(r.notice_key) : t("ask.dont_know");
}

export function Ask() {
  const { t, i18n } = useTranslation();
  const language = useSession((s) => s.language);
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [reply, setReply] = useState<AskResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const ask = async (q: string, aloud = false) => {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setFailed(false);
    setQuestion(text);
    setAsked(text);
    setReply(null);
    try {
      const r = await api.ask(text, language);
      setReply(r);
      // a spoken question gets a spoken answer (DESIGN PushToTalk: "answer sheet opens, read aloud")
      if (aloud) {
        const words = answerText(t, r);
        speak(words, i18n.language, language === "en" ? words : "");
      }
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  // arriving from push-to-talk with the question already heard
  const location = useLocation();
  const spoken = (location.state as { question?: string } | null)?.question;
  const handled = useRef<string | null>(null);
  useEffect(() => {
    if (!spoken || handled.current === location.key) return;
    handled.current = location.key;
    void ask(spoken, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per arrival
  }, [spoken, location.key]);

  const shown = reply ? answerText(t, reply) : "";
  // a note that is not the answer itself (e.g. "this part is only in English")
  const note = reply?.answer && reply.notice_key ? t(reply.notice_key) : null;

  return (
    <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_400px]">
      <section className="flex min-w-0 flex-col gap-5 pb-24">
        <header className="flex flex-col gap-1">
          <h1 className="text-cab-heading">{t("ui.ask.title")}</h1>
          <p className="text-cab-meta text-ink-2">{t("ui.ask.intro")}</p>
        </header>
        <form
          className="flex flex-wrap items-stretch gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            aria-label={t("ui.ask.input")}
            placeholder={t("ui.ask.input")}
            className="sm-rule sm-focus min-h-(--sm-size-target) min-w-0 flex-1 bg-surface px-4 text-cab-body"
          />
          <Button type="submit" size="standard" loading={busy} disabled={!question.trim()}>
            {t("ui.ask.send")}
          </Button>
        </form>
        {busy && <p className="text-cab-body">{t("ui.ptt.thinking")}</p>}
        {failed && <p className="text-cab-body">{t("ui.ask.failed")}</p>}
        {reply && asked && (
          <AssistantAnswer
            question={t("ui.ask.you_asked", { question: asked })}
            answer={shown}
            unknown={!reply.answerable}
            offlineTag={reply.mode === "offline" && reply.answerable ? t("ui.ask.offline_answer") : undefined}
            sources={
              reply.citations.length > 0 ? (
                <>
                  {reply.citations.map((c) => (
                    <SourceChip key={c.chunk_id} title={c.title} section={c.section} offline={reply.mode === "offline"} />
                  ))}
                </>
              ) : undefined
            }
            actions={
              <>
                <Button variant="secondary" onClick={() => speak(shown, i18n.language, reply.language === "en" ? shown : "")}>
                  {t("ui.ask.read_aloud")}
                </Button>
                <Button
                  variant="quiet"
                  onClick={() => {
                    setReply(null);
                    setAsked(null);
                    setQuestion("");
                  }}
                >
                  {t("ui.ask.new")}
                </Button>
              </>
            }
          />
        )}
        {note && <p className="text-cab-meta text-ink-2">{note}</p>}
      </section>
      <aside className="flex min-w-0 flex-col gap-4 pb-24">
        <h2 className="text-cab-label">{t("ui.ask.examples")}</h2>
        {(["ui.ask.example1", "ui.ask.example2", "ui.ask.example3"] as const).map((k) => (
          <Button
            key={k}
            variant="secondary"
            className="justify-start text-left"
            onClick={() => {
              setQuestion(t(k));
              void ask(t(k));
            }}
          >
            {t(k)}
          </Button>
        ))}
        <p className="sm-dash mt-4 bg-surface p-3 text-cab-meta text-ink-2">{t("ui.ask.banner")}</p>
      </aside>
    </div>
  );
}
