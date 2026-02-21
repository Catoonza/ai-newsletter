# 🤖 AI Weekly Newsletter Generator

An automated pipeline that collects AI news, blog posts, arXiv papers, and tweets every week, then uses Claude to synthesise them into a dual-layer newsletter (quick takes + technical deep dives).

Runs automatically every **Friday at 5 PM UTC** via GitHub Actions.

---

## What It Collects

| Source | Method | Cost |
|--------|--------|------|
| AI industry news | NewsAPI | Free tier |
| Provider blogs (Anthropic, OpenAI, Google, Mistral, Meta, HuggingFace, AWS, NVIDIA, Cohere) | RSS feeds | Free |
| arXiv papers (cs.AI, cs.LG, cs.CL, cs.CV, stat.ML) | arXiv public API | Free |
| Tweets from ~18 AI leaders & researchers | ntscraper (public Nitter) | Free |
| Newsletter generation | Anthropic API (Claude) | ~$0.01–0.05/week |

---

## Setup

### 1. Fork or clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/ai-newsletter.git
cd ai-newsletter
```

### 2. Get your API keys

#### Anthropic API (required)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account and add a payment method
3. Go to **API Keys** and create a new key
4. Cost: ~$0.01–0.05 per weekly newsletter run

#### NewsAPI (required for news articles)
1. Go to [newsapi.org/register](https://newsapi.org/register)
2. Sign up for a free account
3. Copy your API key from the dashboard
4. Free tier: 100 requests/day (more than enough)

#### Email / SMTP (optional — for emailing yourself the newsletter)
If you use **Gmail**:
1. Go to your Google Account → Security → 2-Step Verification (must be enabled)
2. Go to **App Passwords** → create one for "Mail"
3. Use your Gmail address as `SMTP_FROM` and the App Password as `SMTP_PASSWORD`

For other providers, set `SMTP_HOST` and `SMTP_PORT` accordingly.

---

### 3. Add secrets to GitHub

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `NEWSAPI_KEY` | Your NewsAPI key |
| `SMTP_FROM` | Your email address (optional) |
| `SMTP_PASSWORD` | Your Gmail App Password (optional) |
| `SMTP_TO` | Recipient email address (optional) |

---

### 4. Enable GitHub Actions

Go to **Actions** tab in your repo and click **"I understand my workflows, go ahead and enable them"** if prompted.

The workflow will now run automatically every Friday at 5 PM UTC.

---

## Running Manually

### Locally

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY="your-key"
export NEWSAPI_KEY="your-key"

cd src
python newsletter.py
```

Output is saved to `output/ai-weekly-YYYY-MM-DD.md`.

### Via GitHub Actions

1. Go to **Actions → AI Weekly Newsletter**
2. Click **"Run workflow"**
3. Click the green **"Run workflow"** button

The newsletter will appear as a downloadable artifact, be committed to `output/`, and emailed if SMTP is configured.

---

## Customising

### Add/remove Twitter handles
Edit `src/collectors/twitter.py` → `TWITTER_PROFILES` list.

### Add/remove RSS feeds
Edit `src/collectors/rss.py` → `RSS_FEEDS` list. Any RSS/Atom feed URL works.

### Change news search topics
Edit `src/collectors/news.py` → `SEARCH_QUERIES` list.

### Change arXiv categories
Edit `src/collectors/arxiv.py` → `CATEGORIES` list.

### Change the newsletter format/tone
Edit the `SYSTEM_PROMPT` and `build_user_prompt()` in `src/summariser.py`.

### Change the schedule
Edit `.github/workflows/newsletter.yml` → `cron` field.
- Every Friday 5 PM UTC: `0 17 * * 5`
- Every Monday 8 AM UTC: `0 8 * * 1`
- Use [crontab.guru](https://crontab.guru) to build custom schedules.

---

## Output

Each run produces two files in `output/`:

- `ai-weekly-YYYY-MM-DD.md` — the formatted newsletter (Markdown)
- `raw_YYYYMMDD.json` — all raw collected data (for debugging or reprocessing)

---

## Project Structure

```
ai-newsletter/
├── .github/
│   └── workflows/
│       └── newsletter.yml      # GitHub Actions schedule
├── src/
│   ├── newsletter.py           # Main entry point
│   ├── summariser.py           # Claude API call + prompt
│   ├── exporter.py             # Save to file + optional email
│   └── collectors/
│       ├── news.py             # NewsAPI
│       ├── rss.py              # RSS feed scraper
│       ├── arxiv.py            # arXiv API
│       └── twitter.py          # ntscraper (Twitter)
├── output/                     # Generated newsletters (auto-created)
├── requirements.txt
└── README.md
```

---

## Troubleshooting

**Twitter scraping returns 0 tweets**
Nitter instances go down occasionally. Try running again later, or swap to a different Nitter instance by modifying the `Nitter()` constructor in `twitter.py`.

**NewsAPI returns 0 articles**
Check your `NEWSAPI_KEY` is set correctly. Free tier only allows fetching articles up to 30 days old.

**Claude API error**
Verify your `ANTHROPIC_API_KEY` is valid and your account has credits.

**GitHub Actions not running**
Make sure Actions are enabled in your repo settings. The first scheduled run will happen at the next Friday 5 PM UTC after you push the workflow file.
