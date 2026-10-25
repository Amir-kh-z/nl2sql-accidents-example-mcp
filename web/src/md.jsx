import React from "react";

// The Layer-0 markdown subset the envelope emits: single-`#` headings, `- ` bullets, one paragraph per line,
// **bold**, *italic*, `code`. No tables, links or fences (the contract test forbids them), so nothing else is parsed.
// React escapes every text node — no innerHTML anywhere.

const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
// a Latin run (an English `detail`, a SQL fragment, a key) inside a Hebrew line: isolated, so the bidi algorithm
// cannot move its punctuation to the other end of the line
const LATIN = /([A-Za-z][A-Za-z0-9_ .,:;'"/()<>=\-]*[A-Za-z0-9)])/g;
// .test() on a /g regex is stateful (lastIndex persists across calls — the isolation became nondeterministic);
// test with an anchored, non-global copy instead
const LATIN_ONE = new RegExp(`^${LATIN.source}$`);

function latin(text, keyBase) {
  return String(text).split(LATIN).filter((p) => p !== "").map((p, i) =>
    LATIN_ONE.test(p) && /^[A-Za-z]/.test(p) && p.length > 3
      ? <bdi key={`${keyBase}-${i}`} className="ltr">{p}</bdi>
      : <React.Fragment key={`${keyBase}-${i}`}>{p}</React.Fragment>);
}

export function inline(text) {
  const parts = String(text).split(INLINE).filter((p) => p !== "");
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`")) return <code key={i} className="ltr">{p.slice(1, -1)}</code>;
    if (p.startsWith("*") && p.endsWith("*") && p.length > 2) return <em key={i}>{p.slice(1, -1)}</em>;
    return <React.Fragment key={i}>{latin(p, i)}</React.Fragment>;
  });
}

/** The three card shapes, by their first line. */
export function shapeOf(text) {
  const first = String(text || "").split("\n")[0];
  if (first.startsWith("# ❌")) return "refusal";
  if (first.startsWith("# 🧭")) return "route";
  if (first.startsWith("מכנה:")) return "answer";
  return "plain";
}

/** Render the markdown lines; `- פעולה מתאימה: X` bullets become route buttons when onRoute is given. */
export function renderMarkdown(text, { onRoute } = {}) {
  const lines = String(text || "").split("\n");
  const out = [];
  let list = [];
  const flush = () => {
    if (list.length) {
      out.push(<ul key={`ul-${out.length}`}>{list}</ul>);
      list = [];
    }
  };
  lines.forEach((line, i) => {
    if (line.startsWith("- ")) {
      const body = line.slice(2);
      const m = body.match(/^פעולה מתאימה: ([a-z_]+)$/);
      if (m && onRoute) {
        list.push(
          <li key={i} className="route-item">
            <span>פעולה מתאימה: </span>
            <button type="button" className="route-btn ltr" onClick={() => onRoute(m[1])}>{m[1]} ←</button>
          </li>,
        );
      } else {
        list.push(<li key={i}>{inline(body)}</li>);
      }
      return;
    }
    flush();
    if (line.startsWith("# ")) {
      out.push(<h3 key={i}>{inline(line.slice(2))}</h3>);
    } else if (line.trim() === "") {
      /* skip */
    } else {
      out.push(<p key={i}>{inline(line)}</p>);
    }
  });
  flush();
  return out;
}
