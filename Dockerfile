FROM python:3.11-slim

WORKDIR /app

# Kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodni nusxalash
COPY . .

# Botni ishga tushirish
CMD ["python", "bot.py"]
