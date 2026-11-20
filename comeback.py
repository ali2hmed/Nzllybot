"""Tell recent users the bot is back after it was cut off from Telegram for a while.

Every minute the bot checks it can reach Telegram and saves the time in bot.db. When a
check works after a long gap (a restart, a blocked network, a dead proxy), everyone who
used the bot in the week before the outage gets a short "I'm back" message.
"""

import asyncio
import logging
import os
import time

from pyrogram.errors import FloodWait, RPCError
from pyrogram.raw.functions.updates import GetState

log = logging.getLogger(__name__)

CHECK_EVERY = 60  # seconds
DOWN_FOR = 10 * 60  # only announce outages at least this long
ACTIVE_WITHIN = 7 * 86400  # who hears about it: users seen this long before the outage
ANNOUNCE_GAP = 6 * 3600  # never announce more often than this
STUCK_FOR = 5 * 60  # restart the bot when Telegram can't be reached for this long


def _meta(db, key):
    row = db.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return int(row[0]) if row else 0


def _set_meta(db, key, value):
    with db.conn:
        db.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(int(value))))


async def _announce(bot, db, text_for, down_since):
    users = db.conn.execute(
        "SELECT id, lang FROM users WHERE last_seen >= ?", (down_since - ACTIVE_WITHIN,)
    ).fetchall()
    log.info("Back after %d min, telling %d user(s)", (time.time() - down_since) // 60, len(users))
    sent = 0
    for user_id, lang in users:
        while True:
            try:
                await bot.send_message(user_id, text_for(lang))
                sent += 1
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except RPCError:  # blocked the bot, deleted account, ...
                break
        await asyncio.sleep(0.1)  # stay far below Telegram's 30 messages a second
    log.info("Told %d user(s) the bot is back", sent)


async def watch(bot, db, text_for):
    """Run forever. text_for(lang) returns the message for a user's language."""
    reached = time.time()  # last time this process reached Telegram
    while True:
        try:
            await asyncio.wait_for(bot.invoke(GetState()), 30)
        except Exception:  # still offline; try again next minute
            if time.time() - reached >= STUCK_FOR:
                # The connection can get stuck after the proxy drops. Docker starts us again fresh.
                log.warning("Can't reach Telegram for %d min, restarting", STUCK_FOR // 60)
                os._exit(1)
            await asyncio.sleep(CHECK_EVERY)
            continue
        now = reached = time.time()
        last_ok = _meta(db, "online_at")
        _set_meta(db, "online_at", now)
        if last_ok and now - last_ok >= DOWN_FOR and now - _meta(db, "back_sent_at") >= ANNOUNCE_GAP:
            _set_meta(db, "back_sent_at", now)
            await _announce(bot, db, text_for, last_ok)
            _set_meta(db, "online_at", time.time())
        await asyncio.sleep(CHECK_EVERY)
