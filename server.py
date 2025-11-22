import os
import sys
import asyncio
from threading import Thread
from flask import Flask

app = Flask(__name__)

# Добавляем путь к проекту
sys.path.append('/opt/render/project/src')
sys.path.append('.')

def run_bot():
    """Запускает бота в отдельном потоке"""
    try:
        if os.path.exists('main.py'):
            from main import bot
            print("🚀 Запуск бота из main.py...")
            bot.run()
        elif os.path.exists('/opt/render/project/src/main.py'):
            sys.path.append('/opt/render/project/src')
            from main import bot
            print("🚀 Запуск бота из /opt/render/project/src/main.py...")
            bot.run()
        else:
            print("❌ Файл main.py не найден")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

@app.route('/')
def home():
    return "🎵 Music Bot is running! Use Telegram to interact with the bot."

@app.route('/health')
def health():
    return "OK"

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Бот запущен в отдельном потоке")
    
    # Запускаем Flask сервер
    print("🌐 Flask сервер запускается на порту 5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
