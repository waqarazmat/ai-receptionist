// Lightweight markdown → HTML for bot messages.
// Ported from the original GenAITech widget.js renderMarkdown function.

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function inline(s: string): string {
  s = esc(s);
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*(.+?)\*/g, "<em>$1</em>");
  s = s.replace(/`(.+?)`/g, "<code>$1</code>");
  s = s.replace(
    /(\bhttps?:\/\/[^\s<"]+)/g,
    (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`,
  );
  return s;
}

export function renderMarkdown(raw: string): string {
  if (!raw) return "";

  const lines = raw.split("\n");
  const out: string[] = [];
  let inUl = false;
  let inOl = false;

  const closeList = () => {
    if (inUl) { out.push("</ul>"); inUl = false; }
    if (inOl) { out.push("</ol>"); inOl = false; }
  };

  for (const line of lines) {
    let m: RegExpMatchArray | null;

    if ((m = line.match(/^### (.+)/))) { closeList(); out.push(`<h4>${inline(m[1]!)}</h4>`); continue; }
    if ((m = line.match(/^## (.+)/)))  { closeList(); out.push(`<h3>${inline(m[1]!)}</h3>`); continue; }
    if ((m = line.match(/^# (.+)/)))   { closeList(); out.push(`<h2>${inline(m[1]!)}</h2>`); continue; }
    if (/^---+$/.test(line.trim()))    { closeList(); out.push("<hr>"); continue; }

    if ((m = line.match(/^[-•→*] (.+)/))) {
      if (inOl) { out.push("</ol>"); inOl = false; }
      if (!inUl) { out.push("<ul>"); inUl = true; }
      out.push(`<li>${inline(m[1]!)}</li>`);
      continue;
    }

    if ((m = line.match(/^\d+\. (.+)/))) {
      if (inUl) { out.push("</ul>"); inUl = false; }
      if (!inOl) { out.push("<ol>"); inOl = true; }
      out.push(`<li>${inline(m[1]!)}</li>`);
      continue;
    }

    if (line.trim() === "") { closeList(); out.push('<div style="height:6px"></div>'); continue; }

    closeList();
    out.push(`<p class="md-p">${inline(line)}</p>`);
  }

  closeList();
  return out.join("");
}
