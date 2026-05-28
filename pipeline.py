import os
import logging
import threading
from helpers import clean_url
from transcript import fetch_transcript, format_transcript
from whisper_transcribe import download_audio, transcribe_with_whisper
from gemini_summary import summarize_with_gemini
from notion_api import parse_gemini_markdown, prepend_url_block, create_notion_page

logger = logging.getLogger(__name__)


def run_pipeline(url, lang_code, video_folder, use_whisper,
                 notion_page_id, on_progress, on_done, on_error,
                 prompt_text=None):
    """Run the full transcription-to-Notion pipeline in a background thread.

    Args:
        url: YouTube video URL.
        lang_code: Language code for transcription.
        video_folder: Full path to the per-video output folder.
        use_whisper: True for Whisper transcription, False for subtitles.
        notion_page_id: Notion page ID to create under, or None to skip Notion.
        on_progress: Callback(pct: int, message: str).
        on_done: Callback(result: dict) with keys 'folder' and 'notion_url'.
        on_error: Callback(message: str).
        prompt_text: Raw prompt template text, or None to use default file.
    """
    def worker():
        try:
            url_clean = clean_url(url)
            os.makedirs(video_folder, exist_ok=True)
            has_notion = notion_page_id is not None

            # ── Step 1: Transcription ───────────────────────────────
            if use_whisper:
                on_progress(0, "Downloading audio...")
                audio_path = download_audio(url_clean, video_folder)

                p_transcribe_start = 10 if has_notion else 15
                on_progress(p_transcribe_start, "Transcribing with Whisper...")
                text = transcribe_with_whisper(audio_path, lang_code)
                p_transcribe_done = 55 if has_notion else 60
            else:
                on_progress(0, "Fetching subtitles...")
                segments = fetch_transcript(url_clean, lang_code)
                text = format_transcript(segments)
                p_transcribe_done = 20 if has_notion else 25

            on_progress(p_transcribe_done, "Transcript ready.")
            logger.info("Transcript length: %d chars", len(text))

            # Save transcript
            transcript_path = os.path.join(video_folder, "transcript.txt")
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(f"YouTube Video URL: {url_clean}\n\n")
                f.write(text)
            logger.info("Transcript saved: %s", transcript_path)

            # ── Step 2: Summarize ───────────────────────────────────
            p_summary_start = p_transcribe_done + 5
            on_progress(p_summary_start, "Summarizing with Gemini...")
            summary = summarize_with_gemini(text, lang_code, prompt_text=prompt_text)

            summary_path = os.path.join(video_folder, "summary.md")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)
            logger.info("Summary saved: %s", summary_path)

            p_summary_done = 70 if (use_whisper and has_notion) else \
                             80 if (not use_whisper and has_notion) else 95
            # Correct values per plan:
            # subtitle+notion: 70, whisper+notion: 80, either without notion: 95
            if has_notion:
                p_summary_done = 70 if not use_whisper else 80
            else:
                p_summary_done = 95
            on_progress(p_summary_done, "Summary saved.")

            # ── Step 3: Notion (optional) ───────────────────────────
            notion_url = None
            if has_notion:
                on_progress(p_summary_done + 5, "Creating Notion page...")
                title, blocks = parse_gemini_markdown(summary)
                blocks = prepend_url_block(url_clean, blocks)
                notion_url = create_notion_page(notion_page_id, title, blocks)
                on_progress(95, "Notion page created.")
                logger.info("Notion page created: %s", notion_url)

            on_progress(100, "Done!")
            on_done({"folder": video_folder, "notion_url": notion_url})

        except Exception as e:
            logger.exception("Pipeline error")
            on_error(f"{type(e).__name__}: {e}")

    threading.Thread(target=worker, daemon=True).start()
