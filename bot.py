import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from data_parser import ScheduleParser
from datetime import datetime, timedelta
import re
from telegram.constants import ChatAction

# Загрузка переменных окружения
load_dotenv()
# BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_TOKEN = 
FULL_TIME_JSON = 
PART_TIME_JSON = 

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация парсера
schedule_parser = ScheduleParser(FULL_TIME_JSON, PART_TIME_JSON)

GROUPS_PER_PAGE = 10

ADMIN_IDS = [848245861]  # fattakh77

def natural_group_sort(groups):
    def alphanum_key(key):
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', key)]
    return sorted(groups, key=alphanum_key)

def get_group_buttons(groups, page=0, my_group=None):
    start = page * GROUPS_PER_PAGE
    end = start + GROUPS_PER_PAGE
    buttons = []
    shown = set()
    if my_group and my_group in groups:
        buttons.append([InlineKeyboardButton(f'⭐ {my_group}', callback_data=f'group_{my_group}')])
        shown.add(my_group)
    for group in groups[start:end]:
        if group not in shown:
            buttons.append([InlineKeyboardButton(group, callback_data=f'group_{group}')])
            shown.add(group)
    nav_buttons = []
    if start > 0:
        nav_buttons.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'group_page_{page-1}'))
    if end < len(groups):
        nav_buttons.append(InlineKeyboardButton('Вперёд ➡️', callback_data=f'group_page_{page+1}'))
    if nav_buttons:
        buttons.append(nav_buttons)
    return buttons

