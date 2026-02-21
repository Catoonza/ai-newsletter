"""
Uses the Anthropic API to summarise all collected data into a newsletter.
Model: claude-opus-4-6 (best reasoning for synthesis tasks)
"""

import os
import json
import datetime
import anthropic
from typing import Dict


# ── Newsletter prompt ────────────────────────────────────────────
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
    if data["news_articles"]:
        news_text = "\n\n".join([
            f"Title: {a['title']}\nSource: {a['source_name']}\nDate: {a['published_at'][:10]}\nSummary: {a['description']}\nURL: {a['url']}"
            for a in data["news_articles"][:30]  # Cap at 30
        ])
        sections.append(f"## NEWS ARTICLES\n{news_text}")

    # ── Blog posts ───────────────────────────────────────────────
    if data["blog_posts"]:
        blogs_text = "\n\n".join([
            f"Provider: {p['provider']}\nTitle: {p['title']}\nDate: {p['published_at'][:10]}\nSummary: {p['summary']}\nURL: {p['url']}"
            for p in data["blog_posts"][:25]
        ])
        sections.append(f"## PROVIDER BLOG POSTS\n{blogs_text}")

    # ── arXiv papers ─────────────────────────────────────────────
    if data["arxiv_papers"]:
        papers_text = "\n\n".join([
            f"Title: {p['title']}\nAuthors: {', '.join(p['authors'])}\nCategory: {p['primary_category']}\nDate: {p['published_at'][:10]}\nAbstract: {p['abstract']}\nURL: {p['url']}"
            for p in data["arxiv_papers"][:30]
        ])
        sections.append(f"## ARXIV PAPERS\n{papers_text}")

    # ── Tweets ───────────────────────────────────────────────────
    if data["tweets"]:
        tweets_text = "\n\n".join([
            f"@{t['handle']} ({t['published_at'][:10]}) | 👍{t['stats']['likes']} 🔁{t['stats']['retweets']}\n{t['text']}\n{t['url']}"
            for t in data["tweets"][:40]
        ])
        sections.append(f"## TWEETS FROM AI LEADERS\n{tweets_text}")

    raw_data = "\n\n---\n\n".join(sections)

    return f"""You are generating the AI Weekly Newsletter for the week of {start} to {end}.

Below is all the raw data collected from news APIs, provider blogs, arXiv, and Twitter this week.
Synthesise it into a polished newsletter using EXACTLY this structure:

---

# 🤖 AI Weekly — Week of {end}

*Your dual-layer briefing on everything happening in AI this week.*

---

## This Week at a Glance
[2-3 sentence editorial summary of the week's most important theme(s). What story does this week tell overall?]

---

## 🚀 Model Releases & Provider Updates
### The Quick Take
[Bullet points]
### 🔬 Deeper Dive
[Technical explanation with analogies]

---

## 📚 Research Highlights (arXiv)
### The Quick Take
[Bullet points — pick the 4-6 most significant or interesting papers]
### 🔬 Deeper Dive
[Explain 1-2 of the most important papers in plain English — what did they find, why does it matter?]

---

## 🏢 AI in Business & Industry
### The Quick Take
[Bullet points]
### 🔬 Deeper Dive
[Broader implications — what trends are emerging?]

---

## 🛠️ AI Tools & Products
### The Quick Take
[Bullet points]
### 🔬 Deeper Dive
[What does the evolution of tooling tell us about where the field is heading?]

---

## 🐦 From the AI Community (Twitter/X)
### Notable Discussions This Week
[3-5 notable tweets or threads worth highlighting — summarise them and explain why they're interesting. Include the Twitter handle and link.]

---

## 📌 One to Watch
[One emerging trend, paper, company, or idea that didn't make headlines but deserves attention. 1 paragraph.]

---

*Next edition: {(datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=7)).strftime('%B %d, %Y')}*

---

HERE IS THE RAW DATA TO SYNTHESISE:

{raw_data}

Important instructions:
- Only include content from the provided data. Do not invent or hallucinate.
- If a section has no data, write "No significant updates this week." rather than fabricating content.
- Prioritise quality over quantity. Cut weak stories. Surface surprising or important ones.
- Always explain WHY something matters, not just WHAT happened.
- Ensure that data from multiple sources is synthesised together to identify trends, not just listed separately.
- Spend time sifting through all content to find the most relevant releases and news. Do not just pick the first few items.
- Ensure model releases are checked for over every day in the date range, and using multiple sources.
- Provide URLs as markdown links wherever available.
"""


def generate_newsletter(data: Dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = build_user_prompt(data)

    print("   Sending to Claude (this may take 30-60 seconds)...")

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt}
        ],
    )

    newsletter = message.content[0].text

    print(f"   ✓ Generated ({message.usage.output_tokens} tokens used)")

    return newsletter
