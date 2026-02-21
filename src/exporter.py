"""
Saves the generated newsletter to disk.
Optionally sends it via email (configure below).
"""

import os
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def save_newsletter(newsletter_md: str, date: datetime.datetime) -> str:
    """Save the newsletter markdown to the output directory."""
    os.makedirs("output", exist_ok=True)
    filename = f"output/ai-weekly-{date.strftime('%Y-%m-%d')}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(newsletter_md)

    # Optionally send via email if credentials are configured
    _maybe_send_email(newsletter_md, date)

    return filename


def _maybe_send_email(newsletter_md: str, date: datetime.datetime):
    """
    Sends the newsletter via email if SMTP env vars are set.
    Uses Gmail App Password by default — works with any SMTP provider.

    Required environment variables (all optional — skip to disable email):
      SMTP_FROM      — sender address (e.g. you@gmail.com)
      SMTP_PASSWORD  — Gmail App Password (not your main password)
      SMTP_TO        — recipient address (can be same as FROM)
      SMTP_HOST      — defaults to smtp.gmail.com
      SMTP_PORT      — defaults to 587
    """
    smtp_from = os.environ.get("SMTP_FROM")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_to = os.environ.get("SMTP_TO")

    if not all([smtp_from, smtp_password, smtp_to]):
        print("   ℹ️  Email not configured (SMTP_FROM / SMTP_PASSWORD / SMTP_TO not set)")
        print("   ℹ️  Newsletter saved to file only")
        return

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    week_str = date.strftime("%B %d, %Y")
    subject = f"🤖 AI Weekly — Week of {week_str}"

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = smtp_to

    # Plain text fallback
    msg.attach(MIMEText(newsletter_md, "plain"))

    # HTML version (basic markdown → HTML conversion)
    html_body = _markdown_to_simple_html(newsletter_md)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_from, smtp_password)
            server.sendmail(smtp_from, smtp_to, msg.as_string())
        print(f"   ✉️  Newsletter emailed to {smtp_to}")
    except Exception as e:
        print(f"   ⚠️  Email failed: {e}")


def _markdown_to_simple_html(md: str) -> str:
    """
    Very lightweight markdown → HTML conversion for email.
    For richer rendering, replace with the `markdown` library.
    """
    import re

    html = md

    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)

    # Italic
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Links
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)

    # Bullet points
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)

    # Paragraphs (double newlines)
    html = re.sub(r"\n\n", r"</p><p>", html)

    return f"""
    <html>
    <body style="font-family: Georgia, serif; max-width: 680px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.7;">
        <p>{html}</p>
    </body>
    </html>
    """
