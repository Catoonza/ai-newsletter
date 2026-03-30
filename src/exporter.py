"""
Converts Claude's Markdown newsletter into the branded HTML template
and sends it via email.

Section structure expected from summariser.py:
  ## This Week at a Glance        → summary bar
  ## 🚀 Model Releases...         → #models
  ## 📚 Research Highlights       → #research
  ## 🏢 AI in Business...         → #industry
  ## 🛠️ AI Tools...               → #tools
  ## 🐦 From the AI Community     → #community
  ## 📌 One to Watch              → #watch  (inverted block)
"""

import os
import re
import datetime
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# Maps heading fragment → (html_id, display_title, section_number)
# html_id MUST match the href in the nav links in newsletter.html
SECTION_MAP = [
    ("Model Releases",        "models",    "Model Releases & Provider Updates",  "§ 01"),
    ("Research Highlights",   "research",  "Research Highlights",                "§ 02"),
    ("AI in Business",        "industry",  "AI in Business & Industry",          "§ 03"),
    ("AI Tools",              "tools",     "AI Tools & Products",                "§ 04"),
    ("From the AI Community", "community", "From the AI Community",              "§ 05"),
    ("One to Watch",          "watch",     "One to Watch",                       "§ 06"),
]


# ── Inline markdown → HTML ────────────────────────────────────────

def _md_inline(text: str) -> str:
    """Convert inline markdown to HTML, preserving source links."""
    # Links → <a> (must come before bold/italic to avoid mangling brackets)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


def _extract_source_link(text: str) -> tuple[str, str]:
    """
    Pull the LAST markdown link from a bullet text and return
    (text_without_link, source_html).  If no link, returns (text, "").
    """
    matches = list(re.finditer(r'\[(.+?)\]\((.+?)\)', text))
    if not matches:
        # Also handle bare URLs at end of line
        bare = re.search(r'https?://\S+$', text.strip())
        if bare:
            url = bare.group(0).rstrip('.,)')
            clean = text[:bare.start()].strip()
            domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
            return clean, f'<a class="source-link" href="{url}">{domain} ↗</a>'
        return text, ""

    # Use the last link as the source attribution
    last = matches[-1]
    url = last.group(2)
    # Remove that link from the text
    clean = text[:last.start()].rstrip(' —–') + text[last.end():]
    clean = clean.strip()
    domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
    return clean, f'<a class="source-link" href="{url}">{domain} ↗</a>'


# ── Section content extraction ────────────────────────────────────

def _extract_bullets(content_lines: list[str]) -> list[str]:
    """Return bullet lines from beneath any ### sub-heading."""
    bullets = []
    past_subheading = False
    for line in content_lines:
        stripped = line.strip()
        if stripped.startswith("###"):
            past_subheading = True
            continue
        if past_subheading and (stripped.startswith("- ") or stripped.startswith("* ")):
            bullets.append(stripped)
    return bullets


def _extract_prose(content_lines: list[str]) -> list[str]:
    """Return non-heading, non-bullet prose lines."""
    prose = []
    for line in content_lines:
        s = line.strip()
        if s.startswith("#") or s.startswith("- ") or s.startswith("* ") or s == "---":
            continue
        prose.append(s)
    return prose


# ── Component renderers ───────────────────────────────────────────

def _render_bullet_block(bullets: list[str], label: str = "The Quick Take") -> str:
    if not bullets:
        return '<p style="color:var(--text-muted);font-style:italic;font-size:13px;">No significant updates this week.</p>'

    items_html = ""
    for raw in bullets:
        line = raw[2:].strip()           # strip leading "- " or "* "
        body, source_html = _extract_source_link(line)
        body_html = _md_inline(body)
        items_html += f"    <li>{body_html}{source_html}</li>\n"

    return f"""<div class="quick-take">
  <div class="quick-take-label">{label}</div>
  <ul>
{items_html}  </ul>
</div>"""


def _render_one_to_watch(content_lines: list[str]) -> str:
    prose_lines = _extract_prose(content_lines)
    paragraphs, current = [], []
    for line in prose_lines:
        if line == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))

    paras_html = "\n  ".join(
        f"<p>{_md_inline(p)}</p>" for p in paragraphs if p
    )
    return f"""<div class="section" id="watch">
  <div class="section-header">
    <div class="section-label">§ 06</div>
    <div class="section-title">One to Watch</div>
    <div class="section-rule"></div>
  </div>
  <div class="one-to-watch">
    <div class="one-to-watch-label">📌 &nbsp;Editor's Pick</div>
    {paras_html}
  </div>
</div>"""


def _render_standard_section(html_id: str, section_num: str,
                               title: str, content_lines: list[str]) -> str:
    bullets = _extract_bullets(content_lines)
    label = "Notable Discussions This Week" if html_id == "community" else "The Quick Take"
    bullet_html = _render_bullet_block(bullets, label)

    return f"""<div class="section" id="{html_id}">
  <div class="section-header">
    <div class="section-label">{section_num}</div>
    <div class="section-title">{title}</div>
    <div class="section-rule"></div>
  </div>
  {bullet_html}
</div>"""


