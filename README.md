# 🎬 X-line Production Manager Bot

Video produksiya agentligi uchun **avtonom nazorat boti** — Google Sheets bilan to'liq integratsiya + AI yordamchi.

## ✨ Bot nima qiladi (mustaqil ishlaydi)

### 📸 Story nazorati (2 tomonlama)
- **9:00, 14:05, 19:05** — mijoz guruhiga "ma'lumot tashlang" (mijozni TG belgilab)
- **+10 daqiqa** — storymaker'ga "berdimi?" `[Ha/Yo'q]`
- **Ha** → "nechta?" `[1/2/3]` — 3 ga yetguncha eslatadi
- **Yo'q** → mijoz guruhiga eslatma + adminga darrov ogohlantirish

### 🎬 Video zanjiri
- **10:30, 15:30** — Operator'ga syomka, Montajchi'ga montaj eslatmasi
- VIDEO ISHLAB CHIQARISH sheetdagi Holat ustuniga qarab

### 📤 Post & vazifa
- **17:00** — storymaker'ga "post yuklandimi?"
- **Har soat** (9–21) — mas'ulga bajarilmagan vazifa eslatmasi

### 💬 Mijozga kunlik aloqa
- **11:00** — har mijozning shaxsiysiga "savollaringiz bormi?" (agentlik nomidan)

### 👑 Adminga nazorat hisoboti
- **9:00** — ertalabki reja
- **20:00** — kechki hisobot + 🧠 AI xulosa (kim qildi, kim qoldirdi)
- Muammo bo'lsa — darrov ogohlantirish

## 📱 Buyruqlar (faqat admin)

| Buyruq | Vazifasi |
|--------|----------|
| `/start` | Menyu (admin/oddiy farqlanadi) |
| `/nazorat` | To'liq nazorat paneli |
| `/holat` | Bugungi story/post holati |
| `/davomat` | Hodimlar rollari (sozlash tekshiruvi) |
| `/today` `/tasks` | Vazifalar |
| `/videos` `/content` | Video, kontent |
| `/clients` `/meetings` `/stats` | Mijoz, uchrashuv, statistika |
| `/goya <brend>` | 🤖 AI story g'oyasi |
| `/caption <mavzu>` | 🤖 AI caption + hashtag |
| `/ai <savol>` | 🤖 AI yordamchi |
| `/setup` `/test_story` | Sozlash, sinash |

Storymaker/operator/montajchi faqat **o'ziga tegishli** eslatma oladi — boshqa ma'lumotni ko'rmaydi.

## 🔑 Rollar (Hodimlar sheetda `Rol` ustuni)

Bot quyidagi rollarni tushunadi (turli yozilishlarni ham):
- `Direktor` / `SMM menejer` → admin
- `Storymaker` → story eslatma
- `Operator` → syomka eslatma
- `Montajchi` → montaj eslatma

## 🚀 Railway environment variables

| Variable | Qiymat |
|----------|--------|
| `TELEGRAM_TOKEN` | @BotFather token |
| `ADMIN_IDS` | `332723689,5107397160` |
| `SHEET_ID` | Google Sheets ID |
| `CREDENTIALS_JSON` | Service Account JSON (to'liq) |
| `GROQ_API_KEY` | console.groq.com key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `TIMEZONE` | `Asia/Samarkand` |

⚠️ Service Account emailni Google Sheetga **Editor** qiling.
⚠️ Botni har mijoz guruhiga **admin** qilib qo'shing.

## 💻 Local test

```bash
pip install -r requirements.txt
cp .env.example .env   # to'ldiring
# credentials.json ni shu papkaga qo'ying
python bot.py
```
