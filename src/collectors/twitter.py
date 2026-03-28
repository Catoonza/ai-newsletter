"""
Fetches recent AI discussion from Twitter/X profiles.

Strategy: ntscraper / Nitter is effectively dead (all public instances down).
Instead we use web search via the Anthropic API's web search tool to find
recent posts from key AI figures. This is reliable, free, and requires no
Twitter API credentials.
"""

import os
import json
import datetime
import anthropic
from typing import List, Dict


# Profiles and topics to search for
AI_FIGURES = [
    ("Sam Altman", "sama"),
    ("Demis Hassabis", "demishassabis"),
    ("Andrej Karpathy", "karpathy"),
    ("Yann LeCun", "ylecun"),
    ("Dario Amodei", "darioamodei"),
    ("François Chollet", "fchollet"),
    ("Jim Fan", "jimfan"),
    ("Gary Marcus", "GaryMarcus"),
    ("Shawn Wang", "swyx"),
    ("Emad Mostaque", "EMostaque"),
]


def fetch_twitter_posts(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    """
    Uses Claude with web search to find notable recent posts/statements
    from key AI figures on Twitter/X.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⚠️  ANTHROPIC_API_KEY not set — skipping Twitter fetch")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    start_str = start_date.strftime("%B %d, %Y")
    end_str = end_date.strftime("%B %d, %Y")

    figures_list = "\n".join([f"- {name} (@{handle})" for name, handle in AI_FIGURES])

    prompt = f"""Search Twitter/X for notable posts from these AI figures between {start_str} and {end_str}:

{figures_list}

For each person, find their most notable or discussed tweet/post from this week.
Focus on posts about: AI model releases, research findings, industry commentary, 
predictions, or anything that sparked significant discussion.

Return your findings as a JSON array with this exact structure:
[
  {{
    "handle": "username",
    "name": "Full Name",
    "text": "the tweet content or a close paraphrase",
    "url": "https://x.com/... or empty string if not found",
    "published_at": "YYYY-MM-DD",
    "why_notable": "one sentence on why this post matters"
  }}
]

Return ONLY the JSON array, no other text. If you cannot find notable posts for 
someone this week, skip them. Only include genuinely interesting or impactful posts."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text content from response
        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        # Parse JSON
        clean = full_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("```").strip()

        posts_raw = json.loads(clean)

        # Normalise into our standard format
        tweets = []
        for p in posts_raw:
            tweets.append({
                "source": "twitter",
                "handle": p.get("handle", ""),
                "text": p.get("text", "") + (f"\n\n💡 {p['why_notable']}" if p.get("why_notable") else ""),
                "url": p.get("url", ""),
                "published_at": p.get("published_at", end_date.strftime("%Y-%m-%d")),
                "stats": {"likes": 0, "retweets": 0, "comments": 0},
            })

        return tweets

    except json.JSONDecodeError as e:
        print(f"   ⚠️  Could not parse Twitter search results as JSON: {e}")
        return []
    except Exception as e:
        print(f"   ⚠️  Twitter web search failed: {e}")
        return []
