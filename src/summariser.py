import os
import re
import time
import json
import datetime
import anthropic
from typing import Dict

def _clean_source_name(url: str) -> str:
    # Extract domain name
    domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0].lower()
    
    # Mapping of common domains to clean names
    mapping = {
        "openai.com": "OpenAI Blog",
        "anthropic.com": "Anthropic News",
        "deepmind.google": "Google DeepMind",
        "blog.google": "Google Blog",
        "techcrunch.com": "TechCrunch",
        "venturebeat.com": "VentureBeat",
        "arxiv.org": "arXiv",
        "twitter.com": "Twitter/X",
        "x.com": "Twitter/X",
        "github.com": "GitHub",
        "huggingface.co": "Hugging Face",
        "aws.amazon.com": "AWS Blog",
        "blogs.nvidia.com": "NVIDIA Blog",
        "nvidia.com": "NVIDIA",
        "cohere.com": "Cohere Blog",
        "mistral.ai": "Mistral AI",
        "meta.com": "Meta AI",
    }
    
    for key, value in mapping.items():
        if key in domain:
            return value
            
    # Default fallback: domain name with capitalized components (e.g. blog.openai.com -> Blog OpenAI)
    parts = domain.split('.')
    if len(parts) >= 2:
        name = parts[-2]
    else:
        name = domain
    return name.capitalize()

SYSTEM_PROMPT = """You are an expert AI journalist and researcher.
You write a weekly AI newsletter for a dual audience:
- Non-technical readers who want clear, jargon-free summaries of what happened and why it matters
- Technical readers who want depth, nuance, and understanding of the underlying mechanisms

You must submit the newsletter content using the `publish_newsletter` tool.

For each section entry (bullet point), you must explain the topic clearly and list the specific URLs from the raw data that support this story. Never omit source links - every entry must be backed by the actual source URLs.

For the 'From the AI Community' section, you MUST only summarize tweets from the provided tweets dataset (TWEETS FROM AI LEADERS) and include the tweet author's handle and link. Do not include news articles, provider blog posts, or research papers in this section.

Your writing is precise, neutral, insightful, and never hype-driven.
You skip anything that is not meaningfully new or interesting.
You synthesise across sources to identify patterns."""


def build_user_prompt(data: Dict) -> str:
    start = data["date_range"]["start"][:10]
    end = data["date_range"]["end"][:10]

    sections = []

    # — News articles
    if data.get("news_articles"):
        news_text = "\n\n".join([
            f"Title: {a['title']}\nSource: {_clean_source_name(a['url'])}\nDate: {a['published_at'][:10]}\nSummary: {a.get('description','')}\nURL: {a['url']}"
            for a in data["news_articles"]
        ])
        sections.append(f"## NEWS ARTICLES\n{news_text}")

    # — Blog posts
    if data.get("blog_posts"):
        blogs_text = "\n\n".join([
            f"Provider: {_clean_source_name(p['url'])}\nTitle: {p['title']}\nDate: {p['published_at'][:10]}\nSummary: {p.get('summary','')}\nURL: {p['url']}"
            for p in data["blog_posts"]
        ])
        sections.append(f"## PROVIDER BLOG POSTS\n{blogs_text}")

    # — arXiv papers
    if data.get("arxiv_papers"):
        papers_text = "\n\n".join([
            f"Title: {p['title']}\nAuthors: {', '.join(p.get('authors', []))}\nCategory: {p['primary_category']}\nDate: {p['published_at'][:10]}\nAbstract: {p.get('abstract','')}\nURL: {p['url']}"
            for p in data["arxiv_papers"]
        ])
        sections.append(f"## ARXIV PAPERS\n{papers_text}")

    # — Tweets
    if data.get("tweets"):
        tweets_text = "\n\n".join([
            f"@{t['handle']} ({t['published_at'][:10]})\n{t.get('text','')}\n{t.get('url','')}"
            for t in data["tweets"]
        ])
        sections.append(f"## TWEETS FROM AI LEADERS\n{tweets_text}")

    raw_data = "\n\n---\n\n".join(sections)

    return f"""Generate the AI Weekly Newsletter for the week of {start} to {end}.

RAW DATA:

{raw_data}

Rules:
- Only use content from the data above. Do not hallucinate.
- Prioritise quality over quantity. Surface surprising or important stories.
- Always explain WHY something matters, not just WHAT happened.
- For each entry in any section, extract the associated source URLs from the RAW DATA and pass them in the urls array.
"""



