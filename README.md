# YouTube / Instagram yuklovchi Telegram bot

Havola yuboring, «🎬 Video» yoki «🎵 Audio» tugmasini bosing — yuklash darhol boshlanadi.
Tugmasiz audio uchun: «mp3 <havola>».

## Render'ga joylash
1. Bu papkani GitHub'da yangi repoga yuklang.
2. render.com → New → Blueprint → repoyni tanlang (render.yaml avtomatik o'qiladi).
3. BOT_TOKEN ga @BotFather bergan tokenni kiriting → Deploy.
4. Bepul rejada server 15 daqiqa bo'sh tursa uxlaydi. uptimerobot.com'da
   `https://<sizning-nomingiz>.onrender.com/` manziliga har 5 daqiqada ping qo'ying.

## Agar YouTube "bot emassiz" deb bloklasa
Brauzerdan cookies.txt eksport qiling (Netscape format) va Render → Environment →
Secret Files bo'limiga `cookies.txt` nomi bilan qo'shing. Bot uni o'zi topadi.
(Eslatma: bu cookies hisobingizga kirish beradi — alohida akkauntdan foydalaning.)

## Lokal ishga tushirish
    pip install -r requirements.txt
    export BOT_TOKEN=...
    python bot.py   # ffmpeg o'rnatilgan bo'lishi kerak
