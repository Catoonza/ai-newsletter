"""
Generates a fully inline-styled HTML email newsletter.

Email clients (Gmail, Apple Mail, Outlook) strip <style> blocks.
Every visible element here has styles applied as inline style="" attributes,
so the design survives any email client's CSS sanitiser.

The only <style> block included is a minimal one for hover states and
dark mode — these cannot be inlined, but all elements look correct
without them as fallback.
"""

import os
import re
import datetime
import smtplib
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

# Palette — hardcoded, no CSS variables (email clients don't support them)
PAPER      = "#faf8f4"
WARM       = "#f2efe9"
OUTER      = "#e8e4dc"
INK        = "#0f0f0f"
INK_MID    = "#3a3a3a"
INK_SOFT   = "#5a5a5a"
INK_FAINT  = "#909090"
ON_DARK    = "#f0ece4"
RULE       = "#d8d3ca"
RULE_MID   = "#b0a898"
RED        = "#c41e3a"
TEAL       = "#0a6b78"
TEAL_BG    = "#e4f4f6"
DARK_BG    = "#0f0f0f"

# Font stacks — Playfair/Source Serif load via Google Fonts link in <head>;
# Georgia/Times are the email-safe fallbacks that match the feel closely.
F_DISPLAY = "'Playfair Display', Georgia, 'Times New Roman', serif"
F_BODY    = "'Source Serif 4', Georgia, 'Times New Roman', serif"
F_MONO    = "'JetBrains Mono', 'Courier New', Courier, monospace"


# ── Markdown inline → HTML ────────────────────────────────────────

def _md(text: str) -> str:
    """Convert inline markdown to HTML with inline styles."""
    # Links
    text = re.sub(
        r'\[(.+?)\]\((https?://[^\)]+)\)',
        rf'<a href="\2" style="color:{TEAL};text-decoration:none;">\1</a>',
        text
    )
    # Bold
    text = re.sub(
        r'\*\*(.+?)\*\*',
        rf'<strong style="color:{INK};font-weight:700;">\1</strong>',
        text
    )
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


# ── Content extraction ────────────────────────────────────────────

def _bullets(lines: list) -> list:
    """Collect bullet lines from beneath a ### sub-heading."""
    result, past = [], False
    for line in lines:
        s = line.strip()
        if s.startswith("###"):
            past = True; continue
        if past and (s.startswith("- ") or s.startswith("* ")):
            result.append(s)
    return result


def _prose(lines: list) -> list:
    """Non-heading, non-bullet prose lines."""
    return [
        l.strip() for l in lines
        if not l.strip().startswith(("#", "- ", "* ")) and l.strip() != "---"
    ]


def _first_url(lines: list) -> str:
    """First URL found in any bullet line."""
    for line in lines:
        s = line.strip()
        if not (s.startswith("- ") or s.startswith("* ")):
            continue
        m = re.search(r'https?://[^\s\)]+', s)
        if m:
            return m.group(0).rstrip(".,)")
    return ""


def _split_url_from_line(line: str):
    """
    Split a bullet line into (body_text, url_or_empty).
    Handles both markdown links [text](url) at end and bare URLs.
    Returns body with markdown links still in it for _md() to process.
    """
    line = line.strip()
    if line.startswith(("- ", "* ")):
        line = line[2:].strip()

    # Bare URL at end of line
    bare = re.search(r'\s+(https?://\S+)$', line)
    if bare:
        url = bare.group(1).rstrip(".,)")
        body = line[:bare.start()].strip()
        return body, url

    return line, ""


# ── HTML component builders ───────────────────────────────────────

def _src_badge(url: str) -> str:
    if not url:
        return ""
    domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
    return (
        f'<a href="{url}" style="display:inline-block;margin-left:7px;'
        f'font-family:{F_MONO};font-size:10px;color:{TEAL};'
        f'background:{TEAL_BG};padding:1px 8px;border-radius:2px;'
        f'text-decoration:none;vertical-align:middle;white-space:nowrap;">'
        f'{domain}&nbsp;↗</a>'
    )


