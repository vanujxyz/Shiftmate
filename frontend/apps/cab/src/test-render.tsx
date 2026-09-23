/** Render the cab app (or one screen) the way main.tsx does, on a chosen route, with a fake edge. */
import { createI18n } from "@shiftmate/i18n";
import type { Language } from "@shiftmate/contracts";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

type Route = (url: string, init?: RequestInit) => unknown;

/** Stub fetch: `routes` maps a path prefix to a JSON body (or a function, or an Error status). */
export function fakeEdge(routes: Record<string, unknown | Route>) {
  const calls: { url: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input).replace(/^https?:\/\/[^/]+/, "");
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const key = Object.keys(routes)
      .filter((k) => url.startsWith(k))
      .sort((a, b) => b.length - a.length)[0];
    if (!key) return new Response(JSON.stringify({ error: { message: "not found" } }), { status: 404 });
    const value = routes[key];
    const body = typeof value === "function" ? (value as Route)(url, init) : value;
    if (body instanceof Response) return body;
    return new Response(JSON.stringify(body), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

export function renderAt(ui: ReactNode, path = "/", language: Language = "en") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nextProvider i18n={createI18n(language)}>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}
