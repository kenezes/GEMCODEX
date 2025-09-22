from PySide6.QtCore import QDate
import datetime

def db_string_to_ui_string(db_str: str) -> str:
    """Преобразует строку YYYY-MM-DD в ДД.ММ.ГГГГ."""
    if not db_str:
        return ""
    try:
        return datetime.datetime.strptime(db_str, '%Y-%m-%d').strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        return ""

def qdate_to_db_string(qdate: QDate) -> str:
    """Преобразует QDate в строку YYYY-MM-DD."""
    return qdate.toString("yyyy-MM-dd")

def db_string_to_qdate(db_str: str) -> QDate:
    """Преобразует строку YYYY-MM-DD в QDate."""
    if not db_str:
        return QDate.currentDate()
    try:
        dt = datetime.datetime.strptime(db_str, '%Y-%m-%d')
        return QDate(dt.year, dt.month, dt.day)
    except (ValueError, TypeError):
        return QDate.currentDate()

def get_current_date_str_for_db() -> str:
    """Возвращает текущую дату в формате YYYY-MM-DD для БД."""
    return QDate.currentDate().toString("yyyy-MM-dd")

