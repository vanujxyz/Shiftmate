/**
 * A small Markdown reader for docs/EVAL.md: headings, paragraphs, bullet lists, tables, fenced
 * code, **bold** and `code`. HTML comments (the eval section markers) are skipped. Text is always
 * rendered as text, never as HTML, so nothing in the file can inject markup.
 */
import type { ReactNode } from "react";

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    out.push(
      tok.startsWith("**") ? (
        <strong key={`${key}-${i++}`}>{tok.slice(2, -2)}</strong>
      ) : (
        <code key={`${key}-${i++}`} className="sm-num bg-surface-sunk px-1">{tok.slice(1, -1)}</code>
      ),
    );
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const cells = (row: string) =>
  row
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/<!--[\s\S]*?-->/g, "").split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let i = 0;
  let n = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    const key = `b${n++}`;
    if (!line.trim()) {
      i++;
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1]!.length;
      const cls = ["text-con-display", "text-con-title", "text-con-heading", "text-con-label"][level - 1];
      const content = inline(h[2]!, key);
      blocks.push(
        level === 1 ? <h2 key={key} className={cls}>{content}</h2>
        : level === 2 ? <h3 key={key} className={`${cls} pt-4`}>{content}</h3>
        : <h4 key={key} className={`${cls} pt-2`}>{content}</h4>,
      );
      i++;
      continue;
    }
    if (line.startsWith("```")) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i]!.startsWith("```")) body.push(lines[i++]!);
      i++;
      blocks.push(<pre key={key} className="sm-num overflow-x-auto bg-surface-sunk p-3 text-con-meta">{body.join("\n")}</pre>);
      continue;
    }
    if (line.trim().startsWith("|")) {
      const rows: string[] = [];
      while (i < lines.length && lines[i]!.trim().startsWith("|")) rows.push(lines[i++]!);
      const [head, , ...body] = rows;
      blocks.push(
        <div key={key} className="overflow-x-auto">
          <table className="sm-rule w-full bg-surface text-left text-con-body">
            <thead>
              <tr className="sm-rule-b">
                {cells(head ?? "").map((c, j) => (
                  <th key={j} scope="col" className="px-3 py-2 text-con-label">{inline(c, `${key}h${j}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri} className="sm-rule-soft-b">
                  {cells(r).map((c, j) => (
                    <td key={j} className="sm-num px-3 py-1.5">{inline(c, `${key}r${ri}c${j}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i]!)) items.push(lines[i++]!.replace(/^\s*[-*]\s+/, ""));
      blocks.push(
        <ul key={key} className="flex list-disc flex-col gap-1 pl-6 text-con-body">
          {items.map((it, j) => (
            <li key={j}>{inline(it, `${key}l${j}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i]!.trim() &&
      !/^(#{1,4})\s|^```|^\s*\||^\s*[-*]\s+/.test(lines[i]!)
    ) {
      para.push(lines[i++]!.trim());
    }
    blocks.push(<p key={key} className="text-con-body">{inline(para.join(" "), key)}</p>);
  }
  return <div className="flex flex-col gap-3">{blocks}</div>;
}
