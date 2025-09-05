#!/usr/bin/env python3
"""
Умный Telegram Bot для точечных обновлений базы знаний FPF
Принимает изменения частями, умеет обновлять конкретные разделы
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import subprocess
import hashlib

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartBazaBot:
    def __init__(self, token, authorized_users):
        self.token = token
        self.authorized_users = set(authorized_users)
        self.baza_file = Path("baza.txt")
        self.gist_dir = Path("gist-baza")
        self.sections_cache = {}
        self.pending_updates = {}  # Хранит частичные обновления
        
    def is_authorized(self, user_id):
        return user_id in self.authorized_users
    
    def parse_sections(self, content: str) -> Dict[str, str]:
        """Разбирает базу знаний на секции"""
        sections = {}
        current_section = "header"
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            # Определяем новую секцию по заголовкам
            if self.is_section_header(line):
                # Сохраняем предыдущую секцию
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Начинаем новую секцию
                current_section = self.extract_section_name(line)
                current_content = [line]
            else:
                current_content.append(line)
        
        # Сохраняем последнюю секцию
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()
            
        return sections
    
    def is_section_header(self, line: str) -> bool:
        """Определяет, является ли строка заголовком секции"""
        patterns = [
            r'^#{1,6}\s+',  # Markdown заголовки
            r'^=+\s*$',     # Разделители ===== (исправлено)
            r'^\*\*[А-ЯЁ\s]+\*\*',  # **ЗАГОЛОВОК**
            r'^\d+\.\s+[А-ЯЁ]',     # 1. Заголовок
            r'^##\s+[А-ЯЁ]',        # ## Заголовок
            r'^#\s*=+',             # # ====== разделители
        ]
        
        for pattern in patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        return False
    
    def extract_section_name(self, line: str) -> str:
        """Извлекает имя секции из заголовка"""
        # Убираем markdown символы и очищаем
        clean_line = re.sub(r'[#*=\d\.\s]+', '', line).strip()
        
        # Преобразуем в ключ
        section_key = clean_line.lower().replace(' ', '_').replace('ё', 'е')
        
        # Убираем спец символы
        section_key = re.sub(r'[^\w_]', '', section_key)
        
        return section_key[:30] if section_key else f"section_{hash(line) % 1000}"
    
    def get_section_summary(self, content: str) -> str:
        """Создает краткое описание секции для отображения"""
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
            [
                InlineKeyboardButton("📖 Показать секции", callback_data='show_sections'),
                InlineKeyboardButton("➕ Добавить секцию", callback_data='add_section')
            ],
            [
                InlineKeyboardButton("✏️ Обновить секцию", callback_data='update_section'),
                InlineKeyboardButton("🔄 Применить изменения", callback_data='apply_changes')
            ],
            [
                InlineKeyboardButton("📊 Статус", callback_data='status'),
                InlineKeyboardButton("🔗 Синхронизация", callback_data='sync_gist')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            """🤖 <b>Smart FPF Baza Bot</b>

🔍 <b>Умею работать с секциями базы:</b>
• Точечные обновления конкретных разделов
• Добавление новых секций  
• Применение изменений частями
• Автосинхронизация с GitHub Gist

📱 <b>Для Claude iPhone:</b>
Отправляйте команды в формате JSON:

<code>
{
  "action": "update_section",
  "section": "этап_1_стабилизация", 
  "changes": "- [x] Переход на timestamp логику"
}
</code>

