/**
 * Report (F-REP-02…05; TRD §11.2 /report). Tap the kind of report, add a few words and two yes/no
 * answers, then check the draft: time, machine, place, task and weather are filled in by the
 * machine gateway. Every field can be changed with big buttons before sending; Send and Delete are
 * never side by side. A report reaches the office through the gateway's outbox, so it works with no
 * internet; if the gateway itself is unreachable, it waits on the tablet (offline/reports.ts).
 * Speaking a report arrives with push-to-talk in milestone 15 and ends in this same draft.
 */
import type { ReportContextModel, ReportDraft, ReportType, SavedReport, Severity } from "@shiftmate/contracts";
import { Button, NetGlyph, PriorityGlyph, ReportDraftCard, SegmentedControl, SystemState } from "@shiftmate/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";

import { api, EdgeError } from "../api";
import { useLive } from "../live/store";
import type { PendingReport } from "../offline/db";
import { clearDraft, type Draft, loadDraft, pendingReports, saveDraft, sendReport } from "../offline/reports";
import { useReports } from "../queries";
import { useSession } from "../session";
import { clockOf } from "../text";

const TYPES: ReportType[] = ["near_miss", "incident", "equipment_problem"];
const SEVERITIES: Severity[] = ["low", "medium", "high"];

type Step = "type" | "details" | "check" | "done";
type Field = "type" | "severity" | "people" | "what";

/** The operator's taps beat the words: a chosen type, people and injury always win. */
export function mergeDraft(
  parsed: ReportDraft | null,
  choice: { type: ReportType; text: string; people: boolean; injury: boolean },
): ReportDraft {
  const severity: Severity =
    parsed?.severity ?? (choice.injury ? "high" : choice.type === "near_miss" ? "medium" : "low");
  return {
    type: choice.type,
    severity: choice.injury && severity === "low" ? "medium" : severity,
    // with no words typed, the parser only saw the type's name: nothing to summarise
    summary_en: choice.text ? (parsed?.summary_en ?? choice.text) : "",
    summary_local: choice.text,
    people_involved: choice.people,
    injury: choice.people && choice.injury,
    parser: parsed ? `${parsed.parser}+tap` : "tap",
  };
}

function YesNo({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <span className="text-cab-label">{label}</span>
      <SegmentedControl<"yes" | "no">
        label={label}
        value={value ? "yes" : "no"}
        onChange={(v) => onChange(v === "yes")}
        options={[
          { value: "yes", label: t("ui.btn.yes") },
          { value: "no", label: t("ui.btn.no") },
        ]}
      />
    </div>
  );
}

function whereText(t: TFunction, context: ReportContextModel | null): string {
  if (!context) return t("ui.report.where_later");
  return t("ui.report.where_value", { zone: context.zone_id ?? context.machine_id, time: clockOf(context.ts) ?? "" });
}

