/**
 * The cab app (TRD §10.1): /start signs in; everything else lives inside the cab frame.
 * The operator's language and theme are applied to the document so every screen follows them.
 */
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router";

import { Ask } from "./screens/Ask";
import { MyDay } from "./screens/MyDay";
import { MyShift } from "./screens/MyShift";
import { Report } from "./screens/Report";
import { Safety } from "./screens/Safety";
import { Start } from "./screens/Start";
import { useSession } from "./session";
import { Booking } from "./screens/learn/Booking";
import { Learn } from "./screens/learn/Learn";
import { LessonPlayer } from "./screens/learn/LessonPlayer";
import { Progress } from "./screens/learn/Progress";
import { CabShell } from "./shell/CabShell";

export function App() {
  const { i18n } = useTranslation();
  const language = useSession((s) => s.language);
  const theme = useSession((s) => s.theme);

  useEffect(() => {
    if (i18n.language !== language) void i18n.changeLanguage(language);
    document.documentElement.lang = language;
  }, [i18n, language]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <Routes>
      <Route path="/start" element={<Start />} />
      <Route element={<CabShell />}>
        <Route index element={<MyShift />} />
        <Route path="safety" element={<Safety />} />
        <Route path="report" element={<Report />} />
        <Route path="insights" element={<MyDay />} />
        <Route path="learn" element={<Learn />} />
        <Route path="learn/book" element={<Booking />} />
        <Route path="learn/progress" element={<Progress />} />
        <Route path="learn/:lessonId" element={<LessonPlayer />} />
        <Route path="ask" element={<Ask />} />
        <Route path="*" element={<MyShift />} />
      </Route>
    </Routes>
  );
}
