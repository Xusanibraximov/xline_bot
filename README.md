# 🎬 X-line Production Manager Bot

Video produksiya kompaniyasi uchun Telegram bot — Google Sheets bilan to'liq integratsiya.

## ✨ Imkoniyatlar

- 📋 Google Sheets dan **real-time** ma'lumot o'qish
- ☀️ Har kuni 09:00 da bugungi reja (3 ta asosiy vazifa)
- ✅ Tugma orqali "Bajarildi" statusini Google Sheets ga yozish
- 🎬 Jarayondagi videolar, kontent kalendar, mijozlar, uchrashuvlar
- 📊 Umumiy statistika

## 📱 Buyruqlar

| Buyruq | Vazifasi |
|--------|----------|
| `/start` | Bosh menyu |
| `/today` | Bugungi 3 ta asosiy vazifa (✅ tugma bilan) |
| `/tasks` | Barcha bajarilmagan vazifalar |
| `/videos` | Jarayondagi videolar |
| `/content` | Yaqin 7 kunlik kontent rejasi |
| `/meetings` | Kutilayotgan uchrashuvlar |
| `/clients` | Aktiv mijozlar |
| `/stats` | Umumiy statistika |

---

## 🚀 Railway'ga deploy qilish

### 1. Bu reponi Railway'ga ulang
[railway.app](https://railway.app) → New Project → Deploy from GitHub repo → `xline-bot`

### 2. Environment Variables qo'shing
Railway → Variables bo'limida:

| Variable | Qiymat |
|----------|--------|
| `TELEGRAM_TOKEN` | @BotFather dan olingan token |
| `ADMIN_CHAT_ID` | @userinfobot dan olingan ID |
| `SHEET_ID` | Google Sheets URL dagi ID |
| `CREDENTIALS_JSON` | Service Account JSON (to'liq matn) |
| `TIMEZONE` | `Asia/Samarkand` |
| `DAILY_HOUR` | `9` |

### 3. Deploy
Railway avtomatik build qiladi va botni ishga tushiradi.

---

## 🔑 Muhim: CREDENTIALS_JSON

`credentials.json` faylni GitHubga **yuklamang** (`.gitignore` da himoyalangan).

Railway'da uning o'rniga `CREDENTIALS_JSON` o'zgaruvchisiga JSON faylning **to'liq ichki matnini** joylang (bitta qatorda yoki ko'p qatorda — ikkalasi ham ishlaydi).

⚠️ **Service Account email** ni Google Sheetga **Editor** sifatida share qilishni unutmang:
```
xline-bot@xline-bot.iam.gserviceaccount.com
```

---

## 💻 Local test

```bash
# 1. Kutubxonalar
pip install -r requirements.txt

# 2. Sozlamalar
cp .env.example .env
# .env ni to'ldiring

# 3. credentials.json ni shu papkaga qo'ying

# 4. Ishga tushirish
python bot.py
```

---

## 📊 Google Sheets tuzilmasi

Bot quyidagi sahifalardan o'qiydi:

- **VAZIFALAR** — `ID, Vazifa, Javobgar, Deadline, Bajarildi, Muhimligi`
- **VIDEO ISHLAB CHIQARISH** — `ID, Mavzu, Loyiha, Holat, Deadline`
- **KONTENT KALENDAR** — `Sana, Vaqt, Loyiha, Platforma, Turi, Mavzu, Holat`
- **MIJOZLAR** — `Mijoz, Platforma, Mas'ul, Yordamchi, Holat`
- **UCHRASHUVLAR** — `Sana, Vaqt, Kim bilan, Maqsad, Holat`

---

## 📁 Fayllar

```
xline-bot/
├── bot.py                      # Asosiy kod
├── requirements.txt            # Kutubxonalar
├── Dockerfile                  # Container
├── railway.json                # Railway config
├── Procfile                    # Zaxira deploy usuli
├── .gitignore                  # Maxfiy fayllar himoyasi
├── .env.example                # Sozlamalar namunasi
├── README.md                   # Bu fayl
└── .github/workflows/test.yml  # Avtomatik test
```
