import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_parser import ScheduleParser

FULL_TIME_JSON = r"C:\Users\user\Downloads\Telegram Desktop\очноеkomp1.json"
PART_TIME_JSON = r"C:\Users\user\Downloads\Telegram Desktop\заочноеkomp1.json"

def test_group(group_number):
    parser = ScheduleParser(FULL_TIME_JSON, PART_TIME_JSON)
    schedule = parser.get_schedule_for_group(group_number)
    print(f"Расписание для группы {group_number}:")
    if isinstance(schedule, str):
        print(schedule)
    else:
        for lesson in schedule:
            print(lesson)

if __name__ == "__main__":
    # Укажите существующую группу из вашего json, например:
    test_group("Б141-01") 