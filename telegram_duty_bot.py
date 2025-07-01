# telegram_duty_bot.py
import os
import csv
import requests
import logging
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # Your bot token
CHAT_ID = int(os.getenv('CHAT_ID', '0'))      # Fixed chat ID to send messages to
THREAD_ID = int(os.getenv('THREAD_ID', '0')) or None # Fixed thead chat ID to send messages to (optional)
SHEET_ID = os.getenv('SHEET_ID')               # Your Google Sheet ID
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

# Настройки планировщика
DAILY_JOB_HOUR = int(os.getenv('DAILY_JOB_HOUR', '9'))
DAILY_JOB_MINUTE = int(os.getenv('DAILY_JOB_MINUTE', '0'))

# Timezone set to Moscow
TZ = ZoneInfo('Europe/Moscow')

# Function to fetch today's duty person
def get_today_duty():
    try:
        resp = requests.get(CSV_URL)
        resp.raise_for_status()
        resp.encoding = 'utf-8-sig'
        reader = csv.reader(resp.text.splitlines())
        today_str = datetime.now(TZ).strftime('%d.%m')
        for row in reader:
            if row and row[0].strip() == today_str and len(row) >= 3:
                duty_person = row[2].strip()
                # Проверяем что значение не пустое
                if duty_person:  # Не пустая строка
                    return duty_person
        return None
    except Exception as e:
        logger.error(f"Error fetching sheet: {e}")
        return None

# Register command handler to get chat_id for debugging
def register_handlers(application):
    application.add_handler(CommandHandler('get_chat_id', get_chat_id))


async def get_chat_id(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    chat_id = chat.id
    thread_id = message.message_thread_id if message.is_topic_message else None
    
    # Логируем полную информацию
    logger.info(
        f"Received /get_chat_id - "
        f"Chat ID: {chat_id}, "
        f"Thread ID: {thread_id}, "
        f"Chat Type: {chat.type}, "
        f"Title: {chat.title or 'N/A'}"
    )
    
    # Формируем информационное сообщение
    response_text = (
        f"🆔 Chat ID: `{chat_id}`\n"
        f"🧵 Thread ID: `{thread_id or 'None (not a thread)'}`\n"
        f"💬 Chat Type: {chat.type}"
    )
    
    # Добавляем название чата/треда если есть
    if chat.title:
        response_text += f"\n🏷️ Title: {chat.title}"
    if thread_id and chat.is_forum:
        response_text += f"\n📌 Thread Name: {message.reply_to_message.forum_topic_created.name}" if message.reply_to_message else "\nℹ️ Thread name not available"

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_text,
            parse_mode='Markdown',
            message_thread_id=thread_id
        )
    except Exception as e:
        logger.error(f"Failed to send chat info to {chat_id}: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Basic info: Chat ID: {chat_id}, Thread ID: {thread_id}\nError: {e}"
        )

# Job callback to send duty message
async def send_daily_duty(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    logger.info(f"Running job 'send_daily_duty' at {now.isoformat()}")
    
    duty_person = get_today_duty()
    
    # Проверяем что дежурный определен
    if not duty_person:
        logger.info(f"No duty person found for {now.strftime('%d.%m')}, skipping message.")
        return
    
    message = f"Сегодня дежурит: {duty_person}"
    try:
        await context.bot.send_message(chat_id=CHAT_ID, text=message, message_thread_id=THREAD_ID)
        logger.info(f"Job 'send_daily_duty' executed successfully at {datetime.now(TZ).isoformat()}")
    except Exception as e:
        logger.error(f"Job 'send_daily_duty' failed to send message: {e}")

# Main entry point
def main():
    if not TELEGRAM_TOKEN or not SHEET_ID or CHAT_ID == 0:
        logger.error('TELEGRAM_TOKEN, SHEET_ID, and CHAT_ID must be set')
        return

    # Ensure OS timezone is set for scheduling
    os.environ['TZ'] = 'Europe/Moscow'
    try:
        import time; time.tzset()
    except Exception:
        logger.warning('tzset not supported, ensure system TZ is correct')

    # Build application and register handlers
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    register_handlers(application)

    # Setup JobQueue
    job_queue = application.job_queue
    if not job_queue:
        logger.error('JobQueue not available: install python-telegram-bot[job-queue]')
        return

    job_time = dtime(hour=DAILY_JOB_HOUR, minute=DAILY_JOB_MINUTE, tzinfo=TZ)
    logger.info(f"Scheduling daily duty job at {job_time} on weekdays")
    try:
        job_queue.run_daily(
            send_daily_duty,
            time=job_time
        )
    except Exception as e:
        logger.error(f"Job scheduling failed: {e}")


    # Debug: send current duty immediately on startup
    # logger.info("Sending immediate debug duty message on startup")
    # job_queue.run_once(send_daily_duty, when=0)

    # Start polling
    application.run_polling()

if __name__ == '__main__':
    main()
