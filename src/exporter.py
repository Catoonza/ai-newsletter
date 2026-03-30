"""
Converts Claude's Markdown newsletter into the branded HTML template
and sends it via email.

The Markdown output from summariser.py follows this structure:
  ## This Week at a Glance        → summary bar
  ## 🚀 Model Releases...         → section with ### The Quick Take bullets
  ## 📚 Research Highlights       → section with ### The Quick Take bullets
  ## 🏢 AI in Business...         → section with ### The Quick Take bullets
  ## 🛠️ AI Tools...               → section with ### The Quick Take bullets
  ## 🐦 From the AI Community     → section with ### Notable Discussions bullets
  ## 📌 One to Watch              → inverted black block, plain prose
"""

import os
import re
import datetime
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# Maps heading fragments → (html_id, display_title, section_number)
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
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


# ── Extract bullet lines from a section's content ─────────────────

def _extract_bullets(content_lines: list[str]) -> list[str]:
    """
    Returns bullet lines from content, skipping ### sub-headings.
    Collects everything after any ### heading (Quick Take, Notable Discussions, etc.)
    """
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
    """
    Returns non-bullet, non-heading prose lines from content.
    Used for One to Watch and any section without bullet structure.
    """
    prose = []
    for line in content_lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            continue
        prose.append(stripped)
    return prose


# ── Component renderers ───────────────────────────────────────────

def _render_bullet_block(bullets: list[str], label: str = "The Quick Take") -> str:
    if not bullets:
        return ""
    items_html = ""
    for line in bullets:
        content = _md_inline(line[2:].strip())  # strip "- " or "* "
        items_html += f"    <li>{content}</li>\n"
    return f"""
<div class="quick-take">
  <div class="quick-take-label">{label}</div>
  <ul>
{items_html}  </ul>
</div>"""


def _render_one_to_watch(content_lines: list[str]) -> str:
    """One to Watch: inverted black block with prose."""
    prose_lines = _extract_prose(content_lines)
    # Merge into paragraphs on blank-line boundaries
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
    return f"""
<div class="section" id="watch">
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
    # Determine label — community section uses "Notable Discussions"
    label = "Notable Discussions This Week" if html_id == "community" else "The Quick Take"
    bullet_html = _render_bullet_block(bullets, label)

    return f"""
<div class="section" id="{html_id}">
  <div class="section-header">
    <div class="section-label">{section_num}</div>
    <div class="section-title">{title}</div>
    <div class="section-rule"></div>
  </div>
  {bullet_html}
</div>"""


# ── Main parser ───────────────────────────────────────────────────

def markdown_to_html(md: str, date: datetime.datetime) -> str:
    lines = md.splitlines()
    week_of = date.strftime("Week of %b %d, %Y")
    next_edition = (date + datetime.timedelta(days=7)).strftime("%B %d, %Y")

    # ── Extract "This Week at a Glance" for the summary bar ───────
    summary_text = ""
    in_summary = False
    for line in lines:
        stripped = line.strip()
        if re.match(r'^##\s+This Week at a Glance', stripped, re.IGNORECASE):
            in_summary = True
            continue
        if in_summary:
            if stripped.startswith("##"):
                break
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                summary_text += stripped + " "

    summary_text = summary_text.strip()
    summary_html = (
        f"<strong>This week:</strong> {_md_inline(summary_text)}"
        if summary_text else ""
    )

    # ── Split into top-level ## sections ──────────────────────────
    raw_sections: list[tuple[str, list[str]]] = []
    current_heading, current_lines = None, []

    for line in lines:
        stripped = line.strip()
        if re.match(r'^##\s+', stripped) and not stripped.startswith("###"):
            heading = re.sub(r'^##\s+', '', stripped)
            if current_heading is not None:
                raw_sections.append((current_heading, current_lines))
            current_heading = heading
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        raw_sections.append((current_heading, current_lines))

    # ── Render each section ───────────────────────────────────────
    sections_html = ""

    for heading, content in raw_sections:
        # Skip — already rendered as summary bar
        if re.search(r'at a glance', heading, re.IGNORECASE):
            continue
        # Skip footer noise
        if re.search(r'next edition', heading, re.IGNORECASE):
            continue
        # One to Watch — special inverted block
        if re.search(r'one to watch', heading, re.IGNORECASE):
            sections_html += _render_one_to_watch(content)
            continue

        # Match to known sections
        matched = False
        for key, html_id, display_title, section_num in SECTION_MAP:
            if key.lower() in heading.lower():
                sections_html += _render_standard_section(
                    html_id, section_num, display_title, content
                )
                matched = True
                break

        if not matched:
            # Fallback for any unexpected section
            bullets = _extract_bullets(content)
            bullet_html = _render_bullet_block(bullets)
            safe_id = re.sub(r'[^a-z0-9]', '-', heading.lower())[:20]
            clean_title = re.sub(r'[^\w\s&]', '', heading).strip()
            sections_html += f"""
<div class="section" id="{safe_id}">
  <div class="section-header">
    <div class="section-title">{clean_title}</div>
    <div class="section-rule"></div>
  </div>
  {bullet_html}
</div>"""

    # ── Populate template ─────────────────────────────────────────
    template_path = Path(__file__).parent / "template" / "newsletter.html"
    template = template_path.read_text(encoding="utf-8")

    edition_num = date.isocalendar()[1]
    html = template
    html = html.replace("{{WEEK_OF}}", week_of)
    html = html.replace("{{EDITION}}", f"Vol. 2026 &nbsp;·&nbsp; No. {edition_num}")
    html = html.replace("{{SUMMARY}}", summary_html)
    html = html.replace("{{SECTIONS}}", sections_html)
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
    smtp_from = os.environ.get("SMTP_FROM")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_to = os.environ.get("SMTP_TO")

    if not all([smtp_from, smtp_password, smtp_to]):
        print("   ℹ️  Email not configured — newsletter saved to file only")
        return

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    week_str = date.strftime("%B %d, %Y")
    subject = f"🤖 AI Weekly — Week of {week_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = smtp_to

    msg.attach(MIMEText(newsletter_md, "plain"))
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
