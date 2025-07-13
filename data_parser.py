import ijson
from datetime import datetime, timedelta

class ScheduleParser:
    def __init__(self, full_time_json_path, part_time_json_path):
        self.full_time_json_path = full_time_json_path
        self.part_time_json_path = part_time_json_path
        self.type_map = {
            "л.": "Лекция",
            "пр.": "Практика",
            "лаб.": "Лабораторная"
        }

    def format_teacher(self, teacher):
        return f"{teacher.get('teacher_post', '')} {teacher.get('teacher_name', '')}"

    def _get_json_path(self, edu_form):
        if edu_form == 'full_time':
            return self.full_time_json_path
        elif edu_form == 'part_time':
            return self.part_time_json_path
        else:
            raise ValueError("Неизвестная форма обучения")

    def get_schedule_for_group(self, group_number, edu_form='full_time'):
        try:
            print(f'group_number: {group_number}')
            schedule = []
            json_path = self._get_json_path(edu_form)
            print(f'json_path: {json_path}')
            import json
            with open(json_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                # data — список объектов с timetable
                weeks = []
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'timetable' in item:
                            weeks.extend(item['timetable'])
                elif isinstance(data, dict) and 'timetable' in data:
                    weeks = data['timetable']
                else:
                    weeks = []
                group_number_norm = group_number.strip().lower()
                for week in weeks:
                    for group in week.get('groups', []):
                        group_name = str(group.get('group_name', '')).strip().lower()
                        if group_name == group_number_norm:
                            for day in group.get('days', []) or []:
                                for lesson in day.get('lessons', []) or []:
                                    # Преподаватели
                                    teachers = []
                                    for t in lesson.get('teachers', []) or []:
                                        if isinstance(t, dict):
                                            teachers.append(t.get('teacher_name', ''))
                                        else:
                                            teachers.append(str(t))
                                    # Аудитория
                                    room = ''
                                    auds = lesson.get('auditories', [])
                                    if auds and isinstance(auds, list) and len(auds) > 0:
                                        room = auds[0].get('auditory_name', '')
                                    # Приводим дату к формату YYYY-MM-DD
                                    date_str = lesson.get('date', '')
                                    try:
                                        if '-' in date_str and len(date_str.split('-')[2]) == 4:
                                            d, m, y = date_str.split('-')
                                            date_str = f'{int(y):04d}-{int(m):02d}-{int(d):02d}'
                                    except Exception:
                                        pass
                                    schedule.append({
                                        'subject': lesson.get('subject', ''),
                                        'type': self.type_map.get(lesson.get('type', ''), lesson.get('type', '')),
                                        'time_start': lesson.get('time_start', ''),
                                        'time_end': lesson.get('time_end', ''),
                                        'room': room,
                                        'teachers': teachers,
                                        'subgroup': lesson.get('subgroup', 0),
                                        'date': date_str
                                    })
            return schedule if schedule else "Расписание для группы не найдено"
        except ValueError as ve:
            print(f'ValueError: {ve}')
            return str(ve)
        except Exception as e:
            print(f'Exception: {e}')
            return f"Ошибка при чтении расписания: {str(e)}"

    def get_week_schedule(self, group_number, week_offset=0, edu_form='full_time'):
        schedule = self.get_schedule_for_group(group_number, edu_form=edu_form)
        if isinstance(schedule, str):
            return schedule

        # Получаем список недель из json
        weeks = []
        data = None
        try:
            import json
            json_path = self._get_json_path(edu_form)
            with open(json_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'timetable' in item:
                        weeks.extend(item['timetable'])
            elif isinstance(data, dict) and 'timetable' in data:
                weeks = data['timetable']
        except Exception:
            pass

        if week_offset < len(weeks):
            week = weeks[week_offset]
            date_start = week.get('date_start', '')
            date_end = week.get('date_end', '')
            # Привести к формату YYYY-MM-DD
            def to_iso(date_str):
                try:
                    if '-' in date_str and len(date_str.split('-')[2]) == 4:
                        d, m, y = date_str.split('-')
                        return f'{int(y):04d}-{int(m):02d}-{int(d):02d}'
                except Exception:
                    pass
                return date_str
            date_start_iso = to_iso(date_start)
            date_end_iso = to_iso(date_end)
        else:
            return {}

        week_schedule = {}
        for lesson in schedule:
            date = lesson.get('date', '')
            if date >= date_start_iso and date <= date_end_iso:
                if date not in week_schedule:
                    week_schedule[date] = []
                week_schedule[date].append(lesson)
        return week_schedule

    def get_today_schedule(self, group_number, edu_form='full_time'):
        schedule = self.get_schedule_for_group(group_number, edu_form=edu_form)
        if isinstance(schedule, str):
            return schedule
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_schedule = [
            lesson for lesson in schedule 
            if lesson.get('date') == today
        ]
        
        # Сортируем по времени начала
        today_schedule.sort(key=lambda x: x.get('time_start', ''))
        return today_schedule if today_schedule else "На сегодня занятий нет"

    def get_available_groups(self):
        """Получаем список всех доступных групп"""
        groups = {'full_time': [], 'part_time': []}
        
        # Читаем группы очного обучения
        try:
            with open(self.full_time_json_path, 'rb') as file:
                parser = ijson.parse(file)
                for prefix, event, value in parser:
                    if prefix.endswith('.group_name'):
                        groups['full_time'].append(value)
        except Exception:
            pass

        # Читаем группы заочного обучения
        try:
            with open(self.part_time_json_path, 'rb') as file:
                parser = ijson.parse(file)
                for prefix, event, value in parser:
                    if prefix.endswith('.group_name'):
                        groups['part_time'].append(value)
        except Exception:
            pass

        return groups 