# -*- coding: utf-8 -*-
import os
import sys
import json
import logging
import tempfile
import re
import random
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# ==================== CONFIG ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = os.environ.get('ADMIN_IDS', '').split(',')

if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не установлен")
    sys.exit(1)

ADMIN_IDS = [id.strip() for id in ADMIN_IDS if id.strip()]
print(f"✅ Админы настроены: {ADMIN_IDS}")

# Импорты
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, 
        ContextTypes
    )
    import yt_dlp
    print("✅ Все зависимости загружены")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

# Настройки
RESULTS_PER_PAGE = 8
DATA_FILE = Path('user_data.json')
CHARTS_FILE = Path('charts_cache.json')

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилище данных
user_data = {}

def load_data():
    global user_data
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
    except Exception as e:
        logger.warning(f"Ошибка загрузки данных: {e}")

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

load_data()

# Основной класс бота
class StableMusicBot:
    def __init__(self):
        logger.info('✅ Бот инициализирован')

    def ensure_user(self, user_id: str):
        if str(user_id) not in user_data:
            user_data[str(user_id)] = {
                'search_results': [],
                'search_query': '',
                'download_history': [],
            }

    @staticmethod
    def clean_title(title: str) -> str:
        if not title:
            return 'Неизвестный трек'
        tags = ['official video', 'official music video', 'lyric video', 'hd', '4k']
        for tag in tags:
            title = re.sub(tag, '', title, flags=re.IGNORECASE)
        return ' '.join(title.split()).strip()

    async def search_soundcloud(self, query: str):
        """Поиск на SoundCloud"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'ignoreerrors': True,
        }

        results = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"scsearch10:{query}", download=False)
                
                entries = info.get('entries', [])
                if not entries:
                    entries = [info] if info else []
                
                for entry in entries:
                    if not entry:
                        continue
                    
                    title = self.clean_title(entry.get('title') or '')
                    url = entry.get('webpage_url') or entry.get('url') or ''
                    duration = entry.get('duration') or 0
                    artist = entry.get('uploader') or 'Неизвестно'
                    
                    if title and url:
                        results.append({
                            'title': title,
                            'webpage_url': url,
                            'duration': duration,
                            'artist': artist,
                        })
                        
        except Exception as e:
            logger.error(f'Ошибка поиска: {e}')
            
        return results

    async def download_track(self, update: Update, context: ContextTypes.DEFAULT_TYPE, track: dict) -> bool:
        """Упрощенное скачивание трека"""
        try:
            url = track.get('webpage_url')
            if not url:
                return False

            # Уведомление о начале скачивания
            status_msg = None
            if update.callback_query:
                await update.callback_query.edit_message_text(f"⏬ Скачиваю: {track.get('title', 'Трек')}")
            else:
                status_msg = await update.message.reply_text(f"⏬ Скачиваю: {track.get('title', 'Трек')}")

            # ПРОСТОЙ МЕТОД СКАЧИВАНИЯ
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'temp_audio.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'noplaylist': True,
            }

            success = False
            try:
                # Скачиваем напрямую
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    temp_files = [f for f in os.listdir('.') if f.startswith('temp_audio')]
                    
                    for temp_file in temp_files:
                        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                            # Отправляем файл
                            with open(temp_file, 'rb') as f:
                                await context.bot.send_audio(
                                    chat_id=update.effective_chat.id,
                                    audio=f,
                                    title=track.get('title', 'Неизвестный трек')[:64],
                                    performer=track.get('artist', 'Неизвестный исполнитель')[:64],
                                    caption=f"🎵 <b>{track.get('title', 'Неизвестный трек')}</b>\n🎤 {track.get('artist', 'Неизвестный исполнитель')}",
                                    parse_mode='HTML',
                                )
                            success = True
                            # Удаляем временный файл
                            os.remove(temp_file)
                            break
                            
            except Exception as download_error:
                logger.error(f"Ошибка скачивания: {download_error}")
                success = False

            # Если скачивание не удалось, отправляем ссылку
            if not success:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎧 <b>Слушайте онлайн:</b>\n{url}\n\n<i>Скачивание временно недоступно</i>",
                    parse_mode='HTML'
                )
                return True
                
            return success
            
        except Exception as e:
            logger.error(f'Общая ошибка: {e}')
            # Всегда отправляем ссылку как запасной вариант
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎧 <b>Слушайте онлайн:</b>\n{track.get('webpage_url', '')}",
                    parse_mode='HTML'
                )
                return True
            except:
                return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        self.ensure_user(user.id)
        
        keyboard = [
            [InlineKeyboardButton('🔍 Поиск музыки', callback_data='start_search')],
            [InlineKeyboardButton('🎲 Случайный трек', callback_data='random_track')],
        ]
        
        await update.message.reply_text(
            f"🎵 <b>Music Bot</b>\nПривет, {user.first_name}!\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик поиска"""
        await update.message.reply_text('🎵 Введите название песни или исполнителя:')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = (update.message.text or '').strip()
        if not text or text.startswith('/'):
            return
            
        user = update.effective_user
        self.ensure_user(user.id)
        
        if len(text) < 2:
            await update.message.reply_text('❌ Введите хотя бы 2 символа')
            return

        # Поиск
        status_msg = await update.message.reply_text(f"🔍 Ищу: <b>{text}</b>", parse_mode='HTML')
        
        try:
            results = await self.search_soundcloud(text)
            if not results:
                await status_msg.edit_text('❌ Ничего не найдено')
                return

            # Сохраняем результаты
            user_data[str(user.id)]['search_results'] = results
            user_data[str(user.id)]['search_query'] = text
            save_data()

            # Показываем первые 5 результатов
            keyboard = []
            for idx, track in enumerate(results[:5]):
                title = track.get('title', 'Неизвестный трек')
                artist = track.get('artist', 'Неизвестный исполнитель')
                short_title = title if len(title) <= 30 else title[:27] + '...'
                button_text = f"🎵 {short_title}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f'download:{idx}')])
            
            keyboard.append([InlineKeyboardButton('🔍 Новый поиск', callback_data='new_search')])
            
            await status_msg.edit_text(
                f"🔍 Найдено {len(results)} треков по запросу: <b>{text}</b>\n\nВыберите трек:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f'Ошибка поиска: {e}')
            await status_msg.edit_text('❌ Ошибка при поиске')

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback кнопок"""
        query = update.callback_query
        data = query.data
        user = update.effective_user
        self.ensure_user(user.id)
        
        await query.answer()
        
        try:
            if data == 'start_search' or data == 'new_search':
                await query.edit_message_text('🎵 Введите название песни или исполнителя:')
                return
                
            elif data == 'random_track':
                searches = ['lo fi', 'chillhop', 'deep house', 'synthwave', 'indie rock']
                random_search = random.choice(searches)
                await query.edit_message_text(f"🎲 Ищу случайный трек: <b>{random_search}</b>", parse_mode='HTML')
                
                results = await self.search_soundcloud(random_search)
                if results:
                    random_track = random.choice(results)
                    success = await self.download_track(update, context, random_track)
                    if success:
                        # Сохраняем в историю
                        user_data[str(user.id)]['download_history'].append(random_track)
                        save_data()
                return
                
            elif data.startswith('download:'):
                idx = int(data.split(':')[1])
                results = user_data[str(user.id)].get('search_results', [])
                
                if 0 <= idx < len(results):
                    track = results[idx]
                    success = await self.download_track(update, context, track)
                    
                    if success:
                        # Сохраняем в историю
                        user_data[str(user.id)]['download_history'].append(track)
                        save_data()
                        
                        # Показываем кнопки для дальнейших действий
                        keyboard = [
                            [InlineKeyboardButton('🔍 Новый поиск', callback_data='new_search')],
                            [InlineKeyboardButton('🎲 Случайный трек', callback_data='random_track')],
                        ]
                        await query.message.reply_text(
                            "✅ Готово! Что дальше?",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                return
                
        except Exception as e:
            logger.error(f'Ошибка callback: {e}')
            await query.message.reply_text('❌ Произошла ошибка')

    def run(self):
        """Запуск бота"""
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрация обработчиков
        app.add_handler(CommandHandler('start', self.start))
        app.add_handler(CommandHandler('search', self.handle_search))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        print('🚀 Бот запущен!')
        app.run_polling()

# Глобальная переменная для server.py
bot = StableMusicBot()

if __name__ == '__main__':
    bot.run()
