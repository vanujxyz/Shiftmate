/** Edge REST data the cab screens share (react-query keeps one copy and refreshes it). */
import { useQuery } from "@tanstack/react-query";

import { api } from "./api";
import { useSession } from "./session";

/** Today's plan for the signed-in operator; refreshed every 30 s, live numbers come over the socket. */
export function useShift() {
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  return useQuery({
    queryKey: ["shift", operatorId],
    queryFn: () => api.shift(operatorId!),
    enabled: operatorId != null,
    refetchInterval: 30_000,
  });
}

/** Alert timings, the checklist and the languages; fixed for the life of the edge. */
export function useCabConfig() {
  return useQuery({ queryKey: ["cab-config"], queryFn: api.config, staleTime: Infinity });
}
