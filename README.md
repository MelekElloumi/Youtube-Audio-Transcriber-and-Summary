# YT Transcriber

A Tkinter desktop app (Windows) that fetches YouTube transcripts, summarizes them with Google Gemini, and creates Notion pages.

## Features

- **Subtitle transcription** — fetches available subtitles via `youtube-transcript-api` (no API key needed)
- **Whisper transcription** — optional local CPU transcription using `faster-whisper` for videos without subtitles
- **Gemini summarization** — sends the transcript to Google Gemini with a customizable prompt
- **Notion integration** — creates a formatted Notion page with the summary and video link
- **Notion browser** — navigate your Notion pages to pick a destination, or create new category pages
- **Language support** — Arabic (+ regional variants), French, and English

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `NOTION_TOKEN` | [Notion Integrations](https://www.notion.so/my-integrations) |
| `NOTION_PARENT_PAGE_ID` | ID of your root Notion page (from the page URL) |

> **Gemini free tier:** `gemini-2.5-flash` is limited to **5 requests/day** on the free tier.

### 3. Run

```bash
python app.py
```

### 4. Whisper mode (optional)

Install `faster-whisper` and `yt-dlp` if you need to transcribe videos without subtitles:

```bash
pip install faster-whisper yt-dlp
```

## Project structure

```
├── app.py                # Entry point (Tkinter window)
├── wizard.py             # 8-screen transcription wizard
├── theme.py              # Dark theme colors and widget helpers
├── config.py             # Paths, API keys, language constants
├── helpers.py            # URL utilities
├── transcript.py         # youtube-transcript-api integration
├── whisper_transcribe.py # Whisper audio transcription
├── gemini_summary.py     # Gemini API summarization
├── notion_api.py         # Notion page creation and browser
├── pipeline.py           # Pipeline orchestration
├── prompts/              # Prompt templates
├── .env.example          # Environment variable template
└── requirements.txt
```
