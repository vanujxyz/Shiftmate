/**
 * Instructor booking (PRD F-LRN-05; DESIGN §10 BookingSlot). Sessions at the site's Cat dealer
 * training centre for the next ten days, each with its topic and seats left. Pick one, then book
 * it; sessions already booked by this operator say so, full ones cannot be picked.
 */
import { BookingSlot, Button, SystemState } from "@shiftmate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api } from "../../api";
import { useLessons, useProgress, useSlots } from "../../queries";
import { useSession } from "../../session";
import { clockOf } from "../../text";
import { loc } from "./words";

export function Booking() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const language = useSession((s) => s.language);
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  const slots = useSlots();
  const lessons = useLessons();
  const progress = useProgress();
  const [selected, setSelected] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const day = new Intl.DateTimeFormat(i18n.language, { weekday: "long", day: "numeric", month: "short" });
  const dayOf = (iso: string) => day.format(new Date(`${iso.slice(0, 10)}T12:00:00`));
  const topic = (id: string | null | undefined) => {
    const l = lessons.data?.find((x) => x.id === id);
    return l ? loc(l.title, language) : (id ?? "");
  };
  const mine = new Set(progress.data?.bookings.map((b) => b.slot_id) ?? []);

  const book = async () => {
    const slot = slots.data?.find((s) => s.slot_id === selected);
    if (!slot || !operatorId) return;
    setBusy(true);
    try {
      await api.book(operatorId, slot.slot_id);
      setMessage(t("ui.learn.booked", { day: dayOf(slot.start), time: clockOf(slot.start), topic: topic(slot.topic) }));
      setSelected(null);
      void queryClient.invalidateQueries({ queryKey: ["slots"] });
      void queryClient.invalidateQueries({ queryKey: ["progress"] });
    } catch {
      setMessage(t("ui.learn.book_failed"));
      void queryClient.invalidateQueries({ queryKey: ["slots"] });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 p-6 pb-28">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-cab-heading">{t("ui.learn.book_title")}</h1>
          <p className="text-cab-meta text-ink-2">{t("ui.learn.book_intro")}</p>
        </div>
        <Button variant="quiet" onClick={() => void navigate("/learn")}>{t("ui.learn.back")}</Button>
      </div>
      {message && <p className="sm-heavy bg-surface p-4 text-cab-body" role="status">{message}</p>}
      {slots.isError && !slots.data ? (
        <SystemState kind="error" heading={t("ui.learn.book_title")} text={t("ui.learn.load_failed")} />
      ) : slots.data && slots.data.length === 0 ? (
        <SystemState kind="empty" heading={t("ui.learn.book_title")} text={t("ui.learn.book_none")} />
      ) : (
        <div className="flex flex-col gap-3">
          {slots.data?.map((s) => (
            <BookingSlot
              key={s.slot_id}
              day={dayOf(s.start)}
              time={clockOf(s.start) ?? ""}
              who={s.dealer_centre}
              where={`${topic(s.topic)} · ${t("ui.learn.seats", { count: s.seats_left })}`}
              state={mine.has(s.slot_id) || s.seats_left === 0 ? "full" : selected === s.slot_id ? "selected" : "open"}
              fullLabel={mine.has(s.slot_id) ? t("ui.learn.booked_mark") : t("ui.learn.full")}
              onSelect={() => setSelected(s.slot_id)}
            />
          ))}
        </div>
      )}
      {selected && (
        <div className="sticky bottom-0 flex justify-end bg-ground py-3">
          <Button size="xl" loading={busy} onClick={() => void book()}>{t("ui.learn.book_confirm")}</Button>
        </div>
      )}
    </div>
  );
}