def _bullet_rows(bullets: list) -> str:
    rows = []
    last = len(bullets) - 1
    for i, raw in enumerate(bullets):
        body, url = _split_url_from_line(raw)
        body_html = _md(body)
        src = _src_badge(url)
        border = f"border-bottom:1px solid {RULE};" if i < last else ""
        rows.append(
            f'<tr valign="top">'
            f'<td style="width:18px;padding:11px 6px 11px 0;{border}'
            f'font-family:{F_BODY};font-size:14px;line-height:1.65;'
            f'color:{RED};font-weight:700;">—</td>'
            f'<td style="padding:11px 0;{border}'
            f'font-family:{F_BODY};font-size:14px;line-height:1.68;color:{INK_MID};">'
            f'{body_html}{src}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _qt_block(bullets: list, label: str = "The Quick Take") -> str:
    if not bullets:
        return (
            f'<p style="font-family:{F_BODY};font-style:italic;'
            f'color:{INK_SOFT};font-size:13px;margin:0;">No significant updates this week.</p>'
        )
    rows_html = _bullet_rows(bullets)
    return (
        f'<div style="background:{WARM};border-left:3px solid {RED};'
        f'padding:18px 22px 14px 22px;">'
        f'<div style="font-family:{F_MONO};font-size:9px;letter-spacing:0.2em;'
        f'text-transform:uppercase;color:{RED};margin-bottom:14px;">{label}</div>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )


def _section_header(num: str, title: str, url: str = "") -> str:
    if url:
        title_el = (
            f'<a href="{url}" style="font-family:{F_DISPLAY};font-size:23px;'
            f'font-weight:700;color:{INK};text-decoration:none;line-height:1.1;">'
            f'{title}</a>'
        )
    else:
        title_el = (
            f'<span style="font-family:{F_DISPLAY};font-size:23px;'
            f'font-weight:700;color:{INK};line-height:1.1;">{title}</span>'
        )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'width="100%" style="margin-bottom:20px;">'
        f'<tr valign="middle">'
        f'<td style="width:1%;white-space:nowrap;padding-right:10px;'
        f'font-family:{F_MONO};font-size:9px;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:{RED};">{num}</td>'
        f'<td style="width:1%;white-space:nowrap;">{title_el}</td>'
        f'<td style="padding-left:12px;">'
        f'<div style="height:1px;background:{RULE};font-size:0;line-height:0;">&nbsp;</div>'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


def _standard_section(html_id: str, num: str, title: str, lines: list) -> str:
    bl    = _bullets(lines)
    url   = _first_url(lines)
    label = "Notable Discussions This Week" if html_id == "community" else "The Quick Take"
    return (
        f'<div id="{html_id}" style="padding:36px 0 32px;'
        f'border-bottom:1px solid {RULE};">'
        f'{_section_header(num, title, url)}'
        f'{_qt_block(bl, label)}'
        f'</div>'
    )


def _one_to_watch(lines: list) -> str:
    pr = _prose(lines)
    pgs, cur = [], []
    for l in pr:
        if l == "":
            if cur: pgs.append(" ".join(cur)); cur = []
        else:
            cur.append(l)
    if cur: pgs.append(" ".join(cur))

    paras = "".join(
        f'<p style="font-family:{F_BODY};font-size:14px;line-height:1.75;'
        f'color:{ON_DARK};font-weight:300;margin:0 0 12px 0;">{_md(p)}</p>'
        for p in pgs if p
    )
    # fix last paragraph margin
    paras = re.sub(r'margin:0 0 12px 0;"></p>$', f'margin:0;"></p>', paras)

    return (
        f'<div id="watch" style="padding:36px 0 0;">'
        f'{_section_header("§ 06", "One to Watch")}'
        f'<div style="background:{DARK_BG};padding:24px 28px;position:relative;">'
        f'<div style="font-family:{F_MONO};font-size:9px;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:{RED};margin-bottom:12px;">📌 &nbsp;Editor\'s Pick</div>'
        f'{paras}'
        f'</div>'
        f'</div>'
    )


# ── Nav bar ───────────────────────────────────────────────────────

def _nav_bar() -> str:
    items = [
        ("🚀", "Models",    "#models"),
        ("📚", "Research",  "#research"),
        ("🏢", "Industry",  "#industry"),
        ("🛠", "Tools",     "#tools"),
        ("🐦", "Community", "#community"),
        ("📌", "One to Watch","#watch"),
    ]
    cells = ""
    for emoji, label, href in items:
        cells += (
            f'<td style="border-right:1px solid {RULE};">'
            f'<a href="{href}" style="display:block;padding:11px 18px;'
            f'font-family:{F_MONO};font-size:9px;letter-spacing:0.13em;'
            f'text-transform:uppercase;color:{INK_SOFT};text-decoration:none;'
            f'white-space:nowrap;">'
            f'{emoji}&nbsp;{label}</a>'
            f'</td>'
        )
    return (
        f'<div style="background:{WARM};border-bottom:1px solid {RULE};overflow:hidden;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">'
        f'<tr>{cells}</tr>'
        f'</table>'
        f'</div>'
    )


# ── Full HTML assembler ───────────────────────────────────────────

def _build_html(summary_html: str, sections_html: str,
                week_of: str, edition: str, next_ed: str) -> str:

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI Weekly — {week_of}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
/* Hover + dark mode only — everything else is inlined */
.nav-link:hover {{ color:{RED} !important; background:rgba(196,30,58,0.05) !important; }}
@media (prefers-color-scheme:dark) {{
  body {{ background:#111110 !important; }}
  .wrapper {{ background:#1c1b19 !important; border-color:#3a3830 !important; }}
  .mh {{ background:#1c1b19 !important; }}
  .warm-bg {{ background:#242220 !important; }}
  .ink-text {{ color:#f0ece4 !important; }}
  .mid-text {{ color:#d0ccc4 !important; }}
  .soft-text {{ color:#908880 !important; }}
  .rule-line {{ background:#343230 !important; }}
  .qt-block {{ background:#242220 !important; }}
  .outer-bg {{ background:#111110 !important; }}
}}
@media (max-width:580px) {{
  .wrapper {{ width:100% !important; }}
  .mh-title {{ font-size:42px !important; letter-spacing:-1px !important; }}
  .mh-meta td {{ display:block !important; text-align:center !important; padding:3px 0 !important; }}
  .body-pad {{ padding:0 22px !important; }}
  .sb {{ padding:14px 22px !important; }}
  .ft {{ padding:18px 22px !important; }}
  .nav-scroll {{ overflow-x:auto !important; -webkit-overflow-scrolling:touch !important; }}
}}
</style>
</head>
<body class="outer-bg" style="margin:0;padding:40px 16px 80px;background:{OUTER};font-family:{F_BODY};">

<div class="wrapper" style="max-width:680px;margin:0 auto;background:{PAPER};
  border:1px solid {RULE_MID};
  box-shadow:0 6px 48px rgba(0,0,0,0.14),0 1px 4px rgba(0,0,0,0.08);">

  <!-- ═══ MASTHEAD ════════════════════════════════════════════ -->
  <div class="mh warm-bg" style="background:{WARM};padding:32px 48px 20px;
    text-align:center;border-bottom:3px double {INK};">

    <div class="soft-text" style="font-family:{F_MONO};font-size:9px;
      letter-spacing:0.22em;text-transform:uppercase;color:{INK_SOFT};
      margin-bottom:14px;">Independent AI Research Digest</div>

    <div class="mh-title ink-text" style="font-family:{F_DISPLAY};font-size:62px;
      font-weight:900;letter-spacing:-2px;line-height:1;color:{INK};">
      AI <span style="color:{RED};">Weekly</span>
    </div>

    <!-- Ornamental rule -->
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"
      width="100%" style="margin:16px 0 14px;">
      <tr valign="middle">
        <td style="height:1px;background:{INK};font-size:0;line-height:0;">&nbsp;</td>
        <td style="width:10px;padding:0 8px;">
          <div style="width:7px;height:7px;background:{RED};
            transform:rotate(45deg);margin:0 auto;font-size:0;"></div>
        </td>
        <td style="height:1px;background:{INK};font-size:0;line-height:0;">&nbsp;</td>
      </tr>
    </table>

    <!-- Vol / tagline / date — 3 column grid -->
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr valign="middle">
        <td style="width:33%;text-align:left;font-family:{F_MONO};font-size:9px;
          letter-spacing:0.14em;text-transform:uppercase;color:{INK_SOFT};"
          class="soft-text">{edition}</td>
        <td style="width:34%;text-align:center;font-family:{F_BODY};
          font-style:italic;font-weight:300;font-size:12px;color:{INK_SOFT};"
          class="soft-text">What happened in AI this week&nbsp;—&nbsp;and why it matters</td>
        <td style="width:33%;text-align:right;font-family:{F_MONO};font-size:9px;
          letter-spacing:0.14em;text-transform:uppercase;color:{INK_SOFT};"
          class="soft-text">{week_of}</td>
      </tr>
    </table>
  </div>

  <!-- ═══ SUMMARY BAR ═════════════════════════════════════════ -->
  <div class="sb" style="background:{DARK_BG};color:{ON_DARK};padding:16px 48px;
    font-family:{F_BODY};font-size:13.5px;line-height:1.65;font-weight:300;
    border-bottom:3px solid {RED};">
    {summary_html}
  </div>

  <!-- ═══ NAV BAR ═════════════════════════════════════════════ -->
  {_nav_bar()}

  <!-- ═══ SECTIONS ════════════════════════════════════════════ -->
  <div class="body-pad" style="padding:0 48px;">
    {sections_html}
  </div>

  <!-- ═══ FOOTER ══════════════════════════════════════════════ -->
  <div class="ft warm-bg" style="background:{WARM};padding:20px 48px 24px;
    border-top:3px double {INK};text-align:center;">
    <div class="soft-text" style="font-family:{F_MONO};font-size:9px;
      letter-spacing:0.16em;text-transform:uppercase;color:{INK_SOFT};margin-bottom:8px;">
      Next edition:&nbsp;
      <strong class="ink-text" style="color:{INK};">{next_ed}</strong>
    </div>
    <div style="font-family:{F_BODY};font-size:11px;color:{INK_FAINT};
      font-style:italic;line-height:1.65;" class="soft-text">
      AI Weekly is an independent digest. All summaries reflect publicly available reporting.<br>
      Not financial or investment advice.
    </div>
  </div>

</div><!-- /wrapper -->
</body>
</html>"""


# ── Main parser ───────────────────────────────────────────────────

def markdown_to_html(md: str, date: datetime.datetime) -> str:
    lines       = md.splitlines()
    week_of     = date.strftime("Week of %b %d, %Y")
    next_ed     = (date + datetime.timedelta(days=7)).strftime("%B %d, %Y")
    edition_num = date.isocalendar()[1]
    edition     = f"Vol. 2026 · No. {edition_num}"

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
        f'<strong style="font-weight:700;color:{ON_DARK};">This week:</strong> {_md(summary_text)}'
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
    sections_html = ""
    for heading, content in raw_sections:
        if re.search(r'at a glance|next edition|independent newsletter|not financial', heading, re.IGNORECASE):
            continue
        if re.search(r'one to watch', heading, re.IGNORECASE):
            sections_html += _one_to_watch(content)
            continue
        matched = False
        for key, html_id, display_title, section_num in SECTION_MAP:
            if key.lower() in heading.lower():
                sections_html += _standard_section(html_id, section_num, display_title, content)
                matched = True
                break
        if not matched:
            bl = _bullets(content)
            safe_id = re.sub(r'[^a-z0-9]', '-', heading.lower())[:24].strip('-')
            clean_t = re.sub(r'[^\w\s&\-]', '', heading).strip()
            sections_html += (
                f'<div id="{safe_id}" style="padding:36px 0 32px;border-bottom:1px solid {RULE};">'
                f'{_section_header("", clean_t)}'
                f'{_qt_block(bl)}'
                f'</div>'
            )

    return _build_html(summary_html, sections_html, week_of, edition, next_ed)


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