function RecentReports({ pending }: { pending: PendingReport[] }) {
  const { t } = useTranslation();
  const reports = useReports();
  const online = useLive((s) => s.online);
  const rows: { id: string; draft: ReportDraft; time: string; state: "tablet" | "waiting" | "synced" }[] = [
    ...pending.map((p) => ({ id: p.id, draft: p.draft, time: "", state: "tablet" as const })),
    ...(reports.data ?? []).map((r: SavedReport) => ({
      id: r.report_id,
      draft: r.draft,
      time: clockOf(r.ts) ?? "",
      state: r.synced ? ("synced" as const) : ("waiting" as const),
    })),
  ];
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-cab-label">{t("ui.report.recent")}</h2>
      {!online && (
        <p className="flex items-center gap-3 text-cab-meta">
          <NetGlyph state="offline" size={36} />
          {t("ui.report.waiting")}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="text-cab-meta text-ink-2">{t("ui.report.none")}</p>
      ) : (
        <ul className="flex flex-col">
          {rows.slice(0, 8).map((r) => (
            <li key={r.id} className="sm-rule-soft-b flex items-start gap-4 py-3">
              <PriorityGlyph priority="P4" size={32} />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <p className="sm-t-feed">
                  {t(`report.type.${r.draft.type}`)} · {t(`report.severity.${r.draft.severity}`)}
                </p>
                {r.draft.summary_local && <p className="text-cab-meta">{r.draft.summary_local}</p>}
                <p className="sm-t-small flex flex-wrap items-center gap-x-3 text-ink-2">
                  {r.time && <span className="sm-num">{r.time}</span>}
                  <span className="flex items-center gap-2">
                    <NetGlyph state={r.state === "synced" ? "synced" : r.state === "waiting" ? "waiting" : "offline"} size={24} />
                    {t(r.state === "synced" ? "ui.report.synced" : r.state === "waiting" ? "ui.report.waiting" : "ui.report.on_tablet")}
                  </span>
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Report() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const language = useSession((s) => s.language);
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? "");
  const [step, setStep] = useState<Step>("type");
  const [type, setType] = useState<ReportType>("near_miss");
  const [text, setText] = useState("");
  const [people, setPeople] = useState(false);
  const [injury, setInjury] = useState(false);
  const [draft, setDraft] = useState<ReportDraft | null>(null);
  const [context, setContext] = useState<ReportContextModel | null>(null);
  const [editing, setEditing] = useState<Field | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const pending = useQuery({ queryKey: ["pending-reports", operatorId], queryFn: () => pendingReports(operatorId) });

  // a draft left unsent (reload, or the machine started working) comes back where it was
  useEffect(() => {
    let live = true;
    void loadDraft().then((d) => {
      if (!live || !d) return;
      setDraft(d.draft);
      setContext(d.context);
      setText(d.text);
      setType(d.draft.type);
      setPeople(d.draft.people_involved);
      setInjury(d.draft.injury);
      setStep("check");
    });
    return () => {
      live = false;
    };
  }, []);

  // a report spoken through push-to-talk (F-REP-01): the words become the draft to check
  const location = useLocation();
  const spoken = (location.state as { transcript?: string } | null)?.transcript;
  const handled = useRef<string | null>(null);
  const fromSpeech = async (transcript: string) => {
    setBusy(true);
    setMessage(null);
    setText(transcript);
    try {
      const parsed = await api.parseReport(transcript, language);
      const d = { ...parsed.draft, summary_local: parsed.draft.summary_local || transcript };
      setType(d.type);
      setPeople(d.people_involved);
      setInjury(d.injury);
      keep(d, parsed.context);
    } catch {
      // the gateway is unreachable: keep the words; place and time are added on arrival
      keep(mergeDraft(null, { type: "near_miss", text: transcript, people: false, injury: false }), null);
    } finally {
      setBusy(false);
      setStep("check");
    }
  };

  const keep = (d: ReportDraft, c: ReportContextModel | null) => {
    setDraft(d);
    setContext(c);
    const row: Draft = { draft: d, text: d.summary_local, context: c };
    void saveDraft(row);
  };

  useEffect(() => {
    if (!spoken || handled.current === location.key) return;
    handled.current = location.key;
    void fromSpeech(spoken);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per arrival
  }, [spoken, location.key]);

  const check = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const parsed = await api.parseReport(text.trim() || t(`report.type.${type}`), language);
      keep(mergeDraft(parsed.draft, { type, text: text.trim(), people, injury }), parsed.context);
      setStep("check");
    } catch (e) {
      if (e instanceof EdgeError) {
        setMessage(t("ui.report.failed"));
      } else {
        // the gateway is unreachable: the draft is built here; place and time are added on arrival
        keep(mergeDraft(null, { type, text: text.trim(), people, injury }), null);
        setStep("check");
      }
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    void clearDraft();
    setDraft(null);
    setContext(null);
    setText("");
    setPeople(false);
    setInjury(false);
    setEditing(null);
    setStep("type");
  };

  const send = async () => {
    if (!draft) return;
    setBusy(true);
    try {
      const sent = await sendReport(operatorId, draft, context, text.trim() || null);
      void clearDraft();
      setMessage(t(sent.queued ? "ui.report.queued" : "ui.report.sent"));
      setStep("done");
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
      void pending.refetch();
    } catch {
      setMessage(t("ui.report.failed"));
    } finally {
      setBusy(false);
    }
  };

  const edit = (patch: Partial<ReportDraft>) => draft && keep({ ...draft, ...patch }, context);

  let body;
  if (step === "type") {
    body = (
      <div className="flex flex-col gap-4">
        <h2 className="text-cab-heading">{t("ui.report.new")}</h2>
        {TYPES.map((k) => (
          <Button
            key={k}
            variant="secondary"
            size="xl"
            className="justify-start text-left"
            onClick={() => {
              setType(k);
              setStep("details");
            }}
          >
            <span className="flex flex-col items-start">
              <span>{t(`report.type.${k}`)}</span>
              <span className="text-cab-meta text-ink-2">{t(`report.hint.${k}`)}</span>
            </span>
          </Button>
        ))}
      </div>
    );
  } else if (step === "details") {
    body = (
      <div className="flex flex-col gap-5">
        <h2 className="text-cab-heading">{t(`report.type.${type}`)}</h2>
        <label className="flex flex-col gap-2">
          <span className="text-cab-label">{t("ui.report.what_prompt")}</span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            aria-label={t("ui.report.text_label")}
            className="sm-rule sm-focus w-full bg-surface p-4 text-cab-body"
          />
        </label>
        <YesNo label={t("ui.report.people_q")} value={people} onChange={setPeople} />
        {people && <YesNo label={t("ui.report.injury_q")} value={injury} onChange={setInjury} />}
        <p className="text-cab-meta text-ink-2">{t("ui.report.auto")}</p>
        {message && <p className="text-cab-body">{message}</p>}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Button variant="quiet" onClick={() => setStep("type")}>{t("ui.start.back")}</Button>
          <Button size="xl" loading={busy} onClick={() => void check()}>{t("ui.report.check")}</Button>
        </div>
      </div>
    );
  } else if (step === "check" && draft) {
    const peopleText = draft.people_involved
      ? `${t("ui.report.people_yes")}${draft.injury ? ` · ${t("ui.report.injury_yes")}` : ""}`
      : t("ui.report.people_no");
    body = (
      <div className="flex flex-col gap-4">
        <h2 className="text-cab-heading">{t("ui.report.check")}</h2>
        {/* filled in by the machine gateway, not typed: shown, not editable */}
        <p className="flex flex-wrap gap-x-4 text-cab-label">
          <span className="text-ink-2">{t("ui.report.where_when")}</span>
          <span className="sm-num font-bold">{whereText(t, context)}</span>
        </p>
        <ReportDraftCard
          fields={[
            { key: "type", name: t("ui.report.type"), value: t(`report.type.${draft.type}`) },
            { key: "severity", name: t("ui.report.severity"), value: t(`report.severity.${draft.severity}`) },
            { key: "what", name: t("ui.report.what"), value: draft.summary_local || t("ui.report.what_empty") },
            { key: "people", name: t("ui.report.people"), value: peopleText },
          ]}
          editLabel={t("ui.btn.edit")}
          sendLabel={context ? t("ui.btn.send_report") : t("ui.btn.send_offline")}
          deleteLabel={t("ui.btn.delete_draft")}
          offlineTag={context ? undefined : t("ui.report.offline_tag")}
          onEdit={(key) => setEditing(key as Field)}
          onSend={() => void send()}
          onDelete={reset}
        />
        {editing === "type" && (
          <SegmentedControl<ReportType>
            label={t("ui.report.type")}
            value={draft.type}
            onChange={(v) => {
              edit({ type: v });
              setEditing(null);
            }}
            options={TYPES.map((k) => ({ value: k, label: t(`report.type.${k}`) }))}
          />
        )}
        {editing === "severity" && (
          <SegmentedControl<Severity>
            label={t("ui.report.severity")}
            value={draft.severity}
            onChange={(v) => {
              edit({ severity: v });
              setEditing(null);
            }}
            options={SEVERITIES.map((k) => ({ value: k, label: t(`report.severity.${k}`) }))}
          />
        )}
        {editing === "people" && (
          <div className="flex flex-col gap-3">
            <YesNo label={t("ui.report.people_q")} value={draft.people_involved} onChange={(v) => edit({ people_involved: v, injury: v && draft.injury })} />
            {draft.people_involved && (
              <YesNo label={t("ui.report.injury_q")} value={draft.injury} onChange={(v) => edit({ injury: v })} />
            )}
            <div>
              <Button variant="secondary" onClick={() => setEditing(null)}>{t("ui.btn.done")}</Button>
            </div>
          </div>
        )}
        {editing === "what" && (
          <div className="flex flex-col gap-3">
            <textarea
              value={draft.summary_local}
              onChange={(e) => edit({ summary_local: e.target.value, summary_en: e.target.value })}
              rows={3}
              aria-label={t("ui.report.text_label")}
              className="sm-rule sm-focus w-full bg-surface p-4 text-cab-body"
            />
            <div>
              <Button variant="secondary" onClick={() => setEditing(null)}>{t("ui.btn.done")}</Button>
            </div>
          </div>
        )}
        {message && <p className="text-cab-body">{message}</p>}
      </div>
    );
  } else {
    body = (
      <div className="flex flex-col items-start gap-5">
        <SystemState kind="empty" heading={t("ui.report.title")} text={message ?? ""} />
        <Button size="xl" onClick={reset}>{t("ui.report.another")}</Button>
      </div>
    );
  }

  return (
    <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_400px]">
      <section className="flex min-w-0 flex-col gap-4 pb-24">
        <h1 className="sr-only">{t("ui.report.title")}</h1>
        {body}
      </section>
      <aside className="min-w-0 pb-24">
        <RecentReports pending={pending.data ?? []} />
      </aside>
    </div>
  );
}
