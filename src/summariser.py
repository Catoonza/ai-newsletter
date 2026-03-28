"""
Uses the Anthropic API to summarise all collected data into a newsletter.
Model: claude-sonnet-4-6
Includes retry with exponential backoff for rate limit errors.
"""

import os
import time
import json
import datetime
import anthropic
from typing import Dict


SYSTEM_PROMPT = """You are an expert AI journalist and researcher. 
You write a weekly AI newsletter for a dual audience:
- Non-technical readers who want clear, jargon-free summaries of what happened and why it matters
- Technical readers who want depth, nuance, and understanding of the underlying mechanisms

Your newsletter structure for each section must always include:
1. **The Quick Take** — 3-5 bullet points. Plain English. One sentence each. What happened and why it matters.
2. **Deeper Dive** — 2-4 paragraphs. Explain the technical concepts behind the news. Use analogies. 
   Assume the reader is intelligent but not a specialist.

Your writing is precise, neutral, insightful, and never hype-driven.
You always attribute claims to their sources.
You skip anything that is not meaningfully new or interesting.
You synthesise across sources to identify patterns — not just list events.
Output only valid Markdown."""


def build_user_prompt(data: Dict) -> str:
    start = data["date_range"]["start"][:10]
    end = data["date_range"]["end"][:10]

    sections = []

    # ── News articles ────────────────────────────────────────────
    if data.get("news_articles"):
        news_text = "\n\n".join([
            f"Title: {a['title']}\nSource: {a['source_name']}\nDate: {a['published_at'][:10]}\nSummary: {a.get('description','')}\nURL: {a['url']}"
            for a in data["news_articles"]
        ])
        sections.append(f"## NEWS ARTICLES\n{news_text}")

    # ── Blog posts ───────────────────────────────────────────────
    if data.get("blog_posts"):
        blogs_text = "\n\n".join([
            f"Provider: {p['provider']}\nTitle: {p['title']}\nDate: {p['published_at'][:10]}\nSummary: {p.get('summary','')}\nURL: {p['url']}"
            for p in data["blog_posts"]
        ])
        sections.append(f"## PROVIDER BLOG POSTS\n{blogs_text}")

    # ── arXiv papers ─────────────────────────────────────────────
    if data.get("arxiv_papers"):
        papers_text = "\n\n".join([
            f"Title: {p['title']}\nAuthors: {', '.join(p.get('authors',[]))}\nCategory: {p['primary_category']}\nDate: {p['published_at'][:10]}\nAbstract: {p.get('abstract','')}\nURL: {p['url']}"
            for p in data["arxiv_papers"]
        ])
        sections.append(f"## ARXIV PAPERS\n{papers_text}")

    # ── Tweets ───────────────────────────────────────────────────
    if data.get("tweets"):
        tweets_text = "\n\n".join([
            f"@{t['handle']} ({t['published_at'][:10]})\n{t.get('text','')}\n{t.get('url','')}"
            for t in data["tweets"]
        ])
        sections.append(f"## TWEETS FROM AI LEADERS\n{tweets_text}")

    raw_data = "\n\n---\n\n".join(sections)
    next_edition = (datetime.datetime.strptime(end, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime("%B %d, %Y")

    return f"""Generate the AI Weekly Newsletter for the week of {start} to {end}.

Use EXACTLY this structure:

---

# 🤖 AI Weekly — Week of {start}

*Your dual-layer briefing on everything happening in AI this week.*

---

## This Week at a Glance
[2-3 sentence editorial summary. What story does this week tell overall?]

---

## 🚀 Model Releases & Provider Updates
### The Quick Take
[Bullet points]
### 🔬 Deeper Dive
[Technical explanation with analogies]

---

## 📚 Research Highlights (arXiv)
### The Quick Take
[4-6 most significant papers as bullet points]
### 🔬 Deeper Dive
[Plain English explanation of 1-2 most important papers]

---

## 🏢 AI in Business & Industry
### The Quick Take
[Bullet points]
### 🔬 Deeper Dive
[Broader trends and implications]

---

## 🛠️ AI Tools & Products
### The Quick Take
[Bullet points]
### 🔬 Deeper Dive
[What does tooling evolution tell us about where the field is heading?]

---

## 🐦 From the AI Community
### Notable Discussions This Week
[3-5 notable tweets — summarise and explain why interesting. Include handle and link.]

---

## 📌 One to Watch
[One emerging trend or idea that deserves attention. 1 paragraph.]

---

*Next edition: {next_edition}*

---

*AI Weekly is an independent newsletter. Not financial or investment advice.*

---

RAW DATA:

{raw_data}

Rules:
- Only use content from the data above. Do not hallucinate.
- If a section has no data write "No significant updates this week."
- Prioritise quality over quantity. Surface surprising or important stories.
- Always explain WHY something matters, not just WHAT happened.
- Format URLs as markdown links wherever available.
"""


def generate_newsletter(data: Dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = build_user_prompt(data)

    max_retries = 5
    base_wait = 60  # seconds

    for attempt in range(max_retries):
        try:
            print(f"   Sending to Claude (attempt {attempt + 1}/{max_retries})...")

            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            newsletter = message.content[0].text
            print(f"   ✓ Generated ({message.usage.output_tokens} output tokens, {message.usage.input_tokens} input tokens)")
            return newsletter

        except anthropic.RateLimitError as e:
            if attempt == max_retries - 1:
                raise  # Out of retries, let it fail loudly

            wait = base_wait * (2 ** attempt)  # 60s, 120s, 240s, 480s
            print(f"   ⏳ Rate limit hit — waiting {wait}s before retry...")
            time.sleep(wait)

        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}") from e
