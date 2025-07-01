FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем переменные окружения (опционально можно использовать .env)
ENV TZ=Europe/Moscow

# Устанавливаем зависимости
RUN pip install --no-cache-dir 'python-telegram-bot[job-queue]' requests

# Копируем файлы приложения
COPY telegram_duty_bot.py .

# Определяем команду запуска
CMD ["python", "telegram_duty_bot.py"]
