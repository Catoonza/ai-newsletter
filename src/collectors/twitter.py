"""
Fetches recent tweets from specific AI profiles.

Uses ntscraper — a free library that scrapes public Nitter instances.
No Twitter API key required, but scraping may occasionally be rate-limited.

To use the official Twitter API instead (paid, $100+/month):
  - Set TWITTER_BEARER_TOKEN in your environment
  - Uncomment the twitter_api.py implementation below
"""

import datetime
import os
from typing import List, Dict


# ── Profiles to follow ───────────────────────────────────────────
# Add or remove handles as you like
TWITTER_PROFILES = [
    # AI Lab Leaders
    "sama",           # Sam Altman (OpenAI)
    "demishassabis",  # Demis Hassabis (Google DeepMind)
    "karpathy",       # Andrej Karpathy
    "ylecun",         # Yann LeCun (Meta)
    "goodfellow_ian", # Ian Goodfellow
    "drfeifei",       # Fei-Fei Li
    "EMostaque",      # Emad Mostaque
    "abhi1nandy2",    # Abhishek Thakur (HuggingFace)

    # AI Researchers & Engineers
    "GaryMarcus",     # Gary Marcus (AI critic)
    "fchollet",       # François Chollet (Keras)
    "jimfan",         # Jim Fan (NVIDIA)
    "hardmaru",       # David Ha
    "xlr8harder",     # Sasha Rush

    # AI News & Commentary
    "bentossell",     # Ben Tossell (AI tools)
    "swyx",           # Shawn Wang (AI engineer)
    "hturan",         # AI news

    # Anthropic
    "darioamodei",    # Dario Amodei (Anthropic CEO)
    "danielgross",    # Daniel Gross
]


def fetch_twitter_posts(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    """
    Attempts to fetch tweets using ntscraper.
    Falls back gracefully if the library isn't installed or scraping fails.
    """
    try:
        from ntscraper import Nitter
        return _fetch_with_ntscraper(start_date, end_date)
    except ImportError:
        print("   ⚠️  ntscraper not installed — run: pip install ntscraper")
        print("   ⚠️  Skipping Twitter fetch")
        return []
    except Exception as e:
        print(f"   ⚠️  Twitter scraping failed: {e}")
        return []


def _fetch_with_ntscraper(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    from ntscraper import Nitter

    tweets = []

    # Use a public Nitter instance (ntscraper picks one automatically)
    scraper = Nitter(log_level=0, skip_instance_check=False)

    for handle in TWITTER_PROFILES:
        try:
            results = scraper.get_tweets(handle, mode="user", number=20)

            for tweet in results.get("tweets", []):
                # Parse date
                date_str = tweet.get("date", "")
                try:
                    # ntscraper returns dates like "Feb 19, 2026 · 3:42 PM UTC"
                    # Strip the middle dot separator
                    clean = date_str.replace(" · ", " ").strip()
                    published = datetime.datetime.strptime(clean, "%b %d, %Y %I:%M %p UTC")
                except Exception:
                    continue

                # Filter to date range
                if not (start_date <= published <= end_date):
                    continue

                # Skip retweets (they start with "RT @")
                text = tweet.get("text", "")
                if text.startswith("RT @"):
                    continue

                tweets.append({
                    "source": "twitter",
                    "handle": handle,
                    "text": text,
                    "url": tweet.get("link", ""),
                    "published_at": published.isoformat(),
                    "stats": {
                        "likes": tweet.get("likes", 0),
                        "retweets": tweet.get("retweets", 0),
                        "comments": tweet.get("comments", 0),
                    },
                })

        except Exception as e:
            print(f"   ⚠️  Could not fetch tweets for @{handle}: {e}")

    # Sort by engagement (likes + retweets) descending
    tweets.sort(
        key=lambda x: x["stats"]["likes"] + x["stats"]["retweets"],
        reverse=True,
    )

    return tweets
