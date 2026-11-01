import asyncio
import contextlib
import html
import logging
import os
import shutil
import signal
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pyrogram import Client, filters, idle
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import FloodWait, MessageNotModified, RPCError
from pyrogram.raw.functions.bots import SetBotInfo
from pyrogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    LinkPreviewOptions,
    ReplyParameters,
)

import downloader
from db import DB
from downloader import DownloadError
from texts import CHOOSE_LANG, LANGS, t

CHANNEL = "aliahmedbots"
DEVELOPER = "ali2hmed"
MAX_LINKS = 5  # per message
MAX_BYTES = 2000 * 1024 * 1024  # Telegram's limit for bots is 2 GB
PARALLEL_DOWNLOADS = 3
RESTART_HOUR = 4  # restart daily at 04:00 so Docker installs the newest yt-dlp/gallery-dl
TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Baghdad"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "."))
TMP_DIR = DATA_DIR / "tmp"
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
PROGRESS_EVERY = 2.5  # seconds between progress bar updates; Telegram limits message edits

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("pyrogram").setLevel(logging.WARNING)
log = logging.getLogger("bot")

bot = Client(
    "downloader-bot",
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"],
    bot_token=os.environ["BOT_TOKEN"],
    parse_mode=ParseMode.HTML,
    workdir=str(DATA_DIR),
)
db = DB(str(DATA_DIR / "bot.db"))
slots = asyncio.Semaphore(PARALLEL_DOWNLOADS)
busy: set[int] = set()  # users with a download in progress


# ---------- helpers ----------

def user_lang(user):
    if user is None:
        return "en"
    return db.get_lang(user.id) or ("ar" if (user.language_code or "").startswith("ar") else "en")


def welcome_text(lang, user):
    return t(lang, "welcome", name=html.escape(user.first_name or ""), channel=CHANNEL, developer=DEVELOPER)


def main_menu(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_group"), url=f"https://t.me/{bot.me.username}?startgroup=true")],
        [InlineKeyboardButton(t(lang, "btn_help"), callback_data="help"),
         InlineKeyboardButton(t(lang, "btn_lang"), callback_data="lang")],
        [InlineKeyboardButton(t(lang, "btn_channel"), url=f"https://t.me/{CHANNEL}"),
         InlineKeyboardButton(t(lang, "btn_dev"), url=f"https://t.me/{DEVELOPER}")],
    ])


def lang_menu():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
        InlineKeyboardButton("🇮🇶 العربية", callback_data="lang:ar"),
    ]])


def back_menu(lang):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="home")]])


def caption_for(post):
    parts = []
    if post.author:
        parts.append(f"👤 <b>{html.escape(post.author)}</b>")
    if post.caption:
        text = post.caption.strip()
        parts.append(html.escape(text if len(text) <= 600 else text[:600] + "…"))
    parts.append(f'🔗 <a href="{html.escape(post.url, quote=True)}">{post.site}</a> · 📥 @{bot.me.username}')
    return "\n\n".join(parts)


# ---------- progress ----------

class Progress:
    """What the status message should show: a stage and how far along it is (0..1)."""

    def __init__(self):
        self.stage = "downloading"
        self.fraction = None  # None until we know, e.g. gallery-dl or albums don't report it

    def set(self, fraction):
        # Called from the download thread too; never go backwards.
        self.fraction = max(fraction, self.fraction or 0.0)

    def next_stage(self, stage):
        self.stage, self.fraction = stage, None

    def upload(self, current, total):
        if total:
            self.set(current / total)

    def text(self, lang):
        text = t(lang, self.stage)
        if self.fraction is None:
            return text
        filled = round(self.fraction * 10)
        bar = "▰" * filled + "▱" * (10 - filled)
        return text + "\n\n" + t(lang, "progress", bar=bar, percent=int(self.fraction * 100))


async def stop(task):
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def show_progress(status, progress, lang):
    """Keep the status message up to date until cancelled."""
    shown = progress.text(lang)
    while True:
        await asyncio.sleep(PROGRESS_EVERY)
        text = progress.text(lang)
        if text == shown:
            continue
        try:
            await status.edit_text(text)
            shown = text
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except RPCError:
            pass


