import re


def clean_url(url: str) -> str:
    """Strip playlist params from youtube.com URLs and query strings from youtu.be URLs."""
    return url.split("?")[0] if "youtu.be/" in url else re.sub(r"&list=[^&]+", "", url)


def extract_video_id(url: str) -> str:
    """Extract the video ID from a youtube.com or youtu.be URL."""
    match = re.match(r'(?:https?://)?youtu\.be/([^?&]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'[?&]v=([^&]+)', url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")
