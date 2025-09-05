#!/usr/bin/env python3
"""
Исправленная версия Telegram бота (совместимость с event loop)
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import subprocess
import hashlib
import nest_asyncio

# Исправляем проблему с event loop
nest_asyncio.apply()

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartBazaBot:
    def __init__(self, token, authorized_users):
        self.token = token
        self.authorized_users = set(authorized_users)
        self.baza_file = Path("baza.txt")
        self.gist_dir = Path("gist-baza")
        self.sections_cache = {}
        self.pending_updates = {}
        
    def is_authorized(self, user_id):
        return user_id in self.authorized_users
    
    def parse_sections(self, content: str) -> Dict[str, str]:
        """Разбирает базу знаний на секции"""
        sections = {}
        current_section = "header"
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            if self.is_section_header(line):
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = self.extract_section_name(line)
                current_content = [line]
            else:
                current_content.append(line)
        
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()
            
        return sections
    
    def is_section_header(self, line: str) -> bool:
        """Определяет заголовок секции"""
        patterns = [
            r'^#{1,6}\s+',
            r'^=+\s*$',
            r'^\*\*[А-ЯЁ\s]+\*\*',
            r'^\d+\.\s+[А-ЯЁ]',
            r'^#\s*=+',
        ]
        
        for pattern in patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        return False
    
    def extract_section_name(self, line: str) -> str:
        """Извлекает имя секции"""
        clean_line = re.sub(r'[#*=\d\.\s]+', '', line).strip()
        section_key = clean_line.lower().replace(' ', '_').replace('ё', 'е')
        section_key = re.sub(r'[^\w_]', '', section_key)
        return section_key[:30] if section_key else f"section_{hash(line) % 1000}"
    
    def get_section_summary(self, content: str) -> str:
        """Краткое описание секции"""
        lines = [line.strip() for line in content.split('\n') if line.strip()][:3]
        summary = ' '.join(lines).strip()
        if len(summary) > 100:
            summary = summary[:97] + '...'
        return summary if summary else "Пустая секция"
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Стартовое сообщение"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен!")
            return
            
        keyboard = [
            [InlineKeyboardButton("📖 Секции", callback_data='show_sections')],
            [InlineKeyboardButton("📊 Статус", callback_data='status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            """🤖 <b>Smart FPF Baza Bot v2.0</b>

📱 <b>JSON команды для Claude iPhone:</b>

<code>{"action": "read_sections", "limit": 3}</code>

<code>{"action": "update_section", "section": "основная_задача", "changes": "Новая информация"}</code>

<code>{"action": "add_section", "title": "Новая секция", "content": "Содержимое"}</code>

<code>{"action": "status"}</code>

<code>{"action": "backup"}</code>

💬 <b>Хэштег команды:</b>
• #идея - добавить идею
• #задача - добавить задачу  
• #правка - внести правки
• #баг - сообщить о баге
• #решение - предложить решение

📊 <b>Новые возможности:</b>
• Детальный статус с информацией о файле
• Автоматическое создание резервных копий
• Категоризация сообщений через хэштеги
• Расширенная обработка ошибок

