/**
 * Learn (TRD §11.1 `/learn`; PRD F-LRN-01, 02; DESIGN §10 LessonCard). Suggested lessons first,
 * each with the plain reason it is suggested, then every lesson with whether it is done. Lessons
 * only open while the machine is parked: in Working mode the cab shows only the rail, the task
 * line and alerts (F-LRN-03). Instructor booking and progress are one tap away.
 */
import type { LessonSummary } from "@shiftmate/contracts";
import { Button, Illustration, LessonCard, SystemState } from "@shiftmate/ui";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { useLessons, useRecommended } from "../../queries";
import { useSession } from "../../session";
import { formatKey, loc, whyText } from "./words";

export function Learn() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const language = useSession((s) => s.language);
  const lessons = useLessons();
  const recommended = useRecommended();

  const card = (l: LessonSummary, status: string | undefined) => (
    <LessonCard
      key={l.id}
      status={status}
      title={loc(l.title, language)}
      meta={t(formatKey(l.format), { minutes: Math.max(1, Math.round(l.duration_s / 60)) })}
      art={<Illustration name={l.art ?? "walkaround"} />}
      onOpen={() => void navigate(`/learn/${l.id}`)}
    />
  );

  return (
    <div className="flex flex-col gap-6 p-6 pb-28">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-cab-heading">{t("ui.learn.title")}</h1>
          <p className="text-cab-meta text-ink-2">{t("ui.learn.intro")}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" onClick={() => void navigate("/learn/progress")}>{t("ui.learn.progress_button")}</Button>
          <Button variant="secondary" onClick={() => void navigate("/learn/book")}>{t("ui.learn.book_button")}</Button>
        </div>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-cab-label">{t("ui.learn.recommended")}</h2>
        {recommended.data && recommended.data.length > 0 ? (
          recommended.data.map((r) => card(r.lesson, whyText(t, r.because) ?? undefined))
        ) : (
          <p className="text-cab-body text-ink-2">{t("ui.learn.none_suggested")}</p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-cab-label">{t("ui.learn.all")}</h2>
        {lessons.isError && !lessons.data ? (
          <SystemState kind="error" heading={t("ui.learn.all")} text={t("ui.learn.load_failed")} />
        ) : (
          lessons.data?.map((l) => card(l, l.completed ? t("ui.learn.done") : t("ui.learn.new")))
        )}
      </section>
    </div>
  );
}