# ── Main Markdown → HTML parser ───────────────────────────────────

def markdown_to_html(md: str, date: datetime.datetime) -> str:
    lines = md.splitlines()
    week_of = date.strftime("Week of %b %d, %Y")
    next_edition = (date + datetime.timedelta(days=7)).strftime("%B %d, %Y")
    edition_num = date.isocalendar()[1]

    # ── Extract summary from "This Week at a Glance" ──────────────
    summary_text = ""
    in_summary = False
    for line in lines:
        s = line.strip()
        if re.match(r'^##\s+This Week at a Glance', s, re.IGNORECASE):
            in_summary = True
            continue
        if in_summary:
            if s.startswith("##"):
                break
            if s and not s.startswith("#") and s != "---":
                summary_text += s + " "

    summary_text = summary_text.strip()
    summary_html = (
        f"<strong>This week:</strong> {_md_inline(summary_text)}"
        if summary_text else "Your weekly briefing on what's happening in AI."
    )

    # ── Split into ## top-level sections ──────────────────────────
    raw_sections: list[tuple[str, list[str]]] = []
    cur_heading, cur_lines = None, []

    for line in lines:
        s = line.strip()
        if re.match(r'^##\s+', s) and not s.startswith("###"):
            heading = re.sub(r'^##\s+', '', s)
            if cur_heading is not None:
                raw_sections.append((cur_heading, cur_lines))
            cur_heading = heading
            cur_lines = []
        elif cur_heading is not None:
            cur_lines.append(line)

    if cur_heading is not None:
        raw_sections.append((cur_heading, cur_lines))

    # ── Render each section ───────────────────────────────────────
    sections_html = ""

    for heading, content in raw_sections:
        # Skip — already used in summary bar
        if re.search(r'at a glance', heading, re.IGNORECASE):
            continue
        # Skip footer artefacts
        if re.search(r'next edition|independent newsletter|not financial', heading, re.IGNORECASE):
            continue
        # One to Watch — inverted dark block
        if re.search(r'one to watch', heading, re.IGNORECASE):
            sections_html += _render_one_to_watch(content) + "\n"
            continue

        # Match to known section map
        matched = False
        for key, html_id, display_title, section_num in SECTION_MAP:
            if key.lower() in heading.lower():
                sections_html += _render_standard_section(
                    html_id, section_num, display_title, content
                ) + "\n"
                matched = True
                break

        if not matched:
            # Generic fallback
            bullets = _extract_bullets(content)
            safe_id = re.sub(r'[^a-z0-9]', '-', heading.lower())[:24].strip('-')
            clean_title = re.sub(r'[^\w\s&\-]', '', heading).strip()
            sections_html += f"""<div class="section" id="{safe_id}">
  <div class="section-header">
    <div class="section-title">{clean_title}</div>
    <div class="section-rule"></div>
  </div>
  {_render_bullet_block(bullets)}
</div>\n"""

    # ── Load template and substitute placeholders ─────────────────
    template_path = Path(__file__).parent / "template" / "newsletter.html"
    html = template_path.read_text(encoding="utf-8")

    html = html.replace("{{WEEK_OF}}",     week_of)
    html = html.replace("{{EDITION}}",     f"Vol. 2026 · No. {edition_num}")
    html = html.replace("{{SUMMARY}}",     summary_html)
    html = html.replace("{{SECTIONS}}",    sections_html)
    html = html.replace("{{NEXT_EDITION}}", next_edition)

    return html


# ── Save & email ──────────────────────────────────────────────────

def save_newsletter(newsletter_md: str, date: datetime.datetime) -> str:
    os.makedirs("output", exist_ok=True)

    md_path = f"output/ai-weekly-{date.strftime('%Y-%m-%d')}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(newsletter_md)

    html = markdown_to_html(newsletter_md, date)

    html_path = f"output/ai-weekly-{date.strftime('%Y-%m-%d')}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    _maybe_send_email(newsletter_md, html, date)
    return md_path


def _maybe_send_email(newsletter_md: str, newsletter_html: str, date: datetime.datetime):
    smtp_from    = os.environ.get("SMTP_FROM")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_to      = os.environ.get("SMTP_TO")

    if not all([smtp_from, smtp_password, smtp_to]):
        print("   ℹ️  Email not configured — newsletter saved to file only")
        return

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    week_str = date.strftime("%B %d, %Y")
    subject  = f"🤖 AI Weekly — Week of {week_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_from
    msg["To"]      = smtp_to

    msg.attach(MIMEText(newsletter_md,   "plain"))
    msg.attach(MIMEText(newsletter_html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_from, smtp_password)
            server.sendmail(smtp_from, smtp_to, msg.as_string())
        print(f"   ✉️  Newsletter emailed to {smtp_to}")
    except Exception as e:
        print(f"   ⚠️  Email failed: {e}")
