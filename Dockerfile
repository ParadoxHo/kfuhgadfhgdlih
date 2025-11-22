FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Запускаем бота
CMD ["python", "main.py"]