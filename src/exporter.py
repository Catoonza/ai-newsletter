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
PAPER     = "#faf8f4"
WARM      = "#f2efe9"
OUTER     = "#e8e4dc"
INK       = "#0f0f0f"
INK_MID   = "#3a3a3a"
INK_SOFT  = "#5a5a5a"
INK_FAINT = "#909090"
ON_DARK   = "#f0ece4"
RULE      = "#d8d3ca"
RULE_MID  = "#b0a898"
RED       = "#c41e3a"
TEAL      = "#0a6b78"
TEAL_BG   = "#e4f4f6"
DARK_BG   = "#0f0f0f"

# Font stacks — Playfair/Source Serif load via Google Fonts link in <head>;
# Georgia/Times are the email-safe fallbacks that match the feel closely.
F_DISPLAY = "'Playfair Display', Georgia, 'Times New Roman', serif"
F_BODY    = "'Source Serif 4', Georgia, 'Times New Roman', serif"
F_MONO    = "'JetBrains Mono', 'Courier New', Courier, monospace"

# Shared overflow-safe text style (prevents content from extending past container)
_WRAP = "overflow-wrap:break-word;word-wrap:break-word;word-break:break-word;"

# ── Endnote registry (populated per newsletter build) ─────────────
_endnotes: list = []  # [(url, domain), ...]


def _reset_endnotes():
    global _endnotes
    _endnotes = []


def _add_endnote(url: str) -> int:
    """Register a URL and return its 1-based endnote number."""
    global _endnotes
    # Deduplicate: if same URL already registered, return existing number
    for i, (existing_url, _) in enumerate(_endnotes):
        if existing_url == url:
            return i + 1
    domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
    _endnotes.append((url, domain))
    return len(_endnotes)


# ── Markdown inline → HTML ────────────────────────────────────────