# ---------- sending ----------

def _file_id(message):
    for kind in ("video", "photo", "audio", "document"):
        if media := getattr(message, kind, None):
            return kind, media.file_id
    return None


async def send_items(message, items, caption, progress=None):
    """Send [(kind, file), ...] where file is a path or a Telegram file id.

    Photos and videos go out as albums of up to 10; audio is sent after.
    Returns [(kind, file_id), ...] so the post can be re-sent instantly next time.
    progress(current, total) is called while a single file uploads (albums can't report it).
    """
    visual = [item for item in items if item[0] in ("photo", "video")]
    audio = [item for item in items if item[0] == "audio"]
    sent = []
    first = True

    def extras(item):
        media = item[2] if len(item) > 2 else None
        if item[0] != "video" or media is None:
            return {}
        return dict(width=media.width, height=media.height, duration=media.duration,
                    thumb=str(media.thumb) if media.thumb else None, supports_streaming=True)

    if len(visual) == 1:
        item = visual[0]
        if item[0] == "video":
            msg = await message.reply_video(str(item[1]), caption=caption, progress=progress, **extras(item))
        else:
            msg = await message.reply_photo(str(item[1]), caption=caption, progress=progress)
        sent.append(_file_id(msg))
        first = False
    else:
        for start in range(0, len(visual), 10):
            group = []
            for item in visual[start:start + 10]:
                cap = caption if first else None
                first = False
                if item[0] == "video":
                    group.append(InputMediaVideo(str(item[1]), caption=cap, **extras(item)))
                else:
                    group.append(InputMediaPhoto(str(item[1]), caption=cap))
            messages = await bot.send_media_group(
                message.chat.id, group, message_thread_id=message.message_thread_id,
                reply_parameters=ReplyParameters(message_id=message.id))
            sent += [_file_id(m) for m in messages]

    for item in audio:
        msg = await message.reply_audio(str(item[1]), caption=caption if first else None)
        first = False
        sent.append(_file_id(msg))
    return [s for s in sent if s]


async def download(message, url, lang):
    key = downloader.cache_key(url)
    if key and (cached := db.get_sent(key)):
        try:
            await send_items(message, [tuple(i) for i in cached["items"]], cached["caption"])
            return
        except RPCError as e:
            log.warning("Cached post %s couldn't be re-sent, downloading again: %s", key, e)

    progress = Progress()
    status = await message.reply(progress.text(lang))
    updater = asyncio.create_task(show_progress(status, progress, lang))
    try:
        async with slots:
            with tempfile.TemporaryDirectory(dir=TMP_DIR) as folder:
                post = await downloader.fetch(url, Path(folder), progress.set)
                if any(m.path.stat().st_size > MAX_BYTES for m in post.media):
                    raise DownloadError("too_big")
                progress.next_stage("uploading")
                caption = caption_for(post)
                items = [(m.kind, m.path, m) for m in post.media]
                sent = await send_items(message, items, caption, progress.upload)
        await stop(updater)
        # Short links only get a key after they're resolved, so ask again with the real URL.
        key = downloader.cache_key(post.url) or key
        log.info("Sent %s (%d files)", key or post.url, len(sent))
        if key:
            db.save_sent(key, {"caption": caption, "items": sent})
        await status.delete()
    except DownloadError as e:
        await stop(updater)
        log.info("Couldn't download %s: %s", url, e.args[0])
        await status.edit_text(t(lang, e.args[0]))
    except Exception:
        await stop(updater)
        log.exception("Failed on %s", url)
        await status.edit_text(t(lang, "failed"))


# ---------- commands ----------

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message):
    lang = user_lang(message.from_user)
    if db.get_lang(message.from_user.id) is None:
        return await message.reply(CHOOSE_LANG, reply_markup=lang_menu())
    await message.reply(welcome_text(lang, message.from_user), reply_markup=main_menu(lang),
                        link_preview_options=NO_PREVIEW)


