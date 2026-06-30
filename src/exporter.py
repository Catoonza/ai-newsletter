"""
Generates a responsive email newsletter using MJML compiled to HTML.
Redesigned with a fresh, tech-focused dark-mode aesthetic.
"""

import os
import re
import datetime
import smtplib
import shutil
import subprocess
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SECTION_MAP = [
    ("Model Releases",        "models",    "Model Releases & Provider Updates",  "§ 01"),
    ("Research Highlights",   "research",  "Research Highlights",                "§ 02"),
    ("AI in Business",        "industry",  "AI in Business & Industry",          "§ 03"),
    ("AI Tools",              "tools",     "AI Tools & Products",                "§ 04"),
    ("From the AI Community", "community", "From the AI Community",              "§ 05"),
    ("One to Watch",          "watch",     "One to Watch",                       "§ 06"),
]

# Tech Palette
BG_DARK       = "#0B0F19"
BG_CARD       = "#161B2E"
BG_INNER_CARD = "#0D1120"
BORDER_COLOR  = "#1E293B"
TEXT_LIGHT    = "#F3F4F6"
TEXT_MUTED    = "#9CA3AF"
TEXT_WHITE    = "#FFFFFF"

SECTION_ACCENTS = {
    "models": "#00F0FF",    # Cyan
    "research": "#A855F7",  # Purple
    "industry": "#3B82F6",  # Blue
    "tools": "#10B981",     # Green
    "community": "#F43F5E", # Rose
    "watch": "#F59E0B",     # Amber
}

# Shared overflow-safe text style (prevents content from extending past container)
_WRAP = "overflow-wrap:break-word;word-wrap:break-word;word-break:break-word;"
_TBL = "border-collapse:collapse;"


# ── Markdown inline → HTML/MJML ───────────────────────────────────

def _md(text: str) -> str:
    """Convert inline markdown to HTML with inline styles and classes."""
    # Links - neon cyan
    text = re.sub(
        r'\[(.+?)\]\((https?://[^\)]+)\)',
        r'<a href="\2" class="link-style" style="color:#00F0FF;text-decoration:none;">\1</a>',
        text
    )
    # Bold - pure white
    text = re.sub(
        r'\*\*(.+?)\*\*',
        r'<strong class="bld" style="font-weight:700;color:#FFFFFF;">\1</strong>',
        text
    )
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em style="font-style:italic;">\1</em>', text)
    return text


# ── Content extraction ────────────────────────────────────────────

def _bullets(lines: list) -> list:
    """Collect bullet lines from beneath a ### sub-heading."""
    result, past = [], False
    for line in lines:
        s = line.strip()
        if s.startswith("###"):
            past = True; continue
        if past and (s.startswith("- ") or s.startswith("* ") or re.match(r'^\d+\.\s', s)):
            result.append(s)
    return result


def _prose(lines: list) -> list:
    """Non-heading, non-bullet prose lines."""
    return [
        l.strip() for l in lines
        if not l.strip().startswith(("#", "- ", "* ")) and l.strip() != "---"
    ]


def _strip_urls_from_body(line: str) -> str:
    """Strip leading bullet/number prefix from a line."""
    line = line.strip()
    if line.startswith(("- ", "* ")):
        line = line[2:].strip()
    else:
        m = re.match(r'^\d+\.\s+', line)
        if m:
            line = line[m.end():].strip()
    return line


# ── MJML component builders ───────────────────────────────────────

def _compile_mjml(mjml_str: str) -> str:
    """Compile MJML markup to responsive HTML using the mjml CLI."""
    mjml_bin = shutil.which("mjml")
    if mjml_bin:
        cmd = [mjml_bin, "-i", "-s"]
    else:
        npx_bin = shutil.which("npx")
        if not npx_bin:
            raise RuntimeError("Neither 'mjml' nor 'npx' executable found in PATH. Please install Node.js/MJML.")
        cmd = [npx_bin, "mjml", "-i", "-s"]

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        stdout, stderr = process.communicate(input=mjml_str)
    except Exception as e:
        raise RuntimeError(f"Failed to start MJML compiler process: {e}")

    if process.returncode != 0:
        raise RuntimeError(f"MJML compilation failed (exit code {process.returncode}): {stderr}")
    
    return stdout


