import os
import subprocess
import sys
import logging
from config import YTDLP_PATH, TEST_MODE

logger = logging.getLogger(__name__)
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def download_audio(url: str, out_dir: str) -> str:
    """Download audio from a YouTube video via yt-dlp. Returns path to the MP3 file."""
    os.makedirs(out_dir, exist_ok=True)
    out_template = os.path.join(out_dir, "audio.%(ext)s")
    audio_path = os.path.join(out_dir, "audio.mp3")

    if TEST_MODE and os.path.exists(audio_path):
        logger.info("Test mode: reusing existing audio — %s", audio_path)
        return audio_path

    cmd = [
        YTDLP_PATH,
        "--extract-audio",
        "--audio-format", "mp3",
        "--format", "bestaudio",
        "--output", out_template,
        "--no-playlist",
    ]
    if TEST_MODE:
        cmd += ["--download-sections", "*0:00-5:00"]
    cmd.append(url)
    logger.info("Downloading audio: %s", url)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            creationflags=_SUBPROCESS_FLAGS)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    if not os.path.exists(audio_path):
        raise FileNotFoundError("Audio file not found after download.")
    logger.info("Audio saved: %s", audio_path)
    return audio_path


def transcribe_with_whisper(audio_path: str, lang: str) -> str:
    """Transcribe an audio file using faster-whisper (CPU, medium model)."""
    from faster_whisper import WhisperModel
    import gc
    base_lang = lang.split("-")[0].lower()
    logger.info("Loading Whisper model...")
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    logger.info("Model loaded. Starting transcription...")
    segments, info = model.transcribe(audio_path, language=base_lang,
                                      beam_size=1, vad_filter=True)
    logger.info("Detected language: %s (%.0f%%)", info.language,
                info.language_probability * 100)
    lines = []
    last_break_time = 0.0
    for seg in segments:
        if seg.start - last_break_time >= 10:
            lines.append("\n")
            last_break_time = seg.start
        lines.append(seg.text.strip())
    result = " ".join(lines)
    del segments, info, model
    gc.collect()
    logger.info("Transcription complete — %d chars.", len(result))
    return result


def get_video_duration(url: str) -> float:
    """Fetch the video duration in seconds via yt-dlp."""
    cmd = [YTDLP_PATH, "--print", "duration", "--no-playlist", url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            creationflags=_SUBPROCESS_FLAGS)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return float(result.stdout.strip())
