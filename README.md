# Nzlly Bot 📥

[@Nzllybot](https://t.me/Nzllybot) is a Telegram bot that downloads TikTok and Instagram videos and photos in the best quality available,
in English and Arabic. TikTok videos come without the watermark.

Send it a link in private, or use `/dl <link>` in a group.

## Run it

1. Copy `.env.example` to `.env` and fill in your keys.
2. `docker compose up -d --build`

Messages are in `texts.py`. For full-size Instagram photos and videos, put a `cookies.txt` from a logged-in
Instagram account in `data/` and set `INSTAGRAM_COOKIES=/data/cookies.txt`.

Made by [@ali2hmed](https://t.me/ali2hmed) · [@aliahmedbots](https://t.me/aliahmedbots)
