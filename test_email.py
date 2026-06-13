"""
test_email.py

Send a test newsletter email using the latest markdown output.
No AI calls - just renders existing markdown to HTML and sends it.

Usage:
    # Using env vars (same ones the real pipeline uses):
    python test_email.py

    # Override recipient for testing:
    python test_email.py --to you@example.com

    # Use a specific markdown file:
    python test_email.py --file output/ai-weekly-2026-05-03.md

    # Just regenerate HTML without sending (opens in browser):
    python test_email.py --preview

Required env vars (unless --preview):
    SMTP_FROM
    SMTP_PASSWORD
    SMTPTO

Optional:
    SMTP_HOST (default: smtp.gmail.com)
    SMTP_PORT (default: 587)
"""

import argparse
import datetime
import glob
import os
import re
import smtplib
import sys
import webbrowser

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from exporter import markdown_to_html


def find_latest_md():
    files = sorted(glob.glob("output/ai-weekly-*.md"))

    if not files:
        print("No markdown files found in output/.")
        print("Run the newsletter generator first,")
        print("or specify a file with --file.")
        sys.exit(1)

    return files[-1]


def extract_date(md_path):
    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        os.path.basename(md_path),
    )

    if match:
        return datetime.datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )

    return datetime.datetime.utcnow()


def main():
    parser = argparse.ArgumentParser(
        description="Send a test newsletter email"
    )

    parser.add_argument(
        "--to",
        help="Override recipient email address",
    )

    parser.add_argument(
        "--file",
        "-f",
        help="Path to markdown file (default: latest in output/)",
    )

    parser.add_argument(
        "--preview",
        "-p",
        action="store_true",
        help="Just open in browser, don't send email",
    )

    parser.add_argument(
        "--subject",
        "-s",
        help="Override email subject line",
    )

    args = parser.parse_args()

    # Find markdown
    md_path = args.file or find_latest_md()

    print(f"Using: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    date = extract_date(md_path)

    print(f"Date: {date.strftime('%Y-%m-%d')}")

    # Render HTML
    html = markdown_to_html(md_content, date)

    print(f"Rendered HTML ({len(html):,} bytes)")

    # Save HTML alongside markdown
    test_html_path = md_path.replace(".md", "-test.html")

    with open(test_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved to: {test_html_path}")

    # Preview only
    if args.preview:
        webbrowser.open(
            f"file://{os.path.abspath(test_html_path)}"
        )
        print("Opened in browser")
        return

    # Email settings
    smtp_from = os.environ.get("SMTP_FROM")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_to = args.to or os.environ.get("SMTPTO")

    if not all([smtp_from, smtp_password, smtp_to]):
        missing = []

        if not smtp_from:
            missing.append("SMTP_FROM")

        if not smtp_password:
            missing.append("SMTP_PASSWORD")

        if not smtp_to:
            missing.append("SMTPTO (or use --to)")

        print(
            f"\nMissing env vars: {', '.join(missing)}"
        )
        print("Set them or use --preview to just view in browser.")
        sys.exit(1)

    smtp_host = os.environ.get(
        "SMTP_HOST",
        "smtp.gmail.com",
    )

    smtp_port = int(
        os.environ.get(
            "SMTP_PORT",
            "587",
        )
    )

    week_str = date.strftime("%B %d, %Y")

    subject = (
        args.subject
        or f"[TEST] AI Weekly - Week of {week_str}"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = smtp_to

    msg.attach(MIMEText(md_content, "plain"))
    msg.attach(MIMEText(html, "html"))

    print(
        f"\nSending to {smtp_to} via {smtp_host}:{smtp_port}..."
    )

    try:
        with smtplib.SMTP(
            smtp_host,
            smtp_port,
        ) as server:
            server.ehlo()
            server.starttls()
            server.login(
                smtp_from,
                smtp_password,
            )

            server.sendmail(
                smtp_from,
                smtp_to,
                msg.as_string(),
            )

        print(f"Test email sent to {smtp_to}")

    except Exception as e:
        print(f"Send failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()