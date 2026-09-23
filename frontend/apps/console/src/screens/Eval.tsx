/**
 * Evaluation (TRD §11.3 /eval, §12): docs/EVAL.md as written by `shiftmate eval all`, read at
 * build time. Nothing on this page is typed in by hand; re-run the evaluation and rebuild to
 * update it (golden rule 11).
 */
import { useTranslation } from "react-i18next";

import evalMd from "../../../../../docs/EVAL.md?raw";
import { Markdown } from "../lib/markdown";

export function Eval() {
  const { t } = useTranslation();
  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <h1 className="text-con-title">{t("ui.ev.title")}</h1>
      <p className="text-con-meta text-ink-2">{t("ui.ev.source")}</p>
      <div lang="en">
        <Markdown source={evalMd} />
      </div>
    </div>
  );
}