def get_week_label(week_offset):
    # Получаем список недель из json
    weeks = []
    data = None
    try:
        import json
        with open(FULL_TIME_JSON, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'timetable' in item:
                    weeks.extend(item['timetable'])
        elif isinstance(data, dict) and 'timetable' in data:
            weeks = data['timetable']
    except Exception:
        pass
    # week_offset = 0 — первая неделя, 1 — вторая и т.д.
    if week_offset < len(weeks):
        week = weeks[week_offset]
        start = week.get('date_start', '')
        end = week.get('date_end', '')
        return f'Неделя {week_offset+1} ({start}–{end})'
    else:
        return f'Неделя {week_offset+1}'

def get_dates_for_group_with_lessons(edu_form, group_number):
    dates = set()
    try:
        import json
        json_path = FULL_TIME_JSON if edu_form == 'full_time' else PART_TIME_JSON
        with open(json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        weeks = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'timetable' in item:
                    weeks.extend(item['timetable'])
        elif isinstance(data, dict) and 'timetable' in data:
            weeks = data['timetable']
        group_number_norm = group_number.strip().lower()
        for week in weeks:
            for group in week.get('groups', []):
                group_name = str(group.get('group_name', '')).strip().lower()
                if group_name == group_number_norm:
                    for day in group.get('days', []) or []:
                        if day.get('lessons'):
                            for lesson in day.get('lessons', []) or []:
                                date = lesson.get('date', '')
                                if date:
                                    dates.add(date)
    except Exception:
        pass
    return sorted(list(dates))

def to_iso(date_str):
    try:
        if '-' in date_str and len(date_str.split('-')[2]) == 4:
            d, m, y = date_str.split('-')
            return f'{int(y):04d}-{int(m):02d}-{int(d):02d}'
    except Exception:
        pass
    return date_str

async def send_or_edit(update, context, text, reply_markup=None, force_new_message=False):
    if force_new_message:
        # Новое сообщение (для расписания и финального меню)
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        # Редактируем предыдущее сообщение с кнопками
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            elif hasattr(update, 'message') and update.message:
                await update.message.edit_text(text, reply_markup=reply_markup)
        except Exception:
            # Если не удалось отредактировать — отправляем новое
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
            elif hasattr(update, 'message') and update.message:
                await update.message.reply_text(text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton('Очная', callback_data='edu_full_time')],
        [InlineKeyboardButton('Заочная', callback_data='edu_part_time')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit(update, context, 'Выберите форму обучения:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action.startswith('edu_'):
        edu_form = 'full_time' if action == 'edu_full_time' else 'part_time'
        context.user_data['edu_form'] = edu_form
        groups = schedule_parser.get_available_groups()[edu_form]
        groups = list(set(groups))
        groups = natural_group_sort(groups)
        my_group = context.user_data.get('my_group')
        keyboard = get_group_buttons(groups, page=0, my_group=my_group)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit(update, context, 'Выберите группу:', reply_markup=reply_markup)
        return

    edu_form = context.user_data.get('edu_form', 'full_time')
    groups = schedule_parser.get_available_groups()[edu_form]
    groups = list(set(groups))
    groups = natural_group_sort(groups)
    my_group = context.user_data.get('my_group')

    if action.startswith('group_page_'):
        page = int(action.split('_')[2])
        context.user_data['group_page'] = page
        keyboard = get_group_buttons(groups, page=page, my_group=my_group)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)
        return
    elif action.startswith('group_') and not action.startswith('group_page_') and action[6:] not in ('', None) and not action[6:].startswith('page_'):
        group_number = action.replace('group_', '', 1)
        context.user_data['group_number'] = group_number
        context.user_data['my_group'] = group_number  # Сохраняем как "мою группу"
        keyboard = [
            [InlineKeyboardButton('Сегодня', callback_data='today')],
            [InlineKeyboardButton('Неделя', callback_data='week')],
            [InlineKeyboardButton('Выбрать дату', callback_data='pick_date')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit(update, context, f'Группа {group_number}. Выберите, что показать:', reply_markup=reply_markup)
        return
    elif action == 'my_group':
        group_number = context.user_data.get('my_group')
        if not group_number:
            await send_or_edit(update, context, 'Сначала выберите свою группу!', force_new_message=True)
            return
        context.user_data['group_number'] = group_number
        keyboard = [
            [InlineKeyboardButton('Сегодня', callback_data='today')],
            [InlineKeyboardButton('Неделя', callback_data='week')],
            [InlineKeyboardButton('Выбрать дату', callback_data='pick_date')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit(update, context, f'Группа {group_number}. Выберите, что показать:', reply_markup=reply_markup)
        return
    elif action == 'today':
        context.user_data['action'] = action
        group_number = context.user_data.get('group_number')
        if not group_number:
            await send_or_edit(update, context, 'Сначала выберите группу!', force_new_message=True)
            return
        schedule = schedule_parser.get_today_schedule(group_number, edu_form=edu_form)
        if isinstance(schedule, str):
            await send_or_edit(update, context, schedule, force_new_message=True)
        else:
            if not schedule:
                await send_or_edit(update, context, 'На сегодня занятий нет.', force_new_message=True)
            else:
                msg = f'📅 Расписание на сегодня для {group_number}:\n\n'
                for lesson in schedule:
                    msg += (f"{lesson['time_start']} - {lesson['time_end']}: {lesson['subject']} ({lesson['type']})\n"
                            f"ауд. {room_humanize(lesson['room'])}, преп. {', '.join(lesson['teachers'])}\n\n")
                await send_or_edit(update, context, msg, force_new_message=True)
        keyboard = [[InlineKeyboardButton('Далее', callback_data='next')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text('Хотите посмотреть другое расписание? Нажмите "Далее".', reply_markup=reply_markup)
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text('Хотите посмотреть другое расписание? Нажмите "Далее".', reply_markup=reply_markup)
        return
    elif action == 'week':
        context.user_data['action'] = 'week'
        group_number = context.user_data.get('group_number')
        if not group_number:
            await send_or_edit(update, context, 'Сначала выберите группу!', force_new_message=True)
            return
        week_offset = 0
        context.user_data['week_offset'] = week_offset
        week_keyboard = [
            [
                InlineKeyboardButton('⬅️', callback_data='week_prev'),
                InlineKeyboardButton(get_week_label(week_offset), callback_data='week_show'),
                InlineKeyboardButton('➡️', callback_data='week_next')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(week_keyboard)
        await send_or_edit(update, context, 'Выберите неделю:', reply_markup=reply_markup)
        return
    elif action == 'pick_date' or (action.startswith('date_page_')):
        group_number = context.user_data.get('group_number')
        if not group_number:
            await send_or_edit(update, context, 'Сначала выберите группу!', force_new_message=True)
            return
        all_dates = get_dates_for_group_with_lessons(edu_form, group_number)
        def date_key(d):
            try:
                if '-' in d and len(d.split('-')[2]) == 4:
                    day, month, year = d.split('-')
                    return int(year), int(month), int(day)
                elif '-' in d and len(d.split('-')[0]) == 4:
                    year, month, day = d.split('-')
                    return int(year), int(month), int(day)
            except Exception:
                pass
            return (9999, 99, 99)
        all_dates = sorted(all_dates, key=date_key)
        DATES_PER_PAGE = 10
        if action == 'pick_date':
            page = 0
        else:
            page = int(action.split('_')[-1])
        context.user_data['date_page'] = page
        start = page * DATES_PER_PAGE
        end = start + DATES_PER_PAGE
        date_buttons = []
        for d in all_dates[start:end]:
            date_buttons.append([InlineKeyboardButton(d, callback_data=f'date_{d}')])
        nav_buttons = []
        if start > 0:
            nav_buttons.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'date_page_{page-1}'))
        if end < len(all_dates):
            nav_buttons.append(InlineKeyboardButton('Вперёд ➡️', callback_data=f'date_page_{page+1}'))
        if nav_buttons:
            date_buttons.append(nav_buttons)
        reply_markup = InlineKeyboardMarkup(date_buttons)
        await send_or_edit(update, context, 'Выберите дату:', reply_markup=reply_markup)
        return
    elif action == 'week_prev' or action == 'week_next':
        week_offset = context.user_data.get('week_offset', 0)
        if action == 'week_prev':
            week_offset = max(0, week_offset - 1)
        else:
            week_offset = week_offset + 1
        context.user_data['week_offset'] = week_offset
        week_keyboard = [
            [
                InlineKeyboardButton('⬅️', callback_data='week_prev'),
                InlineKeyboardButton(get_week_label(week_offset), callback_data='week_show'),
                InlineKeyboardButton('➡️', callback_data='week_next')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(week_keyboard)
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)
    elif action == 'week_show':
        context.user_data['group_page'] = 0
        keyboard = get_group_buttons(groups, page=0, my_group=my_group)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit(update, context, 'Выберите группу:', reply_markup=reply_markup)
    elif action.startswith('date_'):
        date = action.replace('date_', '')
        context.user_data['action'] = 'date'
        context.user_data['picked_date'] = date
        group_number = context.user_data.get('group_number')
        if not group_number:
            await send_or_edit(update, context, 'Сначала выберите группу!', force_new_message=True)
            return
        schedule = schedule_parser.get_schedule_for_group(group_number, edu_form=edu_form)
        picked_date_iso = to_iso(date)
        lessons = [l for l in schedule if to_iso(l.get('date')) == picked_date_iso]
        if not lessons:
            await send_or_edit(update, context, f'На {date} занятий нет.', force_new_message=True)
        else:
            msg = f'📅 Расписание на {date} для {group_number}:\n\n'
            for lesson in lessons:
                msg += (f"{lesson['time_start']} - {lesson['time_end']}: {lesson['subject']} ({lesson['type']})\n"
                        f"ауд. {room_humanize(lesson['room'])}, преп. {', '.join(lesson['teachers'])}\n\n")
            await send_or_edit(update, context, msg, force_new_message=True)
        keyboard = [[InlineKeyboardButton('Далее', callback_data='next')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text('Хотите посмотреть другое расписание? Нажмите "Далее".', reply_markup=reply_markup)
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text('Хотите посмотреть другое расписание? Нажмите "Далее".', reply_markup=reply_markup)
        return
    elif action == 'next':
        # Сброс выбора группы и даты/недели
        context.user_data.pop('group_number', None)
        context.user_data.pop('picked_date', None)
        context.user_data.pop('week_offset', None)
        groups = schedule_parser.get_available_groups()[edu_form]
        groups = list(set(groups))
        groups = natural_group_sort(groups)
        my_group = context.user_data.get('my_group')
        keyboard = get_group_buttons(groups, page=0, my_group=my_group)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit(update, context, 'Выберите группу:', reply_markup=reply_markup)
        return
    else:
        await send_or_edit(update, context, 'Неизвестная команда', force_new_message=True)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"Ваш user_id: {user_id}")
    if user_id not in ADMIN_IDS:
        await update.message.reply_text('Доступ запрещён.')
        return
    keyboard = [
        [InlineKeyboardButton('Загрузить очный JSON', callback_data='admin_upload_full')],
        [InlineKeyboardButton('Загрузить заочный JSON', callback_data='admin_upload_part')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Админ-панель:', reply_markup=reply_markup)

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.answer('Доступ запрещён.', show_alert=True)
        return
    action = query.data
    if action == 'admin_upload_full':
        context.user_data['admin_upload'] = 'full_time'
        await query.message.reply_text('Отправьте новый файл для очного расписания (JSON) как документ.')
    elif action == 'admin_upload_part':
        context.user_data['admin_upload'] = 'part_time'
        await query.message.reply_text('Отправьте новый файл для заочного расписания (JSON) как документ.')
    await query.answer()

async def admin_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    upload_type = context.user_data.get('admin_upload')
    if not upload_type:
        await update.message.reply_text('Сначала выберите тип загрузки через /admin.')
        return
    file = update.message.document
    if not file:
        await update.message.reply_text('Пришлите файл как документ.')
        return
    await update.message.chat.send_action(action=ChatAction.UPLOAD_DOCUMENT)
    file_path = FULL_TIME_JSON if upload_type == 'full_time' else PART_TIME_JSON
    new_file = await file.get_file()
    await new_file.download_to_drive(file_path)
    # Перезагружаем парсер
    global schedule_parser
    schedule_parser = ScheduleParser(FULL_TIME_JSON, PART_TIME_JSON)
    await update.message.reply_text('Файл успешно загружен и расписание обновлено!')
    context.user_data['admin_upload'] = None

def room_humanize(room: str) -> str:
    """
    Преобразует номер аудитории вида 2-41 в ИМиТС-41 и т.д.
    Примеры:
      1-12 -> ИАиЗ-12
      2-41 -> ИМиТС-41
      3-22 -> ИЭ-22
      4-33 -> ФЛХиЭ-33
    Если не подходит — возвращает исходное значение.
    """
    if not isinstance(room, str):
        return room
    mapping = {'1': 'ИАиЗ', '2': 'ИМиТС', '3': 'ИЭ', '4': 'ФЛХиЭ'}
    match = re.match(r"^([1-4])-(.+)$", room)
    if match:
        prefix, rest = match.groups()
        return f"{mapping[prefix]}-{rest}"
    return room

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CallbackQueryHandler(admin_button_handler, pattern='^admin_'))
    application.add_handler(MessageHandler(filters.Document.ALL, admin_document_handler))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 
