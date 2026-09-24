/**
 * The pause-time lesson offer (PRD F-LRN-03; TRD §6.9 P4 `lesson_offered`). The edge offers a
 * lesson only when a long pause starts (waiting for a truck, a break, engine off) and never while
 * working; the cab shows it as a quiet card in Paused mode with Start and Not now. Going back to
 * work ends the offer.
 */
import { Button, Illustration } from "@shiftmate/ui";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router";

import { useLive } from "../../live/store";
import { useLessons } from "../../queries";
import { useSession } from "../../session";
import { formatKey, loc, whyText } from "./words";

export function LessonOfferCard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const offer = useLive((s) => s.lessonOffer);
  const dismiss = useLive((s) => s.dismissOffer);
  const language = useSession((s) => s.language);
  const lessons = useLessons();
  const lesson = lessons.data?.find((l) => l.id === offer?.lesson_id);
  if (!offer || !lesson || location.pathname.startsWith("/learn/")) return null;
  const why = whyText(t, offer.because);
  return (
    <section className="sm-rule m-6 mb-0 flex flex-wrap items-center gap-5 bg-surface p-4" aria-label={t("ui.learn.offer_title")}>
      <span className="flex h-24 w-36 shrink-0 items-center justify-center rounded-bezel bg-surface-sunk">
        <Illustration name={lesson.art ?? "walkaround"} />
      </span>
      <div className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
        <span className="text-cab-meta text-ink-2">{t("ui.learn.offer_title")}</span>
        <span className="text-cab-label">{loc(lesson.title, language)}</span>
        <span className="text-cab-meta text-ink-2">
          {t(formatKey(lesson.format), { minutes: Math.max(1, Math.round(lesson.duration_s / 60)) })}
          {why ? ` · ${why}` : ""}
        </span>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button
          onClick={() => {
            dismiss();
            void navigate(`/learn/${lesson.id}`);
          }}
        >
          {t("ui.learn.offer_start")}
        </Button>
        <Button variant="quiet" onClick={dismiss}>{t("ui.learn.offer_later")}</Button>
      </div>
    </section>
  );
}
