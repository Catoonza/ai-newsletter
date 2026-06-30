"""
send_test.py

A simple, standalone script to send a compiled HTML newsletter file to your inbox
via SMTP to preview how it renders in your actual email client (e.g. Outlook, Gmail).
Does NOT call the Anthropic API.

Usage:
    # Set env vars:
    export SMTP_FROM="your-gmail@gmail.com"
    export SMTP_PASSWORD="your-app-password"
    export SMTP_TO="recipient@example.com"
    
    python send_test.py
    
    # Or pass them as arguments:
    python send_test.py --to recipient@example.com --from your-gmail@gmail.com --password xxxx-xxxx-xxxx-xxxx
"""

import os
import sys
import glob
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for path in [os.path.join(script_dir, ".env"), os.path.join(os.path.dirname(script_dir), ".env")]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        os.environ[key] = val
            break

def find_latest_html():
    # Look for both -test.html and regular .html outputs
    files = sorted(glob.glob("output/*.html"))
    if not files:
        print("❌ No HTML files found in output/ directory.")
        print("Please compile a newsletter first by running: python test_email.py --preview")
        sys.exit(1)
    return files[-1]

def main():
    load_env()
    parser = argparse.ArgumentParser(description="Send compiled HTML newsletter to email")
    parser.add_argument("--to", help="Recipient email address (or SMTP_TO env var)")
    parser.add_argument("--from-email", "--from", dest="from_email", help="Sender email address (or SMTP_FROM env var)")
    parser.add_argument("--password", help="SMTP password or app password (or SMTP_PASSWORD env var)")
    parser.add_argument("--file", "-f", help="HTML file to send (default: latest in output/)")
    parser.add_argument("--subject", "-s", help="Email subject line")
    parser.add_argument("--host", default="smtp.gmail.com", help="SMTP Host (default: smtp.gmail.com)")
    parser.add_argument("--port", type=int, default=587, help="SMTP Port (default: 587)")

    args = parser.parse_args()

    # 1. Resolve credentials and email addresses
    smtp_from = args.from_email or os.environ.get("SMTP_FROM")
    smtp_password = args.password or os.environ.get("SMTP_PASSWORD")
    smtp_to = args.to or os.environ.get("SMTP_TO") or os.environ.get("SMTPTO")

    if not all([smtp_from, smtp_password, smtp_to]):
        missing = []
        if not smtp_from: missing.append("--from / SMTP_FROM")
        if not smtp_password: missing.append("--password / SMTP_PASSWORD")
        if not smtp_to: missing.append("--to / SMTP_TO")
        
        print("❌ Missing required configuration:")
        for item in missing:
            print(f"   * {item}")
        print("\nEither set the environment variables or pass them as arguments.")
        print("Example:")
        print("  python send_test.py --to you@example.com --from your-gmail@gmail.com --password app-password")
        sys.exit(1)

    # 2. Find html file
    html_path = args.file or find_latest_html()
    print(f"📂 Reading HTML file: {html_path}")
    
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 3. Create MIME message
    subject = args.subject or f"[PREVIEW] AI Weekly — {os.path.basename(html_path)}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = smtp_to
    
    # Text fallback
    text_fallback = "Please enable HTML viewing to preview the newsletter."
    msg.attach(MIMEText(text_fallback, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    # 4. Connect to SMTP server and send
    print(f"📡 Connecting to {args.host}:{args.port}...")
    try:
        with smtplib.SMTP(args.host, args.port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_from, smtp_password)
            print("🔑 Logged in successfully!")
            print(f"✉️ Sending to {smtp_to}...")
            server.sendmail(smtp_from, smtp_to, msg.as_string())
        print(f"🎉 Success! Preview email has been sent to {smtp_to}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