@bot.on_message(filters.command("help"))
async def help_cmd(_, message):
    lang = user_lang(message.from_user)
    markup = back_menu(lang) if message.chat.type == ChatType.PRIVATE else None
    await message.reply(t(lang, "help"), reply_markup=markup, link_preview_options=NO_PREVIEW)


@bot.on_message(filters.command("lang"))
async def lang_cmd(_, message):
    await message.reply(CHOOSE_LANG, reply_markup=lang_menu())


# Any message with a TikTok/Instagram link: in private, with /dl in groups, or any
# group message if privacy mode is turned off in @BotFather.
has_link = filters.create(lambda _, __, m: bool(downloader.find_urls(m.text or m.caption)))


@bot.on_message(has_link & ~filters.via_bot)
async def link_message(_, message):
    lang = user_lang(message.from_user)
    user = message.from_user.id if message.from_user else message.chat.id
    if user in busy:
        return await message.reply(t(lang, "busy"))
    busy.add(user)
    try:
        for url in downloader.find_urls(message.text or message.caption)[:MAX_LINKS]:
            await download(message, url, lang)
    finally:
        busy.discard(user)


@bot.on_message(filters.command("dl"))
async def dl_without_link(_, message):
    await message.reply(t(user_lang(message.from_user), "send_link"))


@bot.on_message(filters.private & ~filters.via_bot & ~filters.service)
async def anything_else(_, message):
    await message.reply(t(user_lang(message.from_user), "send_link"))


# ---------- buttons ----------

@bot.on_callback_query()
async def buttons(_, query):
    data = query.data or ""
    lang = user_lang(query.from_user)
    toast = None
    if data.startswith("lang:"):
        lang = data.split(":", 1)[1]
        if lang not in LANGS:
            return await query.answer()
        db.set_lang(query.from_user.id, lang)
        toast = t(lang, "lang_set")
        if query.message.chat.type == ChatType.PRIVATE:
            text, markup = welcome_text(lang, query.from_user), main_menu(lang)
        else:
            text, markup = toast, None
    elif data == "lang":
        text, markup = CHOOSE_LANG, lang_menu()
    elif data == "help":
        text, markup = t(lang, "help"), back_menu(lang)
    elif data == "home":
        text, markup = welcome_text(lang, query.from_user), main_menu(lang)
    else:
        return await query.answer()
    try:
        await query.edit_message_text(text, reply_markup=markup, link_preview_options=NO_PREVIEW)
    except MessageNotModified:
        pass
    await query.answer(toast)


# ---------- startup ----------

async def setup_profile():
    for lang in LANGS:
        code = "" if lang == "ar" else lang  # Arabic for everyone, English for English apps
        private = [BotCommand(c, t(lang, f"cmd_{c}")) for c in ("start", "help", "lang")]
        groups = [BotCommand(c, t(lang, f"cmd_{c}")) for c in ("dl", "help", "lang")]
        await bot.set_bot_commands(private, scope=BotCommandScopeAllPrivateChats(), language_code=code)
        await bot.set_bot_commands(groups, scope=BotCommandScopeAllGroupChats(), language_code=code)
        await bot.invoke(SetBotInfo(
            lang_code=code,
            about=t(lang, "bot_about", channel=CHANNEL),
            description=t(lang, "bot_description", channel=CHANNEL, developer=DEVELOPER),
        ))


async def daily_restart():
    """Exit once a day when idle; Docker starts the bot again with updated downloaders."""
    while True:
        now = datetime.now(TZ)
        target = now.replace(hour=RESTART_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        while busy:
            await asyncio.sleep(30)
        log.info("Daily restart to update yt-dlp and gallery-dl")
        os.kill(os.getpid(), signal.SIGINT)


async def main():
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    await bot.start()
    try:
        await setup_profile()
    except RPCError as e:
        log.warning("Couldn't set up the bot profile: %s", e)
    restart = asyncio.create_task(daily_restart()) if os.environ.get("DAILY_RESTART") else None
    log.info("@%s is running", bot.me.username)
    await idle()
    if restart:
        restart.cancel()
    await bot.stop()


bot.loop.run_until_complete(main())
