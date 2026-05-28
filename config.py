import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths (relative to project root) ────────────────────────────
BASE_DIR = str(Path(__file__).resolve().parent)

TRANSCRIPTIONS_DIR = os.path.join(BASE_DIR, "transcriptions")
LOGS_DIR           = os.path.join(BASE_DIR, "logs")
PROMPTS_DIR        = os.path.join(BASE_DIR, "prompts")

SUMMARY_PROMPT_PATH = os.path.join(PROMPTS_DIR, "summary_prompt.txt")
CUSTOM_PROMPT_PATH  = os.path.join(PROMPTS_DIR, "custom_prompt.txt")
ICON_PATH           = os.path.join(BASE_DIR, "icon.ico")

# ── External tools ───────────────────────────────────────────────
YTDLP_PATH = os.getenv("YTDLP_PATH", "yt-dlp")

# ── API Keys (loaded from .env) ─────────────────────────────────
GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL          = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
NOTION_TOKEN          = os.getenv("NOTION_TOKEN", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")

# ── Settings ─────────────────────────────────────────────────────
TEST_MODE = os.getenv("TEST_MODE", "false").lower() in ("true", "1", "yes")

# ── Language Config ──────────────────────────────────────────────
ALLOWED_LANGS = {
    "ar":    "Arabic",
    "ar-TN": "Arabic (Tunisian)",
    "ar-MA": "Arabic (Moroccan)",
    "ar-EG": "Arabic (Egyptian)",
    "ar-SA": "Arabic (Saudi)",
    "fr":    "French",
    "fr-FR": "French (France)",
    "fr-BE": "French (Belgium)",
    "en":    "English",
    "en-US": "English (US)",
    "en-GB": "English (UK)",
}

WHISPER_LANGS = [
    ("ar", "Arabic"),
    ("fr", "French"),
    ("en", "English"),
]

LANGUAGE_NAMES = {"ar": "Arabic", "fr": "French", "en": "English"}


def setup_logging():
    """Configure file-based logging to logs/ directory."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                os.path.join(LOGS_DIR, "app.log"), encoding="utf-8"
            ),
        ],
    )