def json_to_markdown(js: Dict, start_date: str, end_date: str, next_edition: str) -> str:
    md = []
    md.append(f"# 🤖 AI Weekly – Week of {start_date}")
    md.append("")
    md.append("*Your dual-layer briefing on everything happening in AI this week.*")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## This Week at a Glance")
    md.append("")
    md.append(js.get("week_summary", ""))
    md.append("")
    md.append("---")
    md.append("")
    
    # Helper to render standard sections
    def render_section(title, heading_prefix, entries):
        md.append(f"{heading_prefix} {title}")
        md.append("")
        md.append("### The Quick Take")
        md.append("")
        if not entries:
            md.append("No significant updates this week.")
        else:
            for entry in entries:
                text = entry.get("text", "").strip()
                urls = entry.get("urls", [])
                links = [f"[{_clean_source_name(url)}]({url})" for url in urls if url]
                links_str = ", ".join(links)
                if links_str:
                    md.append(f"- {text} ({links_str})")
                else:
                    md.append(f"- {text}")
        md.append("")
        md.append("---")
        md.append("")

    render_section("Model Releases & Provider Updates", "## 🚀", js.get("models_section", []))
    render_section("Research Highlights (arXiv)", "## 📚", js.get("research_section", []))
    render_section("AI in Business & Industry", "## 💼", js.get("industry_section", []))
    render_section("AI Tools & Products", "## 🛠️", js.get("tools_section", []))
    
    # Community Section
    md.append("## 🐦 From the AI Community")
    md.append("")
    md.append("### Notable Discussions This Week")
    md.append("")
    community_entries = js.get("community_section", [])
    if not community_entries:
        md.append("No significant updates this week.")
    else:
        for entry in community_entries:
            text = entry.get("text", "").strip()
            urls = entry.get("urls", [])
            links = [f"[{_clean_source_name(url)}]({url})" for url in urls if url]
            links_str = ", ".join(links)
            if links_str:
                md.append(f"- {text} ({links_str})")
            else:
                md.append(f"- {text}")
    md.append("")
    md.append("---")
    md.append("")
    
    # One to Watch Section
    watch = js.get("one_to_watch", {})
    md.append("## 🔮 One to Watch")
    md.append("")
    md.append(f"### {watch.get('title', 'Emerging Trend')}")
    md.append("")
    urls = watch.get("urls", [])
    links_str = ", ".join([f"[{_clean_source_name(url)}]({url})" for url in urls if url])
    prose = watch.get("prose", "").strip()
    if links_str:
        md.append(f"{prose} ({links_str})")
    else:
        md.append(prose)
    md.append("")
    md.append("---")
    md.append("")
    
    md.append(f"*Next edition: {next_edition}*")
    md.append("")
    md.append("---")
    md.append("")
    md.append("*AI Weekly is an independent newsletter. Not financial or investment advice.*")
    md.append("")
    md.append("---")
    
    return "\n".join(md)



