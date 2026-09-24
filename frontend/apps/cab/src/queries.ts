/**
 * Edge REST data the cab screens share (react-query keeps one copy and refreshes it). Each answer
 * is also kept on the tablet (offline/db.ts): if the machine gateway cannot be reached, the screen
 * shows the last copy instead of an error (TRD §11.2 Offline). An answer the gateway did send,
 * even an error, is never replaced by an old copy.
 */
import { useQuery } from "@tanstack/react-query";

import { api, EdgeError } from "./api";
import { recall, remember } from "./offline/db";
import { useSession } from "./session";

export async function withCache<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  try {
    const value = await fetcher();
    void remember(key, value);
    return value;
  } catch (e) {
    if (e instanceof EdgeError) throw e;
    const kept = await recall<T>(key);
    if (kept) return kept.value;
    throw e;
  }
}

/** Today's plan for the signed-in operator; refreshed every 30 s, live numbers come over the socket. */
export function useShift() {
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  return useQuery({
    queryKey: ["shift", operatorId],
    queryFn: () => withCache(`shift:${operatorId}`, () => api.shift(operatorId!)),
    enabled: operatorId != null,
    refetchInterval: 30_000,
  });
}

/** Alert timings, the checklist and the languages; fixed for the life of the edge. */
export function useCabConfig() {
  return useQuery({
    queryKey: ["cab-config"],
    queryFn: () => withCache("cab-config", api.config),
    staleTime: Infinity,
  });
}

/** My Day, private to the signed-in operator (P-01): the edge refuses anyone else. */
export function useInsights(range: "shift" | "week") {
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  return useQuery({
    queryKey: ["insights", operatorId, range],
    queryFn: () => withCache(`insights:${operatorId}:${range}`, () => api.insights(operatorId!, range)),
    enabled: operatorId != null,
    refetchInterval: 60_000,
  });
}

/** The operator's recent reports, with whether each has reached the fleet yet. */
export function useReports() {
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  return useQuery({
    queryKey: ["reports", operatorId],
    queryFn: () => withCache(`reports:${operatorId}`, () => api.reports(operatorId!)),
    enabled: operatorId != null,
    refetchInterval: 15_000,
  });
}

/** The lesson catalogue, with which ones this operator has finished (kept for offline use). */
export function useLessons() {
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  return useQuery({
    queryKey: ["lessons", operatorId],
    queryFn: () => withCache(`lessons:${operatorId}`, () => api.lessons(operatorId!)),
    enabled: operatorId != null,
  });
}

/** Up to three lessons suggested by what the operator's machine has seen (F-LRN-02). */
export function useRecommended() {
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  return useQuery({
    queryKey: ["recommended", operatorId],
    queryFn: () => withCache(`recommended:${operatorId}`, () => api.recommended(operatorId!)),
    enabled: operatorId != null,
    refetchInterval: 60_000,
  });
}

/** One lesson's cards, quiz or drill scenes (kept on the tablet once opened). */
export function useLesson(lessonId: string | undefined) {
  return useQuery({
    queryKey: ["lesson", lessonId],
    queryFn: () => withCache(`lesson:${lessonId}`, () => api.lesson(lessonId!)),
    enabled: lessonId != null,
    staleTime: Infinity,
  });
}

/** Training progress, private to the signed-in operator (F-LRN-06). */
export function useProgress() {
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  return useQuery({
    queryKey: ["progress", operatorId],
    queryFn: () => withCache(`progress:${operatorId}`, () => api.progress(operatorId!)),
    enabled: operatorId != null,
  });
}

/** Instructor sessions at the site's training centre (F-LRN-05). */
export function useSlots() {
  return useQuery({ queryKey: ["slots"], queryFn: () => withCache("slots", api.slots) });
}
