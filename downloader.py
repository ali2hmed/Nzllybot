"""Downloading TikTok and Instagram posts at the best quality we can get.

yt-dlp handles videos (TikTok without watermark, Instagram reels and
carousels). gallery-dl handles TikTok photo slideshows.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

URL_RE = re.compile(r"https?://(?:[\w-]+\.)*(?:tiktok\.com|instagram\.com)/[^\s<>\"']+", re.I)
# Optional: a cookies.txt exported from a logged-in Instagram account gives full-size photos.
INSTAGRAM_COOKIES = os.environ.get("INSTAGRAM_COOKIES", "")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".opus"}


@dataclass
class Media:
    path: Path
    kind: str  # "video", "photo" or "audio"
    width: int = 0
    height: int = 0
    duration: int = 0
    thumb: Path | None = None


@dataclass
class Post:
    url: str
    site: str  # "TikTok" or "Instagram"
    author: str = ""
    caption: str = ""
    media: list[Media] = field(default_factory=list)


class DownloadError(Exception):
    """args[0] is the texts.py key of the message to show the user."""


def find_urls(text):
    return [m.group(0).rstrip(".,!?)") for m in URL_RE.finditer(text or "")]


def _cookies(url):
    if "instagram.com" in url and INSTAGRAM_COOKIES and Path(INSTAGRAM_COOKIES).is_file():
        return INSTAGRAM_COOKIES
    return None


def resolve(url):
    """Follow short links like vm.tiktok.com/abc to the real post URL."""
    if not re.match(r"https?://(vm|vt)\.tiktok\.com/|https?://(www\.)?tiktok\.com/t/", url):
        return url
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.geturl()


def cache_key(url):
    """A stable id for a post, so the same post sent twice can be re-sent instantly."""
    if m := re.search(r"tiktok\.com/.*?/(?:video|photo)/(\d+)", url):
        return f"tt:{m[1]}"
    if m := re.search(r"instagram\.com/(?:[\w.]+/)?(?:p|reels?|tv)/([\w-]+)", url):
        return f"ig:{m[1]}"
    return None


def _error_key(message):
    text = str(message).lower()
    if "ip address is blocked" in text:
        return "blocked"
    if "login" in text or "rate-limit" in text or "cookies" in text:
        return "login_needed"
    if "unsupported url" in text:
        return "unsupported"
    if any(w in text for w in ("private", "not available", "unavailable", "404", "does not exist")):
        return "unavailable"
    return "failed"


def _fetch_file(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=60) as response, open(path, "wb") as out:
        while chunk := response.read(1 << 16):
            out.write(chunk)


def _best_thumbnail(entry):
    thumbs = entry.get("thumbnails") or []
    return max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0), default=None)


def _tiktok_formats(entry):
    """TikTok's "audio" format is only the background song, and its sharpest video
    streams often have no sound. Pick the sharpest video and the best stream that
    carries the video's own sound."""
    formats = [f for f in entry.get("formats") or [] if f.get("format_id") not in ("download", "audio")]
    videos = [f for f in formats if f.get("vcodec") != "none"]
    with_sound = [f for f in videos if f.get("acodec") != "none"]
    if not videos or not with_sound:
        return None
    sharpness = lambda f: (f.get("height") or 0, (f.get("vcodec") or "").startswith("h264"), f.get("tbr") or 0)
    return max(videos, key=sharpness), max(with_sound, key=sharpness)


def _download_tiktok(ydl, entry, folder, number):
    def pick(ctx):
        video, sound = _tiktok_formats(ctx)
        yield video
        if sound is not video and (sound.get("height") or 0) < (video.get("height") or 0):
            yield sound  # its sound is added to the sharper video below

    default = ydl.format_selector
    ydl.format_selector = pick
    try:
        done = ydl.process_ie_result(entry, download=True)
    finally:
        ydl.format_selector = default
    files = [Path(d["filepath"]) for d in done.get("requested_downloads") or []]
    if len(files) < 2:
        return files

    picture, audio = files
    out = folder / f"tiktok-{number:02d}.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(picture), "-i", str(audio),
         "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags", "+faststart", str(out)],
        check=True, timeout=300)
    picture.unlink()
    audio.unlink()
    return [out]


