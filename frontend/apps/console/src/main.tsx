import { createI18n } from "@shiftmate/i18n";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { I18nextProvider } from "react-i18next";
import { BrowserRouter, Route, Routes } from "react-router";

import { App } from "./App";
import { KitchenSink } from "./KitchenSink";
import "./index.css";

const queryClient = new QueryClient();
const i18n = createI18n("en");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <BrowserRouter>
          <Routes>
            <Route path="/_kitchen-sink" element={<KitchenSink />} />
            <Route path="*" element={<App />} />
          </Routes>
        </BrowserRouter>
      </I18nextProvider>
    </QueryClientProvider>
  </StrictMode>,
);