<code>
{
  "action": "add_section",
  "title": "Новые идеи",
  "content": "Содержимое новой секции"
}
</code>""",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def handle_json_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка JSON команд от Claude iPhone"""
        if not self.is_authorized(update.effective_user.id):
            return
            
        text = update.message.text.strip()
        
        # Пытаемся распарсить JSON
        try:
            command = json.loads(text)
            
            action = command.get('action')
            
            if action == 'update_section':
                await self.handle_section_update(update, command)
            elif action == 'add_section':
                await self.handle_section_add(update, command)
            elif action == 'replace_section':
                await self.handle_section_replace(update, command)
            elif action == 'delete_section':
                await self.handle_section_delete(update, command)
            elif action == 'read_sections':
                await self.handle_read_sections(update, command)
            else:
                await update.message.reply_text(f"❌ Неизвестное действие: {action}")
                
        except json.JSONDecodeError:
            # Обычное текстовое сообщение - пытаемся понять команду
            await self.handle_text_command(update, context)
    
    async def handle_section_update(self, update: Update, command: Dict):
        """Обновление существующей секции"""
        section = command.get('section', '').lower()
        changes = command.get('changes', '')
        mode = command.get('mode', 'append')  # append, prepend, replace
        
        if not section or not changes:
            await update.message.reply_text("❌ Укажите section и changes")
            return
            
        # Читаем текущую базу
        if not self.baza_file.exists():
            await update.message.reply_text("❌ Файл базы не найден")
            return
            
        content = self.baza_file.read_text(encoding='utf-8')
        sections = self.parse_sections(content)
        
        # Ищем секцию (нечеткий поиск)
        found_section = self.find_section_fuzzy(section, sections.keys())
        
        if not found_section:
            await update.message.reply_text(f"❌ Секция '{section}' не найдена")
            # Показываем доступные секции
            available = ', '.join(list(sections.keys())[:5])
            await update.message.reply_text(f"Доступные секции: {available}")
            return
        
        # Применяем изменения
        old_content = sections[found_section]
        
        if mode == 'append':
            new_content = old_content + '\n' + changes
        elif mode == 'prepend':
            new_content = changes + '\n' + old_content
        elif mode == 'replace':
            new_content = changes
        else:
            new_content = old_content + '\n' + changes
        
        sections[found_section] = new_content
        
        # Сохраняем обновленную базу
        await self.save_sections(sections)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        await update.message.reply_text(
            f"✅ <b>Секция обновлена!</b>\n\n"
            f"📂 Секция: <code>{found_section}</code>\n"
            f"🔄 Режим: <code>{mode}</code>\n"
            f"📝 Добавлено: {len(changes)} символов\n"
            f"⏰ Время: {timestamp}",
            parse_mode='HTML'
        )
        
        # Автосинхронизация
        await self.sync_to_gist(update, silent=True)
    
    def find_section_fuzzy(self, target: str, sections: List[str]) -> Optional[str]:
        """Нечеткий поиск секции"""
        target = target.lower()
        
        # Точное совпадение
        for section in sections:
            if section.lower() == target:
                return section
                
        # Частичное совпадение
        for section in sections:
            if target in section.lower() or section.lower() in target:
                return section
                
        return None
    
    async def handle_section_add(self, update: Update, command: Dict):
        """Добавление новой секции"""
        title = command.get('title', '')
        content = command.get('content', '')
        position = command.get('position', 'end')  # end, start, after:section_name
        
        if not title or not content:
            await update.message.reply_text("❌ Укажите title и content")
            return
            
        # Читаем текущую базу
        if self.baza_file.exists():
            existing_content = self.baza_file.read_text(encoding='utf-8')
        else:
            existing_content = ""
            
        # Форматируем новую секцию
        section_header = f"# {title}" if not title.startswith('#') else title
        new_section = f"\n{section_header}\n\n{content}\n"
        
        if position == 'start':
            # Добавляем в начало
            all_content = new_section + '\n' + existing_content
        elif position.startswith('after:'):
            # Добавляем после указанной секции
            target_section = position.split(':', 1)[1]
            sections = self.parse_sections(existing_content)
            found_section = self.find_section_fuzzy(target_section, sections.keys())
            
            if found_section:
                # Реконструируем контент с вставкой
                all_content = self.insert_section_after(existing_content, found_section, new_section)
            else:
                all_content = existing_content + new_section
        else:
            # Добавляем в конец
            all_content = existing_content + new_section
        
        # Сохраняем
        self.baza_file.write_text(all_content, encoding='utf-8')
        
        section_key = self.extract_section_name(title)
        await update.message.reply_text(
            f"✅ <b>Новая секция добавлена!</b>\n\n"
            f"📂 Название: <b>{title}</b>\n"
            f"🔑 Ключ: <code>{section_key}</code>\n"
            f"📝 Размер: {len(content)} символов\n"
            f"📍 Позиция: {position}",
            parse_mode='HTML'
        )
        
        await self.sync_to_gist(update, silent=True)
    
    def insert_section_after(self, content: str, target_section: str, new_section: str) -> str:
        """Вставляет новую секцию после указанной"""
        sections = self.parse_sections(content)
        result_parts = []
        
        for section_name, section_content in sections.items():
            result_parts.append(section_content)
            if section_name == target_section:
                result_parts.append(new_section)
        
        return '\n\n'.join(result_parts)
    
    async def handle_section_replace(self, update: Update, command: Dict):
        """Замена существующей секции"""
        section = command.get('section', '').lower()
        content = command.get('content', '')
        
        if not section or not content:
            await update.message.reply_text("❌ Укажите section и content")
            return
            
        # Используем handle_section_update с режимом replace
        command['mode'] = 'replace'
        command['changes'] = content
        await self.handle_section_update(update, command)
    
    async def handle_section_delete(self, update: Update, command: Dict):
        """Удаление секции"""
        section = command.get('section', '').lower()
        
        if not section:
            await update.message.reply_text("❌ Укажите section")
            return
            
        if not self.baza_file.exists():
            await update.message.reply_text("❌ Файл базы не найден")
            return
            
        content = self.baza_file.read_text(encoding='utf-8')
        sections = self.parse_sections(content)
        
        found_section = self.find_section_fuzzy(section, sections.keys())
        
        if not found_section:
            await update.message.reply_text(f"❌ Секция '{section}' не найдена")
            return
        
        # Удаляем секцию
        del sections[found_section]
        
        # Сохраняем
        await self.save_sections(sections)
        
        await update.message.reply_text(
            f"✅ <b>Секция удалена!</b>\n\n"
            f"📂 Удалена: <code>{found_section}</code>",
            parse_mode='HTML'
        )
        
        await self.sync_to_gist(update, silent=True)
    
    async def handle_read_sections(self, update: Update, command: Dict):
        """Чтение секций базы"""
        filter_pattern = command.get('filter', '')
        limit = command.get('limit', 10)
        detailed = command.get('detailed', False)
        
        if not self.baza_file.exists():
            await update.message.reply_text("❌ Файл базы не найден")
            return
            
        content = self.baza_file.read_text(encoding='utf-8')
        sections = self.parse_sections(content)
        
        # Фильтрация секций
        if filter_pattern:
            filtered_sections = {k: v for k, v in sections.items() 
                               if filter_pattern.lower() in k.lower()}
        else:
            filtered_sections = sections
            
        # Ограничиваем количество
        section_items = list(filtered_sections.items())[:limit]
        
        if not section_items:
            await update.message.reply_text("❌ Секции не найдены")
            return
            
        # Формируем ответ
        if detailed:
            # Детальный вид - отправляем секции по частям
            for i, (key, section_content) in enumerate(section_items, 1):
                header = f"📚 <b>Секция {i}: {key}</b>\n" + "="*40 + "\n"
                
                # Разбиваем контент на части если он большой
                if len(section_content) > 3000:
                    parts = self.split_content(section_content, 3000)
                    for part_num, part in enumerate(parts, 1):
                        part_header = f"{header}Часть {part_num}/{len(parts)}:\n\n" if part_num == 1 else f"Часть {part_num}/{len(parts)} (продолжение):\n\n"
                        await update.message.reply_text(part_header + part, parse_mode='HTML')
                else:
                    await update.message.reply_text(header + section_content, parse_mode='HTML')
        else:
            # Краткий обзор
            response = f"📚 <b>Секции базы знаний</b> ({len(section_items)}):\n\n"
            
            for i, (key, content) in enumerate(section_items, 1):
                summary = self.get_section_summary(content)
                response += f"{i}. <b>{key}</b>\n   {summary}\n\n"
                
            # Telegram лимит 4096 символов
            if len(response) > 4000:
                response = response[:4000] + "\n\n... (обрезано)"
                
            await update.message.reply_text(response, parse_mode='HTML')
    
    def split_content(self, content: str, max_length: int) -> List[str]:
        """Разбивает контент на части по лимиту символов"""
        if len(content) <= max_length:
            return [content]
            
        parts = []
        lines = content.split('\n')
        current_part = []
        current_length = 0
        
        for line in lines:
            if current_length + len(line) + 1 > max_length and current_part:
                parts.append('\n'.join(current_part))
                current_part = [line]
                current_length = len(line)
            else:
                current_part.append(line)
                current_length += len(line) + 1
        
        if current_part:
            parts.append('\n'.join(current_part))
            
        return parts
    
    async def save_sections(self, sections: Dict[str, str]):
        """Сохраняет секции обратно в файл"""
        # Создаем бэкап
        timestamp = int(datetime.now().timestamp())
        backup_file = Path(f"baza_backup_{timestamp}.txt")
        
        if self.baza_file.exists():
            backup_content = self.baza_file.read_text(encoding='utf-8')
            backup_file.write_text(backup_content, encoding='utf-8')
        
        # Объединяем секции в единый контент
        content_parts = []
        
        for section_name, section_content in sections.items():
            content_parts.append(section_content)
            
        full_content = '\n\n'.join(content_parts)
        
        # Сохраняем новую версию
        self.baza_file.write_text(full_content, encoding='utf-8')
        
        logger.info(f"База сохранена, бэкап: {backup_file}")
    
    async def sync_to_gist(self, update: Update, silent=False):
        """Синхронизация с GitHub Gist"""
        try:
            # Сначала пытаемся использовать наш gist_sync.py
            if Path("gist_sync.py").exists():
                result = subprocess.run(['python3', 'gist_sync.py', 'push'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    if not silent:
                        await update.message.reply_text("🔗 ✅ Синхронизировано через gist_sync.py!")
                    return
            
            # Fallback к git операциям если есть gist директория
            if self.gist_dir.exists() and self.baza_file.exists():
                # Копируем в gist папку
                gist_file = self.gist_dir / "gistfile1.txt"
                content = self.baza_file.read_text(encoding='utf-8')
                gist_file.write_text(content, encoding='utf-8')
                
                # Git операции
                original_cwd = os.getcwd()
                os.chdir(self.gist_dir)
                
                subprocess.run(['git', 'add', '.'], check=True, capture_output=True)
                subprocess.run(['git', 'commit', '-m', f'Smart Bot Update - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'], 
                             check=True, capture_output=True)
                subprocess.run(['git', 'push'], check=True, capture_output=True)
                
                os.chdir(original_cwd)
                
                if not silent:
                    await update.message.reply_text("🔗 ✅ Синхронизировано с GitHub Gist!")
                    
        except Exception as e:
            if not silent:
                await update.message.reply_text(f"❌ Ошибка синхронизации: {e}")
            logger.error(f"Sync error: {e}")
    
    async def handle_text_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных текстовых команд"""
        text = update.message.text.lower()
        
        if 'показать секции' in text or 'список секций' in text:
            await self.show_sections(update)
        elif 'статус' in text:
            await self.show_status(update)
        elif text.startswith('добавь в секцию'):
            # Простая команда добавления
            await update.message.reply_text(
                "💡 Используйте JSON формат:\n\n"
                "<code>{\n"
                '  "action": "update_section",\n'
                '  "section": "название_секции",\n'
                '  "changes": "новый контент"\n'
                "}</code>",
                parse_mode='HTML'
            )
    
    async def show_sections(self, update: Update):
        """Показать список всех секций"""
        if not self.baza_file.exists():
            await update.message.reply_text("❌ Файл базы не найден")
            return
            
        content = self.baza_file.read_text(encoding='utf-8')
        sections = self.parse_sections(content)
        
        if not sections:
            await update.message.reply_text("❌ Секции не найдены")
            return
            
        response = f"📚 <b>Секции базы знаний</b> ({len(sections)}):\n\n"
        
        for i, (key, content) in enumerate(sections.items(), 1):
            size = len(content)
            lines = len(content.split('\n'))
            response += f"{i}. <code>{key}</code> ({size} симв, {lines} строк)\n"
            
        # Разбиваем если слишком длинное
        if len(response) > 4000:
            parts = self.split_content(response, 4000)
            for part in parts:
                await update.message.reply_text(part, parse_mode='HTML')
        else:
            await update.message.reply_text(response, parse_mode='HTML')
    
    async def show_status(self, update: Update):
        """Показать статус системы"""
        file_exists = self.baza_file.exists()
        gist_exists = self.gist_dir.exists()
        gist_sync_exists = Path("gist_sync.py").exists()
        
        if file_exists:
            content = self.baza_file.read_text(encoding='utf-8')
            sections = self.parse_sections(content)
            file_size = len(content)
            sections_count = len(sections)
            modified = datetime.fromtimestamp(self.baza_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        else:
            file_size = 0
            sections_count = 0
            modified = "Не найден"
            
        status_text = f"""📊 <b>Статус Smart Baza Bot</b>

📁 <b>Локальный файл:</b>
{'✅' if file_exists else '❌'} baza.txt
📄 Размер: {file_size} символов
📚 Секций: {sections_count}
🕒 Изменен: {modified}

🔗 <b>Синхронизация:</b>
{'✅' if gist_sync_exists else '❌'} gist_sync.py
{'✅' if gist_exists else '❌'} Папка gist-baza

🤖 <b>Бот готов к работе</b>
👥 Авторизованы: {len(self.authorized_users)} пользователей
"""
        
        await update.message.reply_text(status_text, parse_mode='HTML')
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка inline кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'show_sections':
            await self.show_sections(query)
        elif query.data == 'status':
            await self.show_status(query)
        elif query.data == 'sync_gist':
            await self.sync_to_gist(query, silent=False)

# Основная функция
async def main():
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    AUTHORIZED_USERS = os.getenv("AUTHORIZED_USER_IDS", "").split(",")
    
    if not BOT_TOKEN or not AUTHORIZED_USERS[0]:
        print("❌ Установите переменные окружения!")
        print("TELEGRAM_BOT_TOKEN=ваш_токен")
        print("AUTHORIZED_USER_IDS=user_id1,user_id2")
        return
    
    authorized_ids = [int(uid.strip()) for uid in AUTHORIZED_USERS if uid.strip()]
    
    bot = SmartBazaBot(BOT_TOKEN, authorized_ids)
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_json_command))
    application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
    
    print("🚀 Smart Baza Bot запущен!")
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())