def _bullet_rows(bullets: list, accent_color: str) -> str:
    rows = []
    last = len(bullets) - 1
    for i, raw in enumerate(bullets):
        body = _strip_urls_from_body(raw)
        body_html = _md(body)
        border = "border-bottom:1px solid #1E293B;" if i < last else ""
        rows.append(
            f'<tr valign="top">'
            f'<td style="width:16px;padding:12px 6px 12px 0;{border}'
            f'font-family:Inter, sans-serif;font-size:13.5px;line-height:1.6;'
            f'color:{accent_color};font-weight:700;">—</td>'
            f'<td style="padding:12px 0;{border}font-family:Inter, sans-serif;'
            f'font-size:13.5px;line-height:1.6;color:#D1D5DB;{_WRAP}">'
            f'{body_html}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _qt_block(bullets: list, accent_color: str, label: str = "The Quick Take") -> str:
    if not bullets:
        return (
            f'<mj-text font-family="Inter, sans-serif" font-style="italic"'
            f' color="#9CA3AF" font-size="13px" padding="0px">No significant updates this week.</mj-text>'
        )
    rows_html = _bullet_rows(bullets, accent_color)
    return (
        f'<mj-table padding="0px">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" bgcolor="#0D1120" style="background:#0D1120;'
        f'border-left:3px solid {accent_color};border-radius:4px;{_TBL}">'
        f'<tr><td style="padding:16px 20px 14px 20px;">'
        f'<div style="font-family:\'JetBrains Mono\', monospace;font-size:9px;letter-spacing:0.15em;'
        f'text-transform:uppercase;color:{accent_color};margin-bottom:12px;">{label}</div>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" style="table-layout:fixed;{_TBL}">'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</td></tr></table>'
        f'</mj-table>'
    )


def _section_header(num: str, title: str, accent_color: str, html_id: str = None) -> str:
    prefix = f"// {num}" if num else "// UPDATE"
    anchor = f'<a name="{html_id}" id="{html_id}" style="display:block;height:0;line-height:0;font-size:0;">&nbsp;</a>' if html_id else ""
    return (
        f'<mj-text font-family="\'JetBrains Mono\', monospace" font-size="11px" color="{accent_color}" letter-spacing="0.15em" text-transform="uppercase" padding="0 0 6px 0">{anchor}{prefix}</mj-text>'
        f'<mj-text font-family="Inter, sans-serif" font-size="20px" font-weight="800" color="#FFFFFF" line-height="1.2" padding="0 0 16px 0">{title}</mj-text>'
    )


def _standard_section(html_id: str, num: str, title: str, lines: list, accent_color: str) -> str:
    bl    = _bullets(lines)
    label = "Notable Discussions This Week" if html_id == "community" else "The Quick Take"
    return (
        f'<mj-section padding="24px 24px 12px 24px" css-class="section-block">'
        f'<mj-column>'
        f'{_section_header(num, title, accent_color, html_id)}'
        f'{_qt_block(bl, accent_color, label)}'
        f'<mj-divider border-width="1px" border-color="#1E293B" padding="24px 0 0 0" />'
        f'</mj-column>'
        f'</mj-section>'
    )


def _one_to_watch(lines: list, accent_color: str = "#F59E0B") -> str:
    pr = _prose(lines)
    pgs, cur = [], []
    for l in pr:
        if l == "":
            if cur: pgs.append(" ".join(cur)); cur = []
        else:
            cur.append(l)
    if cur: pgs.append(" ".join(cur))

    paras = ""
    for p in pgs:
        if not p:
            continue
        paras += (
            f'<p style="font-family:Inter, sans-serif;font-size:14px;line-height:1.68;'
            f'color:#E5E7EB;margin:0 0 12px 0;{_WRAP}">'
            f'{_md(p)}</p>'
        )
    paras = re.sub(r'margin:0 0 12px 0;([^"]*?)"></p>$', r'margin:0;\1"></p>', paras)

    return (
        f'<mj-section padding="24px 24px 12px 24px" css-class="section-block">'
        f'<mj-column>'
        f'{_section_header("§ 06", "One to Watch", accent_color, "watch")}'
        f'<mj-table padding="0px">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" bgcolor="#0D1120" style="background:#0D1120;'
        f'border-left:3px solid {accent_color};border-radius:4px;{_TBL}">'
        f'<tr><td style="padding:20px 24px;">'
        f'<div style="font-family:\'JetBrains Mono\', monospace;font-size:9px;letter-spacing:0.15em;'
        f'text-transform:uppercase;color:{accent_color};margin-bottom:12px;">📌 &nbsp;Editor\'s Pick</div>'
        f'{paras}'
        f'</td></tr></table>'
        f'</mj-table>'
        f'<mj-divider border-width="1px" border-color="#1E293B" padding="24px 0 0 0" />'
        f'</mj-column>'
        f'</mj-section>'
    )


def _nav_bar() -> str:
    items = [
        ("🚀", "Models",    "#models",    "#00F0FF"),
        ("📚", "Research",  "#research",  "#A855F7"),
        ("🏢", "Industry",  "#industry",  "#3B82F6"),
        ("🛠", "Tools",     "#tools",     "#10B981"),
        ("🐦", "Community", "#community", "#F43F5E"),
        ("📌", "Watch",     "#watch",     "#F59E0B"),
    ]
    row1 = ""
    row2 = ""
    for i, (emoji, label, href, color) in enumerate(items):
        border_r = "border-right:1px solid #1E293B;" if (i % 3) < 2 else ""
        border_b = "border-bottom:1px solid #1E293B;" if i < 3 else ""
        cell = (
            f'<td width="33%" style="text-align:center;{border_r}{border_b}">'
            f'<a href="{href}" style="display:block;padding:12px 6px;'
            f'font-family:\'JetBrains Mono\', monospace;font-size:10px;letter-spacing:0.1em;'
            f'text-transform:uppercase;color:#9CA3AF;text-decoration:none;white-space:nowrap;">'
            f'<span style="color:{color};">{emoji}</span>&nbsp;{label}</a>'
            f'</td>'
        )
        if i < 3:
            row1 += cell
        else:
            row2 += cell
            
    return (
        f'<mj-section padding="0 24px 20px">'
        f'<mj-column background-color="#111827" border="1px solid #1E293B" padding="0px">'
        f'<mj-table padding="0px">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;">'
        f'<tr>{row1}</tr>'
        f'<tr>{row2}</tr>'
        f'</table>'
        f'</mj-table>'
        f'</mj-column>'
        f'</mj-section>'
    )


# ── Full MJML / HTML assembler ────────────────────────────────────

def _build_mjml(summary_html: str, sections_html: str,
                week_of: str, edition: str, next_ed: str) -> str:
    return f"""<mjml>
  <mj-head>
    <mj-title>AI Weekly — {week_of}</mj-title>
    <mj-font name="Inter" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" />
    <mj-font name="JetBrains Mono" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" />
    <mj-attributes>
      <mj-all font-family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" />
      <mj-text font-size="14px" color="{TEXT_LIGHT}" line-height="1.6" />
    </mj-attributes>
    <mj-style inline="inline">
      .tech-border {{
        border: 1px solid {BORDER_COLOR} !important;
      }}
      .link-style {{
        color: #00F0FF !important;
        text-decoration: none;
      }}
      .link-style:hover {{
        text-decoration: underline;
      }}
      .bld {{
        font-weight: 700;
        color: {TEXT_WHITE};
      }}
    </mj-style>
  </mj-head>
  <mj-body background-color="{BG_DARK}" width="680px">
    <mj-wrapper background-color="{BG_CARD}" border="1px solid {BORDER_COLOR}" padding="0px">
      
      <!-- ══ MASTHEAD ══════════════════════════════════════ -->
      <mj-section padding="32px 24px 20px" background-color="{BG_CARD}">
        <mj-column>
          <mj-text align="center" font-family="'JetBrains Mono', monospace" font-size="10px" letter-spacing="0.2em" color="{TEXT_MUTED}" text-transform="uppercase" padding="0px">
            // Independent AI Research Digest
          </mj-text>
          <mj-text align="center" font-family="Inter, sans-serif" font-weight="800" font-size="42px" color="{TEXT_WHITE}" letter-spacing="-1px" line-height="1.1" padding="10px 0">
            AI <span style="color:#00F0FF;">WEEKLY</span>
          </mj-text>
          <mj-divider border-width="1px" border-color="{BORDER_COLOR}" padding="10px 0" />
          <mj-table padding="0px" font-family="'JetBrains Mono', monospace" font-size="10px" color="{TEXT_MUTED}">
            <tr>
              <td style="text-align: left; width: 33%;">{edition}</td>
              <td style="text-align: center; width: 34%; font-style: italic;">WHAT HAPPENED IN AI THIS WEEK</td>
              <td style="text-align: right; width: 33%;">{week_of}</td>
            </tr>
          </mj-table>
        </mj-column>
      </mj-section>
      
      <!-- ══ SUMMARY BAR ═══════════════════════════════════ -->
      <mj-section padding="0 24px 20px">
        <mj-column background-color="{BG_INNER_CARD}" border-left="4px solid #A855F7" padding="16px 20px">
          <mj-text padding="0px" font-size="13.5px" line-height="1.6" color="{TEXT_LIGHT}">
            <strong style="color: #A855F7; font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.1em; display: block; margin-bottom: 6px; text-transform: uppercase;">⚡ THIS WEEK AT A GLANCE</strong>
            {summary_html}
          </mj-text>
        </mj-column>
      </mj-section>
      
      <!-- ══ NAV BAR ═══════════════════════════════════════ -->
      {_nav_bar()}
      
      <!-- ══ SECTIONS ══════════════════════════════════════ -->
      {sections_html}
      
      <!-- ══ FOOTER ════════════════════════════════════════ -->
      <mj-section padding="28px 24px" background-color="#111827">
        <mj-column>
          <mj-text align="center" font-family="'JetBrains Mono', monospace" font-size="10px" letter-spacing="0.1em" color="{TEXT_MUTED}" text-transform="uppercase" padding="0 0 10px 0">
            Next edition: <strong style="color: #00F0FF; font-weight: 700;">{next_ed}</strong>
          </mj-text>
          <mj-text align="center" font-family="Inter, sans-serif" font-size="11px" color="#6B7280" line-height="1.6" font-style="italic" padding="0px">
            AI Weekly is an independent digest. All summaries reflect publicly available reporting.<br />
            Not financial or investment advice.
          </mj-text>
        </mj-column>
      </mj-section>
      
    </mj-wrapper>
  </mj-body>
</mjml>"""


# ── Main parser ───────────────────────────────────────────────────

def markdown_to_mjml(md: str, date: datetime.datetime) -> str:
    lines      = md.splitlines()
    week_of    = date.strftime("Week of %b %d, %Y")
    next_ed    = (date + datetime.timedelta(days=7)).strftime("%B %d, %Y")
    edition_num = date.isocalendar()[1]
    edition    = f"Vol. 2026 · No. {edition_num}"

    # ── Extract summary ───────────────────────────────────────────
    summary_text, in_sum = "", False
    for line in lines:
        s = line.strip()
        if re.match(r'^##\s+This Week at a Glance', s, re.IGNORECASE):
            in_sum = True; continue
        if in_sum:
            if s.startswith("##"): break
            if s and not s.startswith("#") and s != "---":
                summary_text += s + " "
    summary_text = summary_text.strip()
    summary_html = (
        _md(summary_text)
        if summary_text else "Your weekly AI briefing."
    )

    # ── Split into ## sections ────────────────────────────────────
    raw_sections = []
    cur_h, cur_l = None, []
    for line in lines:
        s = line.strip()
        if re.match(r'^##\s+', s) and not s.startswith("###"):
            heading = re.sub(r'^##\s+', '', s)
            if cur_h is not None:
                raw_sections.append((cur_h, cur_l))
            cur_h, cur_l = heading, []
        elif cur_h is not None:
            cur_l.append(line)
    if cur_h is not None:
        raw_sections.append((cur_h, cur_l))

    # ── Render sections ───────────────────────────────────────────
    sections_mjml = ""
    for heading, content in raw_sections:
        if re.search(r'at a glance|next edition|independent newsletter|not financial', heading, re.IGNORECASE):
            continue
        if re.search(r'one to watch', heading, re.IGNORECASE):
            sections_mjml += _one_to_watch(content, SECTION_ACCENTS.get("watch", "#F59E0B"))
            continue
        matched = False
        for key, html_id, display_title, section_num in SECTION_MAP:
            if key.lower() in heading.lower():
                accent = SECTION_ACCENTS.get(html_id, "#00F0FF")
                sections_mjml += _standard_section(html_id, section_num, display_title, content, accent)
                matched = True
                break
        if not matched:
            bl = _bullets(content)
            safe_id = re.sub(r'[^a-z0-9]', '-', heading.lower())[:24].strip('-')
            clean_t = re.sub(r'[^\w\s&\-]', '', heading).strip()
            accent = "#00F0FF"
            sections_mjml += (
                f'<mj-section padding="24px 24px 12px 24px" css-class="section-block">'
                f'<mj-column>'
                f'{_section_header("", clean_t, accent, safe_id)}'
                f'{_qt_block(bl, accent)}'
                f'<mj-divider border-width="1px" border-color="#1E293B" padding="24px 0 0 0" />'
                f'</mj-column>'
                f'</mj-section>'
            )

    return _build_mjml(summary_html, sections_mjml, week_of, edition, next_ed)


def markdown_to_html(md: str, date: datetime.datetime) -> str:
    mjml_content = markdown_to_mjml(md, date)
    return _compile_mjml(mjml_content)


# ── Save & email ──────────────────────────────────────────────────

def save_newsletter(newsletter_md: str, date: datetime.datetime) -> str:
    os.makedirs("output", exist_ok=True)

    md_path = f"output/ai-weekly-{date.strftime('%Y-%m-%d')}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(newsletter_md)

    mjml = markdown_to_mjml(newsletter_md, date)
    mjml_path = f"output/ai-weekly-{date.strftime('%Y-%m-%d')}.mjml"
    with open(mjml_path, "w", encoding="utf-8") as f:
        f.write(mjml)

    html = _compile_mjml(mjml)
    html_path = f"output/ai-weekly-{date.strftime('%Y-%m-%d')}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    _maybe_send_email(newsletter_md, html, date)
    return md_path


def _maybe_send_email(newsletter_md: str, newsletter_html: str, date: datetime.datetime):
    smtp_from     = os.environ.get("SMTP_FROM")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_to       = os.environ.get("SMTP_TO")

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