✅ <b>Бот готов к работе!</b>""",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def handle_json_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка JSON команд"""
        if not self.is_authorized(update.effective_user.id):
            return
            
        text = update.message.text.strip()
        
        try:
            command = json.loads(text)
            action = command.get('action')
            
            if action == 'read_sections':
                await self.handle_read_sections(update, command)
            elif action == 'update_section':
                await self.handle_section_update(update, command)
            elif action == 'add_section':
                await self.handle_section_add(update, command)
            elif action == 'backup':
                await self.handle_backup_command(update, command)
            elif action == 'status':
                await self.handle_detailed_status(update, command)
            else:
                await update.message.reply_text(f"❌ Неизвестное действие: {action}")
                
        except json.JSONDecodeError:
            await self.handle_text_command(update, context)
    
    async def handle_read_sections(self, update: Update, command: Dict):
        """Чтение секций"""
        limit = command.get('limit', 5)
        
        if not self.baza_file.exists():
            await update.message.reply_text("❌ Файл базы не найден")
            return
            
        content = self.baza_file.read_text(encoding='utf-8')
        sections = self.parse_sections(content)
        
        if not sections:
            await update.message.reply_text("❌ Секции не найдены")
            return
            
        section_items = list(sections.items())[:limit]
        
        response = f"📚 <b>Секции базы знаний</b> ({len(section_items)}):\n\n"
        
        for i, (key, content) in enumerate(section_items, 1):
            summary = self.get_section_summary(content)
            response += f"{i}. <code>{key}</code>\n   {summary}\n\n"
            
        if len(response) > 4000:
            response = response[:4000] + "\n\n... (обрезано)"
            
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def handle_section_update(self, update: Update, command: Dict):
        """Обновление секции"""
        section = command.get('section', '').lower()
        changes = command.get('changes', '')
        mode = command.get('mode', 'append')
        
        if not section or not changes:
            await update.message.reply_text("❌ Укажите section и changes")
            return
            
        if not self.baza_file.exists():
            await update.message.reply_text("❌ Файл базы не найден")
            return
            
        content = self.baza_file.read_text(encoding='utf-8')
        sections = self.parse_sections(content)
        
        # Простой поиск секции
        found_section = None
        for sec_name in sections.keys():
            if section in sec_name.lower() or sec_name.lower() in section:
                found_section = sec_name
                break
        
        if not found_section:
            await update.message.reply_text(f"❌ Секция '{section}' не найдена")
            available = ', '.join(list(sections.keys())[:3])
            await update.message.reply_text(f"Доступные: {available}")
            return
        
        # Обновляем секцию
        old_content = sections[found_section]
        
        if mode == 'append':
            new_content = old_content + '\n' + changes
        elif mode == 'prepend':
            new_content = changes + '\n' + old_content
        else:
            new_content = old_content + '\n' + changes
        
        sections[found_section] = new_content
        
        # Сохраняем
        await self.save_sections(sections)
        
        await update.message.reply_text(
            f"✅ <b>Секция обновлена!</b>\n\n"
            f"📂 Секция: <code>{found_section}</code>\n"
            f"📝 Добавлено: {len(changes)} символов",
            parse_mode='HTML'
        )
        
        await self.sync_to_gist(update, silent=True)
    
    async def handle_section_add(self, update: Update, command: Dict):
        """Добавление новой секции"""
        title = command.get('title', '')
        content = command.get('content', '')
        
        if not title or not content:
            await update.message.reply_text("❌ Укажите title и content")
            return
            
        if self.baza_file.exists():
            existing_content = self.baza_file.read_text(encoding='utf-8')
        else:
            existing_content = ""
            
        section_header = f"## {title}" if not title.startswith('#') else title
        new_section = f"\n{section_header}\n\n{content}\n"
        all_content = existing_content + new_section
        
        self.baza_file.write_text(all_content, encoding='utf-8')
        
        await update.message.reply_text(
            f"✅ <b>Новая секция добавлена!</b>\n\n"
            f"📂 Название: <b>{title}</b>\n"
            f"📝 Размер: {len(content)} символов",
            parse_mode='HTML'
        )
        
        await self.sync_to_gist(update, silent=True)
    
    async def save_sections(self, sections: Dict[str, str]):
        """Сохраняет секции в файл"""
        # Бэкап
        timestamp = int(datetime.now().timestamp())
        backup_file = Path(f"baza_backup_{timestamp}.txt")
        
        if self.baza_file.exists():
            backup_content = self.baza_file.read_text(encoding='utf-8')
            backup_file.write_text(backup_content, encoding='utf-8')
        
        # Объединяем секции
        content_parts = [section_content for section_content in sections.values()]
        full_content = '\n\n'.join(content_parts)
        
        self.baza_file.write_text(full_content, encoding='utf-8')
        logger.info(f"База сохранена, бэкап: {backup_file}")
    
    async def sync_to_gist(self, update: Update, silent=False):
        """Синхронизация с Gist"""
        try:
            if Path("gist_sync.py").exists():
                result = subprocess.run(['python3', 'gist_sync.py', 'push'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    if not silent:
                        await update.message.reply_text("🔗 ✅ Синхронизировано с Gist!")
                    return
                    
        except Exception as e:
            if not silent:
                await update.message.reply_text(f"❌ Ошибка синхронизации: {e}")
            logger.error(f"Sync error: {e}")
    
    async def handle_backup_command(self, update: Update, command: Dict):
        """Создание резервной копии"""
        try:
            if not self.baza_file.exists():
                await update.message.reply_text("❌ Файл базы не найден")
                return
                
            # Создаем бэкап с timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.baza_file.parent / f"baza_backup_{timestamp}.txt"
            
            content = self.baza_file.read_text(encoding='utf-8')
            backup_file.write_text(content, encoding='utf-8')
            
            await update.message.reply_text(
                f"✅ <b>Резервная копия создана</b>\n\n"
                f"📁 Файл: <code>{backup_file.name}</code>\n"
                f"📄 Размер: {len(content)} символов\n"
                f"🕒 Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка создания бэкапа: {e}")
    
    async def handle_detailed_status(self, update: Update, command: Dict):
        """Детальный статус системы"""
        try:
            file_exists = self.baza_file.exists()
            gist_exists = self.gist_dir.exists()
            
            if file_exists:
                content = self.baza_file.read_text(encoding='utf-8')
                sections = self.parse_sections(content)
                file_size = len(content)
                sections_count = len(sections)
                lines_count = len(content.split('\n'))
                modified = datetime.fromtimestamp(self.baza_file.stat().st_mtime).strftime("%d.%m.%Y %H:%M:%S")
                
                # Последние изменения
                recent_lines = content.split('\n')[-5:]
                recent_preview = '\n'.join(recent_lines)[-150:] + "..." if len(recent_preview) > 150 else recent_preview
            else:
                file_size = 0
                sections_count = 0
                lines_count = 0
                modified = "Не найден"
                recent_preview = "Файл отсутствует"
            
            # Статистика бэкапов
            backup_files = list(self.baza_file.parent.glob("baza_backup_*.txt"))
            backup_count = len(backup_files)
            
            status_text = f"""📊 <b>Детальный статус FPF Bot</b>

📁 <b>Локальный файл:</b>
{'✅' if file_exists else '❌'} <code>{self.baza_file.name}</code>
📄 Размер: {file_size} символов
📝 Строк: {lines_count}
📚 Секций: {sections_count}
🕒 Изменен: {modified}

💾 <b>Резервные копии:</b>
📋 Количество: {backup_count} файлов

🔗 <b>Синхронизация:</b>
{'✅' if gist_exists else '❌'} GitHub Gist подключен
🆔 Gist ID: 63beb2b8d1fb3426dd5f064e79a0641f

📝 <b>Последние изменения:</b>
<code>{recent_preview}</code>

🤖 <b>Бот активен и готов к работе</b>"""
            
            await update.message.reply_text(status_text, parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения статуса: {e}")
    
    async def handle_text_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обычные команды и хэштеги"""
        text = update.message.text
        text_lower = text.lower()
        
        # Проверяем хэштеги для автоматической категоризации
        if any(tag in text_lower for tag in ['#идея', '#задача', '#правка', '#баг', '#решение']):
            await self.handle_hashtag_message(update, context)
            return
        
        if 'секции' in text_lower or 'список' in text_lower:
            await self.show_sections(update)
        elif 'статус' in text_lower:
            await self.show_status(update)
        elif 'бэкап' in text_lower or 'backup' in text_lower:
            command = {"action": "backup"}
            await self.handle_backup_command(update, command)
        else:
            await update.message.reply_text(
                "💡 Используйте JSON формат:\n\n"
                '<code>{"action": "read_sections", "limit": 3}</code>\n\n'
                '🏷️ Или хэштеги: #идея #задача #правка #баг #решение',
                parse_mode='HTML'
            )
    
    async def handle_hashtag_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений с хэштегами"""
        text = update.message.text
        username = update.effective_user.username or update.effective_user.first_name
        
        # Определяем тип записи
        entry_type = "💡 Идея"
        if "#задача" in text.lower():
            entry_type = "📋 Задача"
        elif "#правка" in text.lower():
            entry_type = "🔧 Правка"
        elif "#баг" in text.lower():
            entry_type = "🐛 Баг"
        elif "#решение" in text.lower():
            entry_type = "✅ Решение"
        
        # Очищаем текст от хэштегов
        import re
        clean_text = re.sub(r'#\w+\s*', '', text).strip()
        
        # Формируем новую секцию
        timestamp = datetime.now().strftime('%d.%m.%Y %H:%M')
        section_title = f"{entry_type} от {username}"
        section_content = f"""**Дата:** {timestamp}  
**Автор:** @{username}  
**Описание:** {clean_text}"""
        
        # Добавляем как новую секцию
        command = {
            "action": "add_section",
            "title": section_title,
            "content": section_content
        }
        
        await self.handle_section_add(update, command)
        
        # Дополнительное подтверждение с типом
        await update.message.reply_text(
            f"✅ <b>{entry_type} добавлена в базу</b>\n"
            f"📝 Автор: @{username}\n"
            f"🕒 Время: {timestamp}",
            parse_mode='HTML'
        )
    
    async def show_sections(self, update: Update):
        """Показать секции"""
        if not self.baza_file.exists():
            await update.message.reply_text("❌ Файл базы не найден")
            return
            
        content = self.baza_file.read_text(encoding='utf-8')
        sections = self.parse_sections(content)
        
        response = f"📚 <b>Секции</b> ({len(sections)}):\n\n"
        
        for i, (key, content) in enumerate(sections.items(), 1):
            size = len(content)
            response += f"{i}. <code>{key}</code> ({size} симв)\n"
            
        if len(response) > 4000:
            response = response[:4000] + "..."
            
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def show_status(self, update: Update):
        """Статус системы"""
        file_exists = self.baza_file.exists()
        gist_exists = self.gist_dir.exists()
        
        if file_exists:
            content = self.baza_file.read_text(encoding='utf-8')
            sections = self.parse_sections(content)
            file_size = len(content)
            sections_count = len(sections)
        else:
            file_size = 0
            sections_count = 0
            
        status_text = f"""📊 <b>Статус</b>

📁 baza.txt: {'✅' if file_exists else '❌'}
📄 Размер: {file_size} символов
📚 Секций: {sections_count}
🔗 Gist: {'✅' if gist_exists else '❌'}

🤖 <b>Бот активен</b>"""
        
        await update.message.reply_text(status_text, parse_mode='HTML')
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inline кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'show_sections':
            await self.show_sections(query)
        elif query.data == 'status':
            await self.show_status(query)

def main():
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    AUTHORIZED_USERS = os.getenv("AUTHORIZED_USER_IDS", "").split(",")
    
    if not BOT_TOKEN or not AUTHORIZED_USERS[0]:
        print("❌ Переменные окружения не установлены!")
        return
    
    authorized_ids = [int(uid.strip()) for uid in AUTHORIZED_USERS if uid.strip()]
    
    bot = SmartBazaBot(BOT_TOKEN, authorized_ids)
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_json_command))
    application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
    
    print("🚀 Smart Baza Bot запущен!")
    print("📱 Найдите @fixprefix_bot в Telegram")
    
    # Используем polling с обработкой исключений
    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()