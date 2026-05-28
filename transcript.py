from youtube_transcript_api import YouTubeTranscriptApi
from config import ALLOWED_LANGS
from helpers import clean_url, extract_video_id

LANGUAGE_VARIANTS = {
    "ar": ["ar", "ar-TN", "ar-MA", "ar-EG", "ar-SA"],
    "fr": ["fr", "fr-FR", "fr-BE"],
    "en": ["en", "en-US", "en-GB"],
}


def check_captions_available(url: str, lang_code: str) -> tuple:
    """Check if captions exist for the given language, trying variants as fallback.

    Returns (True, matched_code) or (False, None).
    """
    url = clean_url(url)
    video_id = extract_video_id(url)
    ytt_api = YouTubeTranscriptApi()
    variants = LANGUAGE_VARIANTS.get(lang_code, [lang_code])
    for code in variants:
        try:
            ytt_api.fetch(video_id, languages=[code])
            return (True, code)
        except Exception:
            continue
    return (False, None)


def get_available_langs(url: str) -> list:
    """Return list of (code, label) tuples for available subtitles matching ALLOWED_LANGS."""
    url = clean_url(url)
    video_id = extract_video_id(url)
    ytt_api = YouTubeTranscriptApi()
    transcript_list = ytt_api.list(video_id)
    found = []
    seen_codes = set()
    for transcript in transcript_list:
        code = transcript.language_code
        if code in ALLOWED_LANGS and code not in seen_codes:
            found.append((code, ALLOWED_LANGS[code]))
            seen_codes.add(code)
    return found


def fetch_transcript(url: str, lang: str) -> list:
    """Fetch transcript segments as (start_sec, text) tuples via youtube-transcript-api."""
    video_id = extract_video_id(url)
    ytt_api = YouTubeTranscriptApi()
    snippets = ytt_api.fetch(video_id, languages=[lang])
    segments = []
    for snippet in snippets:
        text = snippet.text.strip()
        if text:
            segments.append((snippet.start, text))
    return segments


def format_transcript(segments: list, break_every: int = 10) -> str:
    """Join transcript segments into plain text, inserting line breaks every N seconds."""
    if not segments:
        return ""
    result = []
    last_break_time = segments[0][0]
    for start_sec, text in segments:
        if start_sec - last_break_time >= break_every:
            result.append("\n")
            last_break_time = start_sec
        result.append(text)
    return " ".join(result)
