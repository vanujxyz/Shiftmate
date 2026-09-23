import { createI18n } from "@shiftmate/i18n";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nextProvider i18n={createI18n("en")}>
        <App />
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("cab placeholder", () => {
  it("says when the edge service is not reachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    renderApp();
    expect(await screen.findByText("Machine gateway not reachable yet")).toBeInTheDocument();
  });

  it("says when the edge service answers", async () => {
    const body = { service: "edge", status: "ok", version: "0.1.0" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    renderApp();
    expect(await screen.findByText("Connected to the machine gateway")).toBeInTheDocument();
  });

  it("switches language to Tamil", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "தமிழ்" }));
    expect(await screen.findByText("கேபின் செயலி உருவாக்கப்பட்டு வருகிறது. இப்போது இங்கே செய்ய எதுவும் இல்லை.")).toBeInTheDocument();
  });
});
