"""Every message the bot sends, in English and Arabic.

Words in {braces} are filled in by the code, so keep them as they are.
"""

LANGS = ("en", "ar")

CHOOSE_LANG = "🌐 <b>Please choose your language</b>\n🌐 <b>الرجاء اختيار لغتك</b>"

TEXTS = {
    "en": {
        "welcome": (
            "👋 Hey <b>{name}</b>!\n\n"
            "Send me a link from <b>TikTok</b> or <b>Instagram</b> and I'll send you the "
            "video or photos in the best quality available 📥\n\n"
            "✅ TikTok videos without watermark\n"
            "✅ TikTok photo slideshows with their music\n"
            "✅ Instagram reels, posts and carousels\n\n"
            "Just paste a link here 👇\n\n"
            "📣 News: @{channel}\n"
            "👨‍💻 Developer: @{developer}"
        ),
        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "<b>Here:</b> paste a TikTok or Instagram link and wait a few seconds.\n\n"
            "<b>In groups:</b> add me, then send <code>/dl</code> followed by the link:\n"
            "<code>/dl https://www.tiktok.com/@user/video/123</code>\n\n"
            "<b>Supported links</b>\n"
            "• tiktok.com, vm.tiktok.com, vt.tiktok.com\n"
            "• instagram.com/reel, /p, /tv\n\n"
            "Private accounts and stories aren't supported."
        ),
        "send_link": "📎 Send me a TikTok or Instagram link.",
        "downloading": "⏳ Downloading…",
        "uploading": "📤 Sending…",
        "progress": "{bar}  {percent}%",
        "busy": "⏳ Wait a moment, I'm still working on your last link.",
        "unsupported": "🤷 I only support TikTok and Instagram links.",
        "unavailable": "🔒 This post is private, deleted, or not available.",
        "login_needed": "🔒 Instagram didn't let me open this post. It may be private or deleted, or try again in a few minutes.",
        "blocked": "🌍 TikTok doesn't allow this post in the bot's region.",
        "too_big": "📦 This file is bigger than Telegram's 2 GB limit.",
        "failed": "😕 Something went wrong with this link. Please try again later.",
        "lang_set": "✅ Language set to English",
        "btn_group": "➕ Add me to a group",
        "btn_help": "❓ Help",
        "btn_lang": "🌐 Language",
        "btn_channel": "📣 Channel",
        "btn_dev": "👨‍💻 Developer",
        "btn_back": "⬅️ Back",
        "cmd_start": "Main menu",
        "cmd_help": "How to use the bot",
        "cmd_lang": "Change your language",
        "cmd_dl": "Download a TikTok or Instagram link",
        "bot_about": "Download TikTok & Instagram videos and photos in the best quality. By @{channel}",
        "bot_description": (
            "📥 Download TikTok and Instagram videos and photos in the best quality.\n\n"
            "✅ TikTok without watermark\n"
            "✅ Reels, posts, carousels and slideshows\n\n"
            "Just send a link.\n\n"
            "📣 News: @{channel}\n"
            "👨‍💻 Developer: @{developer}"
        ),
    },
    "ar": {
        "welcome": (
            "👋 أهلاً <b>{name}</b>!\n\n"
            "أرسل لي رابطاً من <b>تيك توك</b> أو <b>إنستغرام</b> وسأرسل لك "
            "الفيديو أو الصور بأفضل جودة متوفرة 📥\n\n"
            "✅ فيديوهات تيك توك بدون علامة مائية\n"
            "✅ صور تيك توك مع الموسيقى\n"
            "✅ ريلز ومنشورات وألبومات إنستغرام\n\n"
            "فقط الصق الرابط هنا 👇\n\n"
            "📣 الأخبار: @{channel}\n"
            "👨‍💻 المطوّر: @{developer}"
        ),
        "help": (
            "ℹ️ <b>المساعدة</b>\n\n"
            "<b>هنا:</b> الصق رابط تيك توك أو إنستغرام وانتظر بضع ثوانٍ.\n\n"
            "<b>في المجموعات:</b> أضفني، ثم أرسل <code>/dl</code> وبعده الرابط:\n"
            "<code>/dl https://www.tiktok.com/@user/video/123</code>\n\n"
            "<b>الروابط المدعومة</b>\n"
            "• tiktok.com و vm.tiktok.com و vt.tiktok.com\n"
            "• instagram.com/reel و /p و /tv\n\n"
            "الحسابات الخاصة والستوريات غير مدعومة."
        ),
        "send_link": "📎 أرسل لي رابطاً من تيك توك أو إنستغرام.",
        "downloading": "⏳ جارٍ التحميل…",
        "uploading": "📤 جارٍ الإرسال…",
        "progress": "{bar}  {percent}%",
        "busy": "⏳ لحظة، ما زلت أعمل على رابطك السابق.",
        "unsupported": "🤷 أدعم روابط تيك توك وإنستغرام فقط.",
        "unavailable": "🔒 هذا المنشور خاص أو محذوف أو غير متاح.",
        "login_needed": "🔒 إنستغرام لم يسمح لي بفتح هذا المنشور. قد يكون خاصاً أو محذوفاً، أو حاول بعد دقائق.",
        "blocked": "🌍 تيك توك لا يسمح بهذا المنشور في منطقة البوت.",
        "too_big": "📦 هذا الملف أكبر من حد تيليجرام (2 جيجابايت).",
        "failed": "😕 حدث خطأ مع هذا الرابط. حاول مرة أخرى لاحقاً.",
        "lang_set": "✅ تم اختيار اللغة العربية",
        "btn_group": "➕ أضفني إلى مجموعة",
        "btn_help": "❓ المساعدة",
        "btn_lang": "🌐 اللغة",
        "btn_channel": "📣 القناة",
        "btn_dev": "👨‍💻 المطوّر",
        "btn_back": "⬅️ رجوع",
        "cmd_start": "القائمة الرئيسية",
        "cmd_help": "طريقة استخدام البوت",
        "cmd_lang": "تغيير اللغة",
        "cmd_dl": "تحميل رابط تيك توك أو إنستغرام",
        "bot_about": "حمّل فيديوهات وصور تيك توك وإنستغرام بأفضل جودة. من @{channel}",
        "bot_description": (
            "📥 حمّل فيديوهات وصور تيك توك وإنستغرام بأفضل جودة.\n\n"
            "✅ تيك توك بدون علامة مائية\n"
            "✅ ريلز ومنشورات وألبومات وصور\n\n"
            "فقط أرسل الرابط.\n\n"
            "📣 الأخبار: @{channel}\n"
            "👨‍💻 المطوّر: @{developer}"
        ),
    },
}


RLM = "\u200f"  # invisible right-to-left mark


def t(lang, key, **values):
    text = TEXTS.get(lang, TEXTS["en"])[key]
    text = text.format(**values) if values else text
    if lang == "ar":
        # Telegram decides each line's direction from its first letter, so a line that
        # starts with an emoji or @username can jump to the left. This keeps it right.
        text = "\n".join(RLM + line if line else line for line in text.split("\n"))
    return text