def _ytdlp(url, folder, on_progress=None):
    """Runs in a thread: yt-dlp is not async.

    on_progress(fraction) is called with 0..1 for the whole post while files download.
    """
    where = {"index": 0, "count": 1}  # which item of the post is downloading

    def report(done):
        if on_progress:
            on_progress(min((where["index"] + done) / where["count"], 1.0))

    def hook(d):
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if d.get("status") == "downloading" and total:
            report(min(d.get("downloaded_bytes", 0) / total, 1.0))

    options = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "outtmpl": str(folder / "%(autonumber)02d.%(ext)s"),
        # Best video + best audio, highest resolution first, H.264 preferred because
        # every Telegram app can play it. Never the watermarked TikTok file.
        "format": "bv*[format_id!=download]+ba/b[format_id!=download]/bv*+ba/b",
        "format_sort": ["res", "vcodec:h264", "acodec:aac"],
        "merge_output_format": "mp4",
        "postprocessor_args": {"merger": ["-movflags", "+faststart"]},
        "socket_timeout": 30,
        "retries": 3,
        "progress_hooks": [hook],
    }
    if cookies := _cookies(url):
        options["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
        post = Post(
            url=info.get("webpage_url") or url,
            site="Instagram" if "instagram" in (info.get("extractor") or "").lower() else "TikTok",
            author=info.get("uploader") or info.get("channel") or info.get("uploader_id") or "",
            caption=info.get("description") or "",
        )
        entries = list(info.get("entries") or []) if info.get("_type") == "playlist" else [info]
        where["count"] = max(len(entries), 1)
        for number, entry in enumerate(entries, 1):
            where["index"] = number - 1
            if post.site == "TikTok" and _tiktok_formats(entry):
                post.media += [Media(path, "video") for path in _download_tiktok(ydl, entry, folder, number)]
            elif entry.get("formats") or entry.get("_type") in ("url", "url_transparent"):
                done = ydl.process_ie_result(entry, download=True)
                for download in done.get("requested_downloads") or []:
                    post.media.append(Media(Path(download["filepath"]), "video"))
            elif thumb := _best_thumbnail(entry):  # a photo inside an Instagram post
                path = folder / f"{number:02d}.jpg"
                _fetch_file(thumb["url"], path)
                post.media.append(Media(path, "photo"))
            report(1.0)
    return post


async def _gallery_dl(url, folder):
    command = [sys.executable, "-m", "gallery_dl", "-q", "-D", str(folder), "--write-info-json"]
    if cookies := _cookies(url):
        command += ["--cookies", cookies]
    process = await asyncio.create_subprocess_exec(
        *command, url, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

    files = sorted((p for p in folder.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
    post = Post(url=url, site="TikTok" if "tiktok" in url else "Instagram")
    for path in files:
        ext = path.suffix.lower()
        if path.name == "info.json":
            info = json.loads(path.read_text())
            author = info.get("author") or info.get("owner") or {}
            post.author = author.get("nickname") or author.get("uniqueId") or author.get("username") or "" \
                if isinstance(author, dict) else str(author)
            post.caption = info.get("desc") or info.get("description") or ""
        elif ext in VIDEO_EXT:
            post.media.append(Media(path, "video"))
        elif ext in PHOTO_EXT:
            post.media.append(Media(path, "photo"))
        elif ext in AUDIO_EXT:
            post.media.append(Media(path, "audio"))
    if not post.media:
        raise DownloadError(_error_key(stderr.decode(errors="replace")))
    return post


async def _probe(media):
    """Fill in a video's size and length, and make a preview picture for Telegram."""
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", str(media.path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    out, _ = await process.communicate()
    data = json.loads(out or b"{}")
    stream = (data.get("streams") or [{}])[0]
    media.width = stream.get("width") or 0
    media.height = stream.get("height") or 0
    media.duration = int(float((data.get("format") or {}).get("duration") or 0))

    thumb = media.path.with_suffix(".thumb.jpg")
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-y", "-ss", "0", "-i", str(media.path), "-frames:v", "1",
        "-vf", "scale=320:320:force_original_aspect_ratio=decrease", str(thumb),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await process.communicate()
    if thumb.exists():
        media.thumb = thumb


async def fetch(url, folder, on_progress=None):
    """Download one post into `folder`. Raises DownloadError with a friendly reason.

    on_progress(fraction) is called from another thread as the download goes on.
    """
    try:
        url = await asyncio.to_thread(resolve, url)
    except OSError:
        raise DownloadError("unavailable")

    if "tiktok.com" in url and "/photo/" in url:
        post = await _gallery_dl(url, folder)
    else:
        try:
            post = await asyncio.to_thread(_ytdlp, url, folder, on_progress)
        except yt_dlp.utils.DownloadError as e:
            reason = _error_key(e)
            if "tiktok.com" not in url or reason == "blocked":
                raise DownloadError(reason)
            post = await _gallery_dl(url, folder)  # some TikTok posts only gallery-dl can read
        if not post.media:
            raise DownloadError("failed")

    for media in post.media:
        if media.kind == "video":
            await _probe(media)
    return post