def _md(text: str, on_dark: bool = False) -> str:
    """Convert inline markdown to HTML with inline styles.

    on_dark: if True, bold text uses light color for dark backgrounds.
    """
    # Links — teal works on both light and dark
    text = re.sub(
        r'\[(.+?)\]\((https?://[^\)]+)\)',
        rf'<a href="\2" style="color:{TEAL};text-decoration:none;">\1</a>',
        text
    )
    # Bold — inherit parent color, don't force dark ink
    bold_color = ON_DARK if on_dark else "inherit"
    text = re.sub(
        r'\*\*(.+?)\*\*',
        rf'<strong class="bld" style="font-weight:700;color:{bold_color};">\1</strong>',
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
        if past and (s.startswith("- ") or s.startswith("* ") or re.match(r'^\d+\.\s', s)):
            result.append(s)
    return result


def _prose(lines: list) -> list:
    """Non-heading, non-bullet prose lines."""
    return [
        l.strip() for l in lines
        if not l.strip().startswith(("#", "- ", "* ")) and l.strip() != "---"
    ]


def _extract_all_urls(line: str) -> list:
    """Extract all URLs from a line (both markdown links and bare URLs)."""
    urls = []
    # Markdown links [text](url)
    for m in re.finditer(r'\[.+?\]\((https?://[^\)]+)\)', line):
        urls.append(m.group(1).rstrip(".,)"))
    # Bare URLs not inside markdown link syntax
    bare_line = re.sub(r'\[.+?\]\(https?://[^\)]+\)', '', line)
    for m in re.finditer(r'https?://[^\s]+', bare_line):
        url = m.group(0).rstrip(".,)")
        if url not in urls:
            urls.append(url)
    return urls


def _strip_urls_from_body(line: str) -> str:
    """Strip leading bullet/number prefix from a line. Keeps markdown links intact."""
    line = line.strip()
    if line.startswith(("- ", "* ")):
        line = line[2:].strip()
    else:
        # Numbered list: "1. text"
        m = re.match(r'^\d+\.\s+', line)
        if m:
            line = line[m.end():].strip()
    return line


# ── HTML component builders ───────────────────────────────────────

# Shared table reset for Outlook spacing
_TBL = "mso-table-lspace:0pt;mso-table-rspace:0pt;"


def _endnote_sup(url: str) -> str:
    """Render a superscript endnote number linking to the source."""
    n = _add_endnote(url)
    return (
        f'<sup style="font-family:{F_MONO};font-size:10px;line-height:0;'
        f'vertical-align:super;">'
        f'<a href="{url}" style="color:{TEAL};text-decoration:none;">[{n}]</a>'
        f'</sup>'
    )


def _bullet_rows(bullets: list) -> str:
    rows = []
    last = len(bullets) - 1
    for i, raw in enumerate(bullets):
        body = _strip_urls_from_body(raw)
        urls = _extract_all_urls(raw)
        body_html = _md(body)
        # Append endnote superscripts for each source URL
        endnotes_html = ""
        for url in urls:
            endnotes_html += _endnote_sup(url)
        border = f"border-bottom:1px solid {RULE};" if i < last else ""
        rows.append(
            f'<tr valign="top">'
            f'<td style="width:18px;padding:11px 6px 11px 0;{border}'
            f'font-family:{F_BODY};font-size:14px;line-height:1.65;'
            f'color:{RED};font-weight:700;">—</td>'
            f'<td class="mid-text" style="padding:11px 0;{border}'
            f'font-family:{F_BODY};font-size:14px;line-height:1.68;color:{INK_MID};{_WRAP}">'
            f'{body_html}{endnotes_html}</td>'
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
        f'<table role="presentation" class="warm-bg" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" bgcolor="{WARM}" style="background:{WARM};'
        f'border-left:3px solid {RED};{_TBL}">'
        f'<tr><td style="padding:18px 22px 14px 22px;">'
        f'<div style="font-family:{F_MONO};font-size:9px;letter-spacing:0.2em;'
        f'text-transform:uppercase;color:{RED};margin-bottom:14px;">{label}</div>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" style="table-layout:fixed;{_TBL}">'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</td></tr></table>'
    )


def _section_header(num: str, title: str) -> str:
    title_el = (
        f'<span class="sec-title ink-text" style="font-family:{F_DISPLAY};font-size:22px;'
        f'font-weight:700;color:{INK};line-height:1.2;{_WRAP}">{title}</span>'
    )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" style="margin-bottom:20px;{_TBL}">'
        f'<tr valign="middle">'
        f'<td style="white-space:nowrap;padding-right:10px;'
        f'font-family:{F_MONO};font-size:9px;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:{RED};">{num}</td>'
        f'<td style="white-space:nowrap;">{title_el}</td>'
        f'<td width="100%" style="padding-left:12px;">'
        f'<div class="rule-line" style="height:1px;background:{RULE};font-size:0;line-height:0;">&nbsp;</div>'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


def _standard_section(html_id: str, num: str, title: str, lines: list) -> str:
    bl    = _bullets(lines)
    label = "Notable Discussions This Week" if html_id == "community" else "The Quick Take"
    return (
        f'<div id="{html_id}" style="padding:36px 0 32px;'
        f'border-bottom:1px solid {RULE};">'
        f'{_section_header(num, title)}'
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

    paras = ""
    for p in pgs:
        if not p:
            continue
        # Collect endnotes from any URLs in prose
        urls = _extract_all_urls(p)
        endnotes_html = ""
        for url in urls:
            endnotes_html += _endnote_sup(url)
        paras += (
            f'<p style="font-family:{F_BODY};font-size:14px;line-height:1.75;'
            f'color:{ON_DARK};font-weight:300;margin:0 0 12px 0;{_WRAP}">'
            f'{_md(p, on_dark=True)}{endnotes_html}</p>'
        )
    # fix last paragraph margin
    paras = re.sub(r'margin:0 0 12px 0;([^"]*?)"></p>$', r'margin:0;\1"></p>', paras)

    return (
        f'<div id="watch" style="padding:36px 0 0;">'
        f'{_section_header("§ 06", "One to Watch")}'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" bgcolor="{DARK_BG}" style="background:{DARK_BG};{_TBL}">'
        f'<tr><td style="padding:24px 28px;">'
        f'<div style="font-family:{F_MONO};font-size:9px;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:{RED};margin-bottom:12px;">📌 &nbsp;Editor\'s Pick</div>'
        f'{paras}'
        f'</td></tr></table>'
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
        ("📌", "Watch",     "#watch"),
    ]
    # 2 rows x 3 columns — fits any screen width without overflow
    row1 = ""
    row2 = ""
    for i, (emoji, label, href) in enumerate(items):
        cell = (
            f'<td width="33%" style="text-align:center;'
            f'border-bottom:1px solid {RULE};'
            f'border-right:1px solid {RULE};">'
            f'<a href="{href}" class="nav-link" style="display:block;'
            f'padding:10px 6px;'
            f'font-family:{F_MONO};font-size:9px;letter-spacing:0.08em;'
            f'text-transform:uppercase;color:{INK_SOFT};text-decoration:none;'
            f'white-space:nowrap;">'
            f'{emoji}&nbsp;{label}</a>'
            f'</td>'
        )
        if i < 3:
            row1 += cell
        else:
            row2 += cell
    return (
        f'<table role="presentation" class="warm-bg" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" bgcolor="{WARM}" style="background:{WARM};{_TBL}">'
        f'<tr>{row1}</tr>'
        f'<tr>{row2}</tr>'
        f'</table>'
    )


# ── Endnotes section ──────────────────────────────────────────────

def _endnotes_section() -> str:
    """Render the Sources endnotes section at the bottom of the newsletter body."""
    global _endnotes
    if not _endnotes:
        return ""
    rows = ""
    for i, (url, domain) in enumerate(_endnotes):
        n = i + 1
        rows += (
            f'<tr valign="top">'
            f'<td style="width:28px;padding:4px 8px 4px 0;'
            f'font-family:{F_MONO};font-size:11px;color:{TEAL};'
            f'text-align:right;vertical-align:top;">[{n}]</td>'
            f'<td style="padding:4px 0;font-family:{F_MONO};font-size:11px;'
            f'color:{INK_SOFT};{_WRAP}">'
            f'<a href="{url}" style="color:{TEAL};text-decoration:none;">'
            f'{domain}</a>'
            f'</td>'
            f'</tr>'
        )
    return (
        f'<div style="padding:32px 0 8px;border-top:1px solid {RULE};margin-top:32px;">'
        f'<div style="font-family:{F_MONO};font-size:9px;letter-spacing:0.2em;'
        f'text-transform:uppercase;color:{INK_SOFT};margin-bottom:14px;">Sources</div>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"'
        f' width="100%" style="table-layout:fixed;">'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )


# ── Full HTML assembler ───────────────────────────────────────────

def _build_html(summary_html: str, sections_html: str,
                week_of: str, edition: str, next_ed: str) -> str:

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->
  <title>AI Weekly — {week_of}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <style>
    :root {{ color-scheme: light dark; }}
    .nav-link:hover {{ color:{RED} !important; background:rgba(196,30,58,0.05) !important; }}
    @media (prefers-color-scheme:dark) {{
      body {{ background:#111110 !important; }}
      .wrapper {{ background:#1c1b19 !important; border-color:#3a3830 !important; }}
      .mh, .warm-bg {{ background:#242220 !important; }}
      .ink-text, .bld, .sec-title {{ color:#f0ece4 !important; }}
      .mid-text, td.mid-text {{ color:#d0ccc4 !important; }}
      .soft-text {{ color:#908880 !important; }}
      .rule-line {{ background:#343230 !important; }}
      .qt-block {{ background:#242220 !important; }}
      .outer-bg {{ background:#111110 !important; }}
      .nav-link {{ color:#908880 !important; }}
      .dark-rule {{ background:#f0ece4 !important; }}
    }}
    @media screen and (max-width:600px) {{
      .wrapper {{ width:100% !important; border-left:0 !important; border-right:0 !important; }}
      .mh-title {{ font-size:36px !important; letter-spacing:-1px !important; }}
      .mh-meta td {{ display:block !important; text-align:center !important; padding:3px 0 !important; }}
      .body-pad {{ padding:0 16px !important; }}
      .mh-pad {{ padding-left:16px !important; padding-right:16px !important; }}
      .sb {{ padding:14px 16px !important; }}
      .ft {{ padding:18px 16px !important; }}
      .sec-title {{ font-size:18px !important; }}
    }}
  </style>
  <!--[if mso]><style>table {{ border-collapse:collapse; }} td {{ font-family:Georgia,'Times New Roman',serif; }}</style><![endif]-->
</head>
<body class="outer-bg" style="margin:0;padding:0;background:{OUTER};font-family:{F_BODY};
  -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">

<!-- Outer centering table — the industry-standard way to center in all clients -->
<table role="presentation" class="outer-bg" cellpadding="0" cellspacing="0" border="0"
  width="100%" bgcolor="{OUTER}" style="background:{OUTER};{_TBL}">
  <tr>
    <td style="padding:24px 12px 48px;" align="center">

<!--[if mso]><table role="presentation" cellpadding="0" cellspacing="0" border="0" width="680" align="center"><tr><td><![endif]-->

      <table role="presentation" class="wrapper" cellpadding="0" cellspacing="0" border="0"
        width="100%"
        bgcolor="{PAPER}"
        style="max-width:680px;background:{PAPER};
          border:1px solid {RULE_MID};{_TBL}">

        <!-- ══ MASTHEAD ══════════════════════════════════════ -->
        <tr><td class="mh warm-bg mh-pad" bgcolor="{WARM}"
          style="background:{WARM};padding:28px 32px 18px;
            text-align:center;border-bottom:3px double {INK};">

          <div class="soft-text" style="font-family:{F_MONO};font-size:9px;
            letter-spacing:0.22em;text-transform:uppercase;color:{INK_SOFT};
            margin-bottom:12px;">Independent AI Research Digest</div>

          <div class="mh-title ink-text" style="font-family:{F_DISPLAY};font-size:48px;
            font-weight:900;letter-spacing:-1.5px;line-height:1;color:{INK};">
            AI <span style="color:{RED};">Weekly</span>
          </div>

          <!-- Ornamental rule — Unicode diamond works everywhere including Outlook -->
          <table role="presentation" cellpadding="0" cellspacing="0" border="0"
            width="100%" style="margin:14px 0 12px;{_TBL}">
            <tr valign="middle">
              <td class="dark-rule" style="height:1px;background:{INK};font-size:0;line-height:0;">&nbsp;</td>
              <td style="width:24px;text-align:center;font-size:8px;color:{RED};padding:0 4px;">&#9670;</td>
              <td class="dark-rule" style="height:1px;background:{INK};font-size:0;line-height:0;">&nbsp;</td>
            </tr>
          </table>

          <!-- Vol / tagline / date — stacked on mobile via mh-meta class -->
          <table class="mh-meta" role="presentation" cellpadding="0" cellspacing="0" border="0"
            width="100%" style="{_TBL}">
            <tr valign="middle">
              <td style="width:30%;text-align:left;font-family:{F_MONO};font-size:9px;
                letter-spacing:0.12em;text-transform:uppercase;color:{INK_SOFT};"
                class="soft-text">{edition}</td>
              <td style="width:40%;text-align:center;font-family:{F_BODY};
                font-style:italic;font-weight:300;font-size:11px;color:{INK_SOFT};"
                class="soft-text">What happened in AI this week</td>
              <td style="width:30%;text-align:right;font-family:{F_MONO};font-size:9px;
                letter-spacing:0.12em;text-transform:uppercase;color:{INK_SOFT};"
                class="soft-text">{week_of}</td>
            </tr>
          </table>
        </td></tr>

        <!-- ══ SUMMARY BAR ═══════════════════════════════════ -->
        <tr><td class="sb" bgcolor="{DARK_BG}"
          style="background:{DARK_BG};color:{ON_DARK};padding:16px 32px;
            font-family:{F_BODY};font-size:13.5px;line-height:1.65;font-weight:300;
            border-bottom:3px solid {RED};{_WRAP}">
          {summary_html}
        </td></tr>

        <!-- ══ NAV BAR ═══════════════════════════════════════ -->
        <tr><td style="padding:0;">
          {_nav_bar()}
        </td></tr>

        <!-- ══ SECTIONS ══════════════════════════════════════ -->
        <tr><td class="body-pad" style="padding:0 32px;">
          {sections_html}
          {_endnotes_section()}
        </td></tr>

        <!-- ══ FOOTER ════════════════════════════════════════ -->
        <tr><td class="ft warm-bg" bgcolor="{WARM}"
          style="background:{WARM};padding:20px 32px 24px;
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
        </td></tr>

      </table>

<!--[if mso]></td></tr></table><![endif]-->

    </td>
  </tr>
</table>

</body>
</html>"""


# ── Main parser ───────────────────────────────────────────────────

def markdown_to_html(md: str, date: datetime.datetime) -> str:
    _reset_endnotes()
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
        f'<strong style="font-weight:700;color:{ON_DARK};">This week:</strong> {_md(summary_text, on_dark=True)}'
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
