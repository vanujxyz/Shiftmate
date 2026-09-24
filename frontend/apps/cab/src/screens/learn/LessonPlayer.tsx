/**
 * The lesson player (PRD F-LRN-01; DESIGN §10 NarratedCardPlayer, QuizOption). Narrated lessons
 * show one illustrated card at a time and read it aloud in the operator's language, moving on by
 * themselves while playing (Pause, Read again and Next are always there). Then the quiz: tap an
 * answer, the right one is marked with why. Finishing saves the result to the operator's progress
 * (share of right answers, time taken, language). A drill opens the hazard drill instead.
 */
import type { Lesson } from "@shiftmate/contracts";
import { Button, Illustration, NarratedCardPlayer, QuizOption, SystemState } from "@shiftmate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { api } from "../../api";
import { speak } from "../../live/audio";
import { useLesson } from "../../queries";
import { useSession } from "../../session";
import { Drill } from "./Drill";
import { loc } from "./words";

const LETTERS = ["A", "B", "C", "D"];

/** How long a card stays up while playing: long enough to hear it read, never under 5 s. */
export function cardMs(text: string): number {
  return Math.max(5000, text.split(/\s+/).length * 450 + 1500);
}

export function LessonPlayer() {
  const { t } = useTranslation();
  const { lessonId } = useParams();
  const lesson = useLesson(lessonId);
  if (lesson.isPending) return <p className="p-6 text-cab-body">{t("ui.health.checking")}</p>;
  if (!lesson.data)
    return (
      <div className="p-6">
        <SystemState kind="error" heading={t("ui.learn.title")} text={t("ui.learn.not_found")} />
      </div>
    );
  if (lesson.data.format === "drill") return <Drill key={lesson.data.id} lesson={lesson.data} />;
  return <CardsAndQuiz key={lesson.data.id} lesson={lesson.data} />;
}

function CardsAndQuiz({ lesson }: { lesson: Lesson }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const language = useSession((s) => s.language);
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  const cards = lesson.cards ?? [];
  const quiz = lesson.quiz ?? [];
  const [phase, setPhase] = useState<"cards" | "quiz" | "done">(cards.length ? "cards" : "quiz");
  const [card, setCard] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [question, setQuestion] = useState(0);
  const [chosen, setChosen] = useState<(number | null)[]>(() => quiz.map(() => null));
  const [startedAt] = useState(() => Date.now());
  const [saved, setSaved] = useState<"saving" | "ok" | "failed" | null>(null);

  const say = (text: string) => speak(text, i18n.language, language === "en" ? text : "");
  const cardText = loc(cards[card]?.text, language);

  // read the card aloud and, while playing, move on when it has been heard
  useEffect(() => {
    if (phase !== "cards" || !playing || !cardText) return;
    say(cardText);
    const id = window.setTimeout(() => {
      if (card + 1 < cards.length) setCard(card + 1);
      else setPhase(quiz.length ? "quiz" : "done");
    }, cardMs(cardText));
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per card shown
  }, [phase, card, playing]);

  // leaving the lesson (or the machine starting to work, which hides it) stops the narration
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const right = quiz.filter((q, i) => chosen[i] === q.answer).length;

  const save = async () => {
    if (!operatorId) return;
    setSaved("saving");
    try {
      await api.completeLesson(lesson.id, {
        operator_id: operatorId,
        score: quiz.length ? right / quiz.length : 1,
        duration_s: Math.round((Date.now() - startedAt) / 1000),
        language,
      });
      setSaved("ok");
      for (const key of ["lessons", "recommended", "progress"]) void queryClient.invalidateQueries({ queryKey: [key] });
    } catch {
      setSaved("failed");
    }
  };

  const finish = () => {
    window.speechSynthesis?.cancel();
    setPhase("done");
    void save();
  };

  const nextCard = () => {
    window.speechSynthesis?.cancel();
    if (card + 1 < cards.length) setCard(card + 1);
    else if (quiz.length) setPhase("quiz");
    else finish();
  };

  let body;
  if (phase === "cards") {
    body = (
      <>
        <NarratedCardPlayer
          diagram={<Illustration name={cards[card]!.illustration} className="max-h-full" />}
          sentence={cardText}
          card={card + 1}
          cards={cards.length}
          progressLabel={t("ui.learn.progress", { card: card + 1, cards: cards.length })}
          playing={playing}
          playLabel={t("ui.learn.play")}
          pauseLabel={t("ui.learn.pause")}
          againLabel={t("ui.learn.again")}
          onPlayPause={() => {
            if (playing) window.speechSynthesis?.cancel();
            setPlaying(!playing);
          }}
          onAgain={() => say(cardText)}
        />
        <div className="flex justify-end">
          <Button size="xl" onClick={nextCard}>{t("ui.learn.next")}</Button>
        </div>
      </>
    );
  } else if (phase === "quiz") {
    const q = quiz[question]!;
    const pick = chosen[question] ?? null;
    body = (
      <section className="flex flex-col gap-4">
        <p className="text-cab-meta text-ink-2">{t("ui.learn.question", { n: question + 1, total: quiz.length })}</p>
        <h2 className="text-cab-title">{loc(q.q, language)}</h2>
        <div className="flex flex-col gap-3">
          {q.options.map((o, i) => (
            <QuizOption
              key={i}
              letter={LETTERS[i]!}
              text={loc(o, language)}
              state={pick == null ? "open" : i === q.answer ? "right" : i === pick ? "wrong" : "other"}
              explanation={loc(q.explain, language)}
              onChoose={() => {
                setChosen((c) => c.map((v, k) => (k === question ? i : v)));
                say(loc(q.explain, language));
              }}
            />
          ))}
        </div>
        {pick != null && (
          <>
            <p className="text-cab-label" role="status">
              {pick === q.answer ? t("ui.learn.quiz_is_right") : t("ui.learn.quiz_is_wrong")}
            </p>
            <div className="flex justify-end">
              <Button size="xl" onClick={() => (question + 1 < quiz.length ? setQuestion(question + 1) : finish())}>
                {question + 1 < quiz.length ? t("ui.learn.next") : t("ui.learn.finish")}
              </Button>
            </div>
          </>
        )}
      </section>
    );
  } else {
    body = (
      <section className="sm-heavy flex flex-col gap-4 bg-surface p-6">
        <h2 className="text-cab-heading">{t("ui.learn.finished")}</h2>
        {quiz.length > 0 && <p className="sm-num text-cab-title">{t("ui.learn.result", { right, total: quiz.length })}</p>}
        {saved === "ok" && <p className="text-cab-body">{t("ui.learn.saved")}</p>}
        {saved === "failed" && (
          <div className="flex flex-wrap items-center gap-4">
            <p className="text-cab-body">{t("ui.learn.save_failed")}</p>
            <Button variant="secondary" onClick={() => void save()}>{t("ui.start.retry")}</Button>
          </div>
        )}
        <div>
          <Button size="xl" onClick={() => void navigate("/learn")}>{t("ui.learn.back")}</Button>
        </div>
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-6 pb-28">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-cab-heading">{loc(lesson.title, language)}</h1>
        {phase !== "done" && (
          <Button variant="quiet" onClick={() => { window.speechSynthesis?.cancel(); void navigate("/learn"); }}>
            {t("ui.learn.back")}
          </Button>
        )}
      </div>
      {body}
    </div>
  );
}
