import os
from notion_client import Client as NotionClient
from dotenv import load_dotenv
import config


def validate_notion_credentials() -> tuple:
    """Re-read .env, update config, and test Notion API access.

    Returns (True, "") on success or (False, error_message) on failure.
    """
    load_dotenv(override=True)
    config.NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
    config.NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
    if not config.NOTION_TOKEN or not config.NOTION_PARENT_PAGE_ID:
        return (False, "NOTION_TOKEN or NOTION_PARENT_PAGE_ID not set in .env")
    try:
        notion = NotionClient(auth=config.NOTION_TOKEN)
        notion.blocks.children.list(block_id=config.NOTION_PARENT_PAGE_ID)
        return (True, "")
    except Exception as e:
        return (False, str(e))


def parse_gemini_markdown(markdown_text: str) -> tuple:
    """Parse Gemini's markdown output into a (title, blocks) tuple for the Notion API."""
    lines = markdown_text.strip().split("\n")
    title = "Summary"
    blocks = []
    for line in lines:
        clean = line.strip()
        if clean.startswith("## "):
            title = clean[3:].strip()
        elif clean.startswith("### "):
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": clean[4:].strip()}}]}
            })
        elif clean.startswith("- ") or clean.startswith("  - "):
            content = clean.lstrip(" ").lstrip("-").strip()
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        elif clean:
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": clean}}]}
            })
    return title, blocks


def prepend_url_block(url: str, blocks: list) -> list:
    """Prepend a YouTube URL link block before the summary content."""
    return [
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [
                {"type": "text", "text": {"content": "YouTube URL: "}},
                {"type": "text", "text": {"content": url, "link": {"url": url}}}
            ]}
        }
    ] + blocks


def get_notion_child_pages(page_id: str) -> list:
    """Return list of (id, title) tuples for child pages under the given Notion page."""
    notion = NotionClient(auth=config.NOTION_TOKEN)
    results = notion.blocks.children.list(block_id=page_id).get("results", [])
    return [
        (b["id"], b["child_page"].get("title", "Untitled"))
        for b in results if b.get("type") == "child_page"
    ]


def create_notion_page(parent_page_id: str, title: str, blocks: list) -> str:
    """Create a new Notion page under the given parent with title and content blocks."""
    notion = NotionClient(auth=config.NOTION_TOKEN)
    new_page = notion.pages.create(
        parent={"page_id": parent_page_id},
        properties={"title": [{"text": {"content": title}}]},
        children=blocks[:100]
    )
    return new_page["url"]
