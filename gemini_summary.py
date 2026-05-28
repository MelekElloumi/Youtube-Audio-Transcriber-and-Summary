import os
import time
import logging
from google import genai
from config import (
    GEMINI_API_KEY, GEMINI_MODEL, TEST_MODE,
    SUMMARY_PROMPT_PATH, CUSTOM_PROMPT_PATH, LANGUAGE_NAMES,
)

logger = logging.getLogger(__name__)


def summarize_with_gemini(transcription: str, lang: str, prompt_text: str = None) -> str:
    """Send the transcript to Gemini with a prompt template. Retries on 503."""
    if prompt_text:
        prompt_template = prompt_text
    elif os.path.exists(CUSTOM_PROMPT_PATH):
        with open(CUSTOM_PROMPT_PATH, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    else:
        with open(SUMMARY_PROMPT_PATH, "r", encoding="utf-8") as f:
            prompt_template = f.read()

    if TEST_MODE:
        transcription = transcription[:1000]

    base_lang = lang.split("-")[0].lower()
    language_name = LANGUAGE_NAMES.get(base_lang, "Arabic")

    full_prompt = prompt_template.replace("[LANGUAGE]", language_name)
    full_prompt = full_prompt.replace("[INSERT TRANSCRIPTION TEXT HERE]", transcription)

    client = genai.Client(api_key=GEMINI_API_KEY)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(model=GEMINI_MODEL, contents=full_prompt)
            if not response.text:
                raise RuntimeError("Gemini returned an empty response.")
            return response.text
        except Exception as e:
            if attempt < max_retries and "503" in str(e):
                logger.warning("Gemini unavailable (attempt %d/%d). Retrying in 5s...",
                               attempt, max_retries)
                time.sleep(5)
            else:
                raise
