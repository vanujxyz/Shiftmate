/** Render the console on a route with a fake gateway and fleet service (fetch stubbed by path). */
import { createI18n } from "@shiftmate/i18n";
import type { Language } from "@shiftmate/contracts";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

type Handler = (url: string, init?: RequestInit) => unknown;

export function fakeServices(routes: Record<string, unknown | Handler>) {
  const calls: { url: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = String(input).replace(/^https?:\/\/[^/]+/, "");
      calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const key = Object.keys(routes)
        .filter((k) => url.startsWith(k))
        .sort((a, b) => b.length - a.length)[0];
      if (!key) return new Response(JSON.stringify({ error: { message: "not found" } }), { status: 404 });
      const v = routes[key];
      const body = typeof v === "function" ? (v as Handler)(url, init) : v;
      return body instanceof Response ? body : new Response(JSON.stringify(body), { status: 200 });
    }),
  );
  return calls;
}

export function renderAt(ui: ReactNode, path: string, language: Language = "en") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nextProvider i18n={createI18n(language)}>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}
