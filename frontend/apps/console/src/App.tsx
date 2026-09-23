/**
 * The supervisor console (TRD §11.3): live site map, day summary, fleet, demo control and the
 * evaluation page, inside one frame. `/_kitchen-sink` shows every design-system component.
 */
import { Navigate, Route, Routes } from "react-router";

import { KitchenSink } from "./KitchenSink";
import { Demo } from "./screens/Demo";
import { Eval } from "./screens/Eval";
import { Fleet } from "./screens/Fleet";
import { SiteMap } from "./screens/SiteMap";
import { Supervisor } from "./screens/Supervisor";
import { ConsoleShell, useDefaultSite } from "./shell/ConsoleShell";

function Home() {
  const site = useDefaultSite();
  return <Navigate to={`/site/${site}`} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/_kitchen-sink" element={<KitchenSink />} />
      <Route element={<ConsoleShell />}>
        <Route index element={<Home />} />
        <Route path="site/:siteId" element={<SiteMap />} />
        <Route path="supervisor/:siteId" element={<Supervisor />} />
        <Route path="fleet" element={<Fleet />} />
        <Route path="demo" element={<Demo />} />
        <Route path="eval" element={<Eval />} />
        <Route path="*" element={<Home />} />
      </Route>
    </Routes>
  );
}
