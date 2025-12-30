import asyncio
import logging
import os
import sqlite3
from datetime import datetime, date

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter

# =========================
# LOAD ENV
# =========================
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

if not TOKEN or not OWNER_ID:
    raise RuntimeError("BOT_TOKEN yoki OWNER_ID topilmadi")

# =========================
# BOT
# =========================
dp = Dispatcher()

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("sanoqchi.db")
cursor = conn.cursor()

# cursor.execute(""" DROP TABLE challenges """)

cursor.execute("""
CREATE TABLE IF NOT EXISTS challenges (
    chat_id INTEGER PRIMARY KEY,
    start_date TEXT,
    end_date TEXT,
    announced INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS invites (
    chat_id INTEGER,
    inviter_id INTEGER,
    inviter_name TEXT,
    count INTEGER,
    PRIMARY KEY (chat_id, inviter_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_users (
    user_id INTEGER PRIMARY KEY,
    first_seen TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_groups (
    chat_id INTEGER PRIMARY KEY,
    added_date TEXT
)
""")

conn.commit()

# =========================
# HELPERS
# =========================
def today() -> date:
    return datetime.now().date()


def get_active_challenge(chat_id: int):
    cursor.execute(
        "SELECT start_date, end_date FROM challenges WHERE chat_id=?",
        (chat_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    start = datetime.fromisoformat(row[0]).date()
    end = datetime.fromisoformat(row[1]).date()

    if start <= today() <= end:
        return start, end
    return None


# =========================
# /start
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.chat.type != "private":
        return

    cursor.execute(
        "INSERT OR IGNORE INTO bot_users VALUES (?, ?)",
        (message.from_user.id, datetime.now().isoformat())
    )
    conn.commit()

    await message.answer(
        "📊 Sanoqchi_bot\n\n"
        "👥 Guruhlarda kim nechta odam qo‘shganini hisoblaydi.\n\n"
        "🧑‍💻 Siz:\n"
        "— Statistikani faqat shu chatda ko‘rasiz(/my_stats)\n\n"
        "👮 Adminlar:\n"
        "— Challenge’ni shu chatda boshlaydi\n\n"
        "📖 /help — foydalanish qo‘llanmasi"
    )


# =========================
# /help
# =========================
@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📊 Sanoqchi_bot — adminlar uchun yo‘riqnoma\n\n"

        "🤖 Bot vazifasi:\n"
        "— Challenge davomida guruhga kim nechta odam qo‘shganini hisoblaydi\n\n"

        "⚙️ Botni faollashtirish:\n"
        "1️⃣ Botni guruhga qo‘shing\n"
        "2️⃣ Admin qiling\n"
        "3️⃣ Delete messages ruxsatini bering\n\n"

        "🚀 Challenge qanday boshlanadi?\n"
        "— Admin bot bilan private chatda quyidagi buyruqni yuboradi:\n"
        "/start_challenge CHAT_ID YYYY-MM-DD YYYY-MM-DD\n\n"

        "📌 Misol:\n"
        "/start_challenge -1001234567890 2025-01-01 2025-01-31\n\n"

        "🆔 Chat ID olish:\n"
        "— Guruhda /chat_id yozing\n"
        "— Chat ID faqat adminning bot chatiga yuboriladi\n\n"

        "📊 Statistikalar:\n"
        "— Guruhda ko‘rsatilmaydi\n"
        "📈 /top10 — eng faol 10 ta qatnashchi (bot chatida)"
        "— Har bir user statistikani bot bilan private chatda ko‘radi\n\n"

        "ℹ️ Muhim:\n"
        "— Faqat qo‘lda qo‘shilgan odamlar hisoblanadi\n"
        "— Invite link orqali kirganlar hisobga olinmaydi"
    )



@dp.message(Command("chat_id"))
async def chat_id_handler(message: Message):
    # Faqat guruhda ishlaydi
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    # Admin ekanligini tekshiramiz
    member = await message.bot.get_chat_member(
        message.chat.id,
        message.from_user.id
    )
    if member.status not in ("administrator", "creator"):
        return

    # Adminning private chatiga yuboramiz
    try:
        await message.bot.send_message(
            message.from_user.id,
            f"🆔 Guruh chat_id:\n{message.chat.id}\n\n"
            f"📌 Guruh nomi:\n{message.chat.title}"
        )

    except Exception:
        # Agar private chat ochilmagan bo‘lsa
        await message.reply(
            "❗ Iltimos, avval bot bilan private chatda /start ni bosing.\n"
            "So‘ngra bu buyruqni yana ishlating."
        )
        return

    # Guruhdagi buyruqni o‘chirib tashlaymiz (toza ko‘rinish)
    try:
        await message.delete()
    except Exception:
        pass


@dp.message(Command("top10"))
async def top10_handler(message: Message):
    if message.chat.type != "private":
        return

    # Faol challenge bormi?
    cursor.execute("""
    SELECT chat_id FROM challenges
    WHERE start_date <= ? AND end_date >= ?
    """, (today(), today()))

    row = cursor.fetchone()
    if not row:
        await message.answer(
            "⏸ Hozircha faol challenge yo‘q.\n"
            "🚀 Challenge boshlansa, guruhda e’lon qilinadi."
        )
        return

    chat_id = row[0]

    cursor.execute(
        """
        SELECT inviter_name, count
        FROM invites
        WHERE chat_id=?
        ORDER BY count DESC
        LIMIT 10
        """,
        (chat_id,)
    )
    results = cursor.fetchall()

    if not results:
        await message.answer("📊 Hozircha statistik ma’lumot yo‘q.")
        return

    text = "🏆 TOP 10 qatnashchilar:\n\n"
    for i, (name, count) in enumerate(results, start=1):
        text += f"{i}. {name} — {count} ta\n"

    await message.answer(text)


@dp.message(Command("bot_stats"))
async def bot_stats(message: Message):
    if message.chat.type != "private":
        return

    # Faqat bot egasi ko‘ra oladi
    if message.from_user.id != OWNER_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM bot_users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bot_groups")
    total_groups = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM challenges")
    total_challenges = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(count) FROM invites")
    total_invites = cursor.fetchone()[0] or 0

    await message.answer(
        "🤖 Bot umumiy statistikasi\n\n"
        f"👤 Foydalanuvchilar: {total_users}\n"
        f"👥 Guruhlar: {total_groups}\n"
        f"🚀 Challenge’lar: {total_challenges}\n"
        f"📊 Jami qo‘shilgan odamlar: {total_invites}"
    )



# =========================
# ADMIN → START CHALLENGE
# =========================
@dp.message(Command("start_challenge"))
async def start_challenge(message: Message):
    if message.chat.type != "private":
        return

    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Sizda bu buyruq uchun ruxsat yo‘q.")
        return

    args = message.text.split()
    if len(args) != 4:
        await message.answer(
            "❌ Format:\n"
            "/start_challenge CHAT_ID YYYY-MM-DD YYYY-MM-DD"
        )
        return

    chat_id = int(args[1])
    start_date, end_date = args[2], args[3]

    cursor.execute(
        "REPLACE INTO challenges VALUES (?, ?, ?, 0)",
        (chat_id, start_date, end_date)
    )
    cursor.execute("DELETE FROM invites WHERE chat_id=?", (chat_id,))
    conn.commit()

    await message.answer(
        "✅ Challenge saqlandi\n\n"
        f"📅 {start_date} → {end_date}\n"
        "⏰ Belgilangan vaqtda guruhga e’lon yuboriladi."
    )


# =========================
# ANNOUNCER LOOP
# =========================
async def announce_loop(bot: Bot):
    while True:
        cursor.execute(
            "SELECT chat_id, start_date, end_date, announced, ended FROM challenges"
        )
        rows = cursor.fetchall()

        for chat_id, start_date, end_date, announced, ended in rows:
            start = datetime.fromisoformat(start_date).date()
            end = datetime.fromisoformat(end_date).date()
            today_date = today()

            # 🔔 Challenge BOSHLANDI
            if not announced and today_date >= start:
                await bot.send_message(
                    chat_id,
                    "🚀 Challenge boshlandi!\n\n"
                    "👥 Kim ko‘proq odam qo‘shadi?\n\n"
                    "📊 Statistikani botdan ko‘rishingiz mumkin."
                )
                cursor.execute(
                    "UPDATE challenges SET announced=1 WHERE chat_id=?",
                    (chat_id,)
                )
                conn.commit()

            # 🏁 Challenge TUGADI → NATIJA
            if announced and not ended and today_date > end:
                cursor.execute(
                    """
                    SELECT inviter_name, count
                    FROM invites
                    WHERE chat_id=?
                    ORDER BY count DESC
                    LIMIT 10
                    """,
                    (chat_id,)
                )
                results = cursor.fetchall()

                if results:
                    text = "🏁 Challenge yakunlandi!\n\n"
                    medals = ["🥇", "🥈", "🥉"]

                    for i, (name, count) in enumerate(results):
                        medal = medals[i] if i < 3 else f"{i+1}."
                        text += f"{medal} {name} — {count} ta\n"

                    text += "\n📊 Barcha qatnashchilarga rahmat! 🎉"
                else:
                    text = "🏁 Challenge yakunlandi!\n\n❗ Hech kim qatnashmadi."

                await bot.send_message(chat_id, text)

                cursor.execute(
                    "UPDATE challenges SET ended=1 WHERE chat_id=?",
                    (chat_id,)
                )
                conn.commit()

        await asyncio.sleep(60)



# =========================
# TRACK INVITES
# =========================
@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=True))
async def track_invites(event: ChatMemberUpdated):
    if event.old_chat_member.status != "left":
        return
    if event.new_chat_member.status != "member":
        return

    # Invite link orqali bo‘lsa — hisoblamaymiz
    if event.invite_link:
        return

    inviter = event.from_user
    if not inviter:
        return

    challenge = get_active_challenge(event.chat.id)
    if not challenge:
        return

    cursor.execute(
        "SELECT count FROM invites WHERE chat_id=? AND inviter_id=?",
        (event.chat.id, inviter.id)
    )
    row = cursor.fetchone()

    if row:
        cursor.execute(
            "UPDATE invites SET count = count + 1 WHERE chat_id=? AND inviter_id=?",
            (event.chat.id, inviter.id)
        )
    else:
        cursor.execute(
            "INSERT INTO invites VALUES (?, ?, ?, 1)",
            (event.chat.id, inviter.id, inviter.full_name)
        )

    conn.commit()


# =========================
# /my_stats
# =========================
@dp.message(Command("my_stats"))
async def my_stats(message: Message):
    if message.chat.type != "private":
        return

    cursor.execute("SELECT COUNT(*) FROM challenges WHERE announced=1")
    active = cursor.fetchone()[0]

    if active == 0:
        await message.answer(
            "⏸ Hozircha faol challenge yo‘q.\n\n"
            "🚀 Yangi challenge boshlansa, guruhda e’lon qilinadi."
        )
        return

    cursor.execute(
        "SELECT SUM(count) FROM invites WHERE inviter_id=?",
        (message.from_user.id,)
    )
    my_count = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT COUNT(DISTINCT inviter_id) FROM invites"
    )
    participants = cursor.fetchone()[0]

    await message.answer(
        "📊 Sizning statistikangiz\n\n"
        f"👥 Qo‘shgan odamlaringiz: {my_count}\n"
        f"👤 Jami qatnashchilar: {participants}\n\n"
        "🚀 Challenge davom etmoqda"
    )


# =========================
# RUN
# =========================
async def main():
    bot = Bot(token=TOKEN)
    asyncio.create_task(announce_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
