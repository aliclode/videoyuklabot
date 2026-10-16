import asyncio
import logging
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import yt_dlp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))  # Render shu portni beradi
MAX_SIZE = 49 * 1024 * 1024  # Telegram Bot API limiti ~50 MB
COOKIES_SRC = os.getenv("COOKIES_FILE", "/etc/secrets/cookies.txt")

URL_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be|instagram\.com)/\S+",
    re.IGNORECASE,
)
AUDIO_RE = re.compile(r"\b(mp3|audio|musiqa)\b", re.IGNORECASE)

LINKS: dict[str, str] = {}  # callback uchun havolalar
SEM = asyncio.Semaphore(2)  # bepul serverda xotira kam: bir vaqtda 2 ta yuklash

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


def cookie_path():
    """Ixtiyoriy: YouTube bloklasa, cookies.txt (Render Secret File) ishlatiladi."""
    if os.path.exists(COOKIES_SRC):
        dst = "/tmp/cookies.txt"
        shutil.copy(COOKIES_SRC, dst)
        return dst
    return None


def download(url: str, mode: str, workdir: str) -> Path:
    opts = {
        "outtmpl": f"{workdir}/%(title).80s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_SIZE,
        "concurrent_fragment_downloads": 4,
        "socket_timeout": 20,
        "retries": 3,
    }
    cookies = cookie_path()
    if cookies:
        opts["cookiefile"] = cookies

    if mode == "audio":
        opts.update(
            {
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "128",
                    }
                ],
            }
        )
    else:
        # Tayyor mp4 ni afzal ko'ramiz: birlashtirish kerak bo'lmasa tezroq
        opts.update(
            {
                "format": "b[ext=mp4][height<=720]/bv*[height<=720]+ba/b[height<=720]/b",
                "merge_output_format": "mp4",
            }
        )

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    files = [p for p in Path(workdir).iterdir() if p.is_file()]
    if not files:
        raise RuntimeError("Fayl yuklanmadi")
    return max(files, key=lambda p: p.stat().st_size)


async def process(message: Message, url: str, mode: str, status: Message | None = None):
    if status is None:
        status = await message.reply("⏳ Yuklanmoqda...")
    workdir = tempfile.mkdtemp(prefix="dl_")
    try:
        async with SEM:
            await message.bot.send_chat_action(
                message.chat.id,
                ChatAction.UPLOAD_VIDEO if mode == "video" else ChatAction.UPLOAD_VOICE,
            )
            path = await asyncio.to_thread(download, url, mode, workdir)

        if path.stat().st_size > MAX_SIZE:
            await status.edit_text("❌ Fayl 50 MB dan katta, yuborib bo'lmaydi.")
            return

        file = FSInputFile(path)
        if mode == "audio":
            await message.answer_audio(file)
        else:
            key = save_link(url)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎵 MP3 qilib olish", callback_data=f"a:{key}")]
                ]
            )
            await message.answer_video(file, reply_markup=kb)
        await status.delete()
    except Exception:
        logging.exception("Yuklashda xato")
        await status.edit_text(
            "❌ Yuklab bo'lmadi. Havola yopiq/noto'g'ri, fayl juda katta yoki "
            "platforma vaqtincha bloklagan bo'lishi mumkin."
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Salom! 👋 YouTube yoki Instagram havolasini yuboring, "
        "so'ng «🎬 Video» yoki «🎵 Audio» tugmasini bosing — yuklash darhol boshlanadi.\n"
        "Tugmasiz audio uchun: «mp3 <havola>»."
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "• Havola yuboring → tugmani tanlang → fayl keladi\n"
        "• «mp3 <havola>» → tugmasiz darhol audio\n"
        "Cheklov: 50 MB gacha, faqat ochiq kontent."
    )


def choice_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Video", callback_data=f"v:{key}"),
                InlineKeyboardButton(text="🎵 Audio (MP3)", callback_data=f"a:{key}"),
            ]
        ]
    )


def save_link(url: str) -> str:
    key = uuid.uuid4().hex[:12]
    if len(LINKS) > 500:
        LINKS.pop(next(iter(LINKS)))
    LINKS[key] = url
    return key


@dp.message(F.text.regexp(URL_RE))
async def got_link(message: Message):
    url = URL_RE.search(message.text).group(0)
    # "mp3 <havola>" yozilsa tugmasiz darhol audio
    if AUDIO_RE.search(message.text):
        await process(message, url, "audio")
        return
    await message.reply("Qaysi formatda yuklab beray?", reply_markup=choice_kb(save_link(url)))


@dp.callback_query(F.data.regexp(r"^[va]:"))
async def choose(call: CallbackQuery):
    kind, key = call.data.split(":", 1)
    url = LINKS.get(key)
    if not url:
        await call.answer("Havola eskirgan, qaytadan yuboring.", show_alert=True)
        return
    await call.answer()  # tugma darhol javob beradi
    mode = "audio" if kind == "a" else "video"
    if call.message.text:  # tanlov xabarini holat xabariga aylantiramiz
        status = await call.message.edit_text("⏳ Yuklanmoqda...")
    else:  # video ostidagi MP3 tugmasi
        status = await call.message.answer("⏳ MP3 tayyorlanmoqda...")
    await process(call.message, url, mode, status)


@dp.message(F.text)
async def not_link(message: Message):
    await message.answer("Iltimos, YouTube yoki Instagram havolasini yuboring.")


async def health(_):
    return web.Response(text="ok")


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN o'rnatilmagan")

    # Render Web Service port ochishni talab qiladi + uyg'oq saqlash uchun ping manzili
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

    bot = Bot(BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
