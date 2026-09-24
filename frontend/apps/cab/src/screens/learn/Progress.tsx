/**
 * Training progress (PRD F-LRN-06; DESIGN ProgressView): lessons finished, days in a row, hazard
 * drills over time as facts, the habits the finished lessons target (how often the machine saw
 * them the week before and this week), and booked instructor sessions. Private to the operator.
 */
import { Button, SystemState } from "@shiftmate/ui";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { useLessons, useProgress } from "../../queries";
import { useSession } from "../../session";
import { clockOf } from "../../text";
import { loc, seconds } from "./words";

export function Progress() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const language = useSession((s) => s.language);
  const progress = useProgress();
  const lessons = useLessons();
  const title = (id: string | null | undefined) => {
    const l = lessons.data?.find((x) => x.id === id);
    return l ? loc(l.title, language) : (id ?? "");
  };
  const date = new Intl.DateTimeFormat(i18n.language, { weekday: "short", day: "numeric", month: "short" });
  const dayOf = (iso: string) => date.format(new Date(`${iso.slice(0, 10)}T12:00:00`));

  const header = (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <h1 className="text-cab-heading">{t("ui.learn.progress_title")}</h1>
      <Button variant="quiet" onClick={() => void navigate("/learn")}>{t("ui.learn.back")}</Button>
    </div>
  );
  if (!progress.data) {
    return (
      <div className="flex flex-col gap-5 p-6">
        {header}
        {progress.isError ? (
          <SystemState kind="error" heading={t("ui.learn.progress_title")} text={t("ui.learn.load_failed")} />
        ) : (
          <p className="text-cab-body">{t("ui.health.checking")}</p>
        )}
      </div>
    );
  }
  const p = progress.data;
  const figure = (label: string, value: string) => (
    <div className="sm-heavy flex min-w-60 flex-1 flex-col gap-1 bg-surface p-5">
      <span className="text-cab-meta text-ink-2">{label}</span>
      <span className="sm-num text-cab-title">{value}</span>
    </div>
  );

  return (
    <div className="flex flex-col gap-6 p-6 pb-28">
      {header}
      <div className="flex flex-wrap gap-4">
        {figure(t("ui.learn.lessons_done"), t("ui.learn.of", { done: p.lessons_done, total: p.lessons_total }))}
        {figure(t("ui.learn.streak"), String(p.streak_days))}
        {figure(t("ui.learn.drills_done"), String(p.drills.length))}
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-cab-label">{t("ui.learn.habits")}</h2>
        {p.habits.length === 0 ? (
          <p className="text-cab-body text-ink-2">{t("ui.learn.no_habits")}</p>
        ) : (
          p.habits.map((h) => (
            <div key={h.lesson_id} className="sm-rule flex flex-col gap-1 bg-surface p-4">
              <span className="text-cab-label">{title(h.lesson_id)}</span>
              <span className="sm-num text-cab-body">
                {t("ui.learn.habit_row", { before: h.previous_week, now: h.this_week })}
              </span>
            </div>
          ))
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-cab-label">{t("ui.learn.drills")}</h2>
        {p.drills.length === 0 ? (
          <p className="text-cab-body text-ink-2">{t("ui.learn.no_drills")}</p>
        ) : (
          <ul className="flex flex-col">
            {[...p.drills].reverse().map((d) => (
              <li key={d.ts} className="sm-rule-soft-b flex flex-wrap justify-between gap-x-6 py-3">
                <span className="text-cab-label">{dayOf(d.ts)} · {clockOf(d.ts)}</span>
                <span className="sm-num text-cab-body">
                  {t("ui.learn.drill_decisions", { right: d.correct, total: d.total })}
                  {d.mean_reaction_ms != null && ` · ${seconds(d.mean_reaction_ms)}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-cab-label">{t("ui.learn.your_bookings")}</h2>
        {p.bookings.length === 0 ? (
          <p className="text-cab-body text-ink-2">{t("ui.learn.no_bookings")}</p>
        ) : (
          p.bookings.map((b) => (
            <div key={b.booking_id} className="sm-rule flex flex-col gap-1 bg-surface p-4">
              <span className="text-cab-label">{b.start ? `${dayOf(b.start)} · ${clockOf(b.start)}` : b.slot_id}</span>
              <span className="text-cab-meta">{title(b.topic)} · {b.dealer_centre}</span>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
