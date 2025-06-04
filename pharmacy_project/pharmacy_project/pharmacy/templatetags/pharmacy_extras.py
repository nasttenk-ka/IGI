from django import template
from django.template.defaultfilters import floatformat, stringfilter
from django.utils import timezone
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo

register = template.Library()

@register.filter(name='multiply')
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return floatformat(float(value) * float(arg), 2)
    except (ValueError, TypeError):
        return 0

@register.filter
def month_name(month_number):
    months = {
        1: 'Январь',
        2: 'Февраль',
        3: 'Март',
        4: 'Апрель',
        5: 'Май',
        6: 'Июнь',
        7: 'Июль',
        8: 'Август',
        9: 'Сентябрь',
        10: 'Октябрь',
        11: 'Ноябрь',
        12: 'Декабрь'
    }
    return months.get(month_number, '')

@register.simple_tag
def get_current_time(timezone_name=None):
    """Return current time in specified timezone or default timezone"""
    if timezone_name:
        current_time = datetime.now(ZoneInfo(timezone_name))
    else:
        current_time = timezone.now()
    return current_time.strftime("%d/%m/%Y %H:%M:%S")

@register.simple_tag
def get_current_date(timezone_name=None):
    """Return current date in specified timezone or default timezone"""
    if timezone_name:
        current_time = datetime.now(ZoneInfo(timezone_name))
    else:
        current_time = timezone.now()
    return current_time.strftime("%d/%m/%Y")

@register.simple_tag
def format_datetime_timezone(dt, timezone_name):
    """Format datetime to specified timezone"""
    if dt.tzinfo is None:
        dt = timezone.make_aware(dt)
    converted_dt = dt.astimezone(ZoneInfo(timezone_name))
    return converted_dt.strftime("%d/%m/%Y %H:%M:%S")

@register.simple_tag
def get_calendar(year=None, month=None):
    """Return calendar for specified month and year in text format"""
    if year is None or month is None:
        now = timezone.now()
        year = now.year
        month = now.month
    
    cal = calendar.monthcalendar(year, month)
    month_name = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }[month]
    
    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    
    # Формируем заголовок календаря
    result = [f"{month_name} {year}"]
    result.append('-' * 28)
    
    # Добавляем дни недели
    result.append(' '.join(f"{day:^4}" for day in weekdays))
    result.append('-' * 28)
    
    # Добавляем дни месяца
    for week in cal:
        week_str = []
        for day in week:
            if day == 0:
                week_str.append('    ')
            else:
                week_str.append(f"{day:^4}")
        result.append(' '.join(week_str))
    
    return '\n'.join(result)

@register.filter(name='addclass')
def addclass(field, css_class):
    """Добавляет CSS класс к полю формы"""
    return field.as_widget(attrs={'class': css_class}) 