PUBLISH_NEWSLETTER_TOOL = {
    "name": "publish_newsletter",
    "description": "Publish the weekly AI newsletter with structured sections and source links.",
    "input_schema": {
        "type": "object",
        "properties": {
            "week_summary": {
                "type": "string",
                "description": "A 2-3 sentence editorial summary of the week's overall AI narrative."
            },
            "models_section": {
                "type": "array",
                "description": "List of entries for the Model Releases & Provider Updates section.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "A bullet point summary in plain English, explaining what happened and why it matters. Do not include markdown links inside the text."
                        },
                        "urls": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "uri"
                            },
                            "description": "The specific source URLs from the raw data supporting this bullet point."
                        }
                    },
                    "required": ["text", "urls"]
                }
            },
            "research_section": {
                "type": "array",
                "description": "List of entries for the Research Highlights (arXiv) section.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "A bullet point summary of the paper in plain English: what they did and why it matters."
                        },
                        "urls": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "uri"
                            },
                            "description": "The arXiv paper URLs supporting this entry."
                        }
                    },
                    "required": ["text", "urls"]
                }
            },
            "industry_section": {
                "type": "array",
                "description": "List of entries for the AI in Business & Industry section.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "A bullet point summary of corporate announcements, launches, or updates and why they matter."
                        },
                        "urls": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "uri"
                            },
                            "description": "The specific source URLs supporting this entry."
                        }
                    },
                    "required": ["text", "urls"]
                }
            },
            "tools_section": {
                "type": "array",
                "description": "List of entries for the AI Tools & Products section.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "A bullet point summary of new tools and developer tooling updates."
                        },
                        "urls": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "uri"
                            },
                            "description": "The specific source URLs supporting this entry."
                        }
                    },
                    "required": ["text", "urls"]
                }
            },
            "community_section": {
                "type": "array",
                "description": "List of entries for the From the AI Community section. You MUST only summarize tweets from the TWEETS FROM AI LEADERS section of the raw data. Do not include news articles, provider blog posts, or research papers.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "A summary of a notable tweet or Twitter/X discussion from AI leaders and researchers, including the author's handle (e.g. '@ylecun')."
                        },
                        "urls": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "uri"
                            },
                            "description": "The specific tweet URL(s) from the tweets dataset supporting this entry."
                        }
                    },
                    "required": ["text", "urls"]
                }
            },
            "one_to_watch": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the emerging trend or project to watch."
                    },
                    "prose": {
                        "type": "string",
                        "description": "A 1-paragraph explanation of the trend/project and why it is important."
                    },
                    "urls": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "format": "uri"
                        },
                        "description": "Associated source URLs for this trend."
                    }
                },
                "required": ["title", "prose", "urls"]
            }
        },
        "required": [
            "week_summary",
            "models_section",
            "research_section",
            "industry_section",
            "tools_section",
            "community_section",
            "one_to_watch"
        ]
    }
}


def generate_newsletter(data: Dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    start = data["date_range"]["start"][:10]
    end = data["date_range"]["end"][:10]
    next_edition = (datetime.datetime.strptime(end, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime("%B %d, %Y")

    user_prompt = build_user_prompt(data)

    max_retries = 5
    base_wait = 60  # seconds

    for attempt in range(max_retries):
        try:
            print(f"🔄 Sending to Claude (attempt {attempt + 1}/{max_retries})...")

            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[PUBLISH_NEWSLETTER_TOOL],
                tool_choice={"type": "tool", "name": "publish_newsletter"}
            )

            # Find tool use block
            tool_use_block = None
            for block in message.content:
                if block.type == "tool_use" and block.name == "publish_newsletter":
                    tool_use_block = block
                    break

            if not tool_use_block:
                raise RuntimeError("Claude response did not contain the publish_newsletter tool call.")

            newsletter_data = tool_use_block.input
            print(f"✅ Generated structured data ({message.usage.output_tokens} output tokens, {message.usage.input_tokens} input tokens)")
            
            # Map structured JSON data to standard markdown string
            markdown_content = json_to_markdown(newsletter_data, start, end, next_edition)
            return markdown_content

        except anthropic.RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            wait = base_wait * (2 ** attempt)
            print(f"⏳ Rate limit hit – waiting {wait}s before retry...")
            time.sleep(wait)

        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}") from e