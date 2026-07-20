"""Down-convert the LLM's Markdown output to WhatsApp's own formatting.

The AI pipeline is shared across channels and emits Markdown (the web widget
renders it properly). WhatsApp does NOT render Markdown — it has its own scheme —
so on this channel `**bold**`, `## headings`, and `[label](url)` links would
show up literally. This converts Markdown → WhatsApp before sending.

WhatsApp text formatting (Meta): *bold*, _italic_, ~strikethrough~,
```monospace```. There is no link syntax — a bare URL auto-links — and no
headings or `**`.
"""

import re

# [label](url) and ![alt](url) — the image form is handled first so the "!" is
# consumed. Only http(s) URLs, to avoid mangling stray brackets.
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")

# **bold** / __bold__  →  *bold* (WhatsApp bold is a single asterisk).
_MD_BOLD_STARS = re.compile(r"\*\*([^*\n]+)\*\*")
_MD_BOLD_UNDERSCORES = re.compile(r"__([^_\n]+)__")

# Leading "# " … "###### " heading markers.
_MD_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.*)$", re.MULTILINE)

# Bullet markers "- " / "* " / "+ " at the start of a line → "• ".
_MD_BULLET = re.compile(r"^([ \t]*)[-*+][ \t]+", re.MULTILINE)

# `inline code` — single backticks aren't monospace on WhatsApp, so drop them.
_MD_INLINE_CODE = re.compile(r"`([^`\n]+)`")


def _link_sub(match: re.Match) -> str:
    label = match.group(1).strip()
    url = match.group(2)
    # Bare URL if the label adds nothing; otherwise "label: url" so the visible
    # text is kept and the URL still auto-links.
    if not label or label == url:
        return url
    return f"{label}: {url}"


def to_whatsapp_text(text: str) -> str:
    """Best-effort Markdown → WhatsApp formatting. Safe on plain text."""
    if not text:
        return text

    text = _MD_IMAGE.sub(lambda m: m.group(1) or m.group(2), text)
    text = _MD_LINK.sub(_link_sub, text)
    # Bold before headings so a "## **Foo**" doesn't end up double-starred.
    text = _MD_BOLD_STARS.sub(r"*\1*", text)
    text = _MD_BOLD_UNDERSCORES.sub(r"*\1*", text)
    # Heading line → bold line; strip any stray surrounding * from the content.
    text = _MD_HEADING.sub(lambda m: f"*{m.group(1).strip().strip('*')}*" if m.group(1).strip() else "", text)
    text = _MD_BULLET.sub(lambda m: f"{m.group(1)}• ", text)
    text = _MD_INLINE_CODE.sub(r"\1", text)
    return text
