import datetime
import logging
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QDate, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QTableView

_ROOT_DIR = Path(__file__).resolve().parents[1]
PARTS_FILES_DIR = _ROOT_DIR / "data" / "parts"
EQUIPMENT_FILES_DIR = _ROOT_DIR / "data" / "equipment"

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


def _sanitize_component(value: str, default: str) -> str:
    value = (value or "").strip()
    if not value:
        value = default
    value = value.replace(" ", "_")
    value = re.sub(r"[^\w\-]", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value)
    return value


def _build_folder_name(name: str, sku: str | None, default_sku: str) -> str:
    return f"{_sanitize_component(name, 'Без_названия')}_{_sanitize_component(sku, default_sku)}"


def get_part_folder_path(name: str, sku: str) -> Path:
    return PARTS_FILES_DIR / _build_folder_name(name, sku, "Без_артикула")


def get_equipment_folder_path(name: str, sku: str | None) -> Path:
    return EQUIPMENT_FILES_DIR / _build_folder_name(name, sku, "без_артикула")


def open_folder(path: Path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
    except Exception as exc:  # pragma: no cover - UI feedback only
        logging.error("Не удалось открыть папку %s: %s", path, exc, exc_info=True)
        QMessageBox.critical(None, "Ошибка", f"Не удалось открыть папку:\n{path}\n\n{exc}")


def open_part_folder(name: str, sku: str):
    open_folder(get_part_folder_path(name, sku))


def open_equipment_folder(name: str, sku: str | None):
    open_folder(get_equipment_folder_path(name, sku))


def apply_table_compact_style(table_view: QTableView, *, row_height: int = 28, padding_v: int = 3, padding_h: int = 6):
    """Слегка уменьшает высоту строк таблиц и отступы ячеек."""

    vertical_header = table_view.verticalHeader()
    if vertical_header:
        vertical_header.setDefaultSectionSize(row_height)
        vertical_header.setMinimumSectionSize(row_height - 4 if row_height > 4 else row_height)

    style_sheet = (
        "QTableView::item{padding:%dpx %dpx;}" % (padding_v, padding_h)
    )
    existing_style = table_view.styleSheet()
    if existing_style:
        table_view.setStyleSheet(existing_style + " " + style_sheet)
    else:
        table_view.setStyleSheet(style_sheet)


def _merge_directories(src: Path, dst: Path):
    for item in src.iterdir():
        target = dst / item.name
        if target.exists():
            continue
        shutil.move(str(item), str(target))
    try:
        src.rmdir()
    except OSError:
        shutil.rmtree(src, ignore_errors=True)


def _move_folder_on_rename(base_dir: Path, old_name: str | None, old_sku: str | None,
                           new_name: str, new_sku: str | None, parent, entity_label: str,
                           default_sku: str):
    if not old_name and not old_sku:
        return

    old_path = base_dir / _build_folder_name(old_name or "", old_sku, default_sku)
    new_path = base_dir / _build_folder_name(new_name, new_sku, default_sku)

    if old_path == new_path or not old_path.exists():
        return

    new_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if new_path.exists():
            message_box = QMessageBox(parent)
            message_box.setWindowTitle("Папка уже существует")
            message_box.setText(
                f"Папка для {entity_label} уже существует:\n{new_path}\n\n"
                "Объединить с текущей или пропустить перенос?"
            )
            merge_button = message_box.addButton("Объединить", QMessageBox.AcceptRole)
            skip_button = message_box.addButton("Пропустить", QMessageBox.RejectRole)
            message_box.setDefaultButton(skip_button)
            message_box.exec()

            if message_box.clickedButton() is not merge_button:
                return

            _merge_directories(old_path, new_path)
        else:
            old_path.rename(new_path)
    except Exception as exc:  # pragma: no cover - UI feedback only
        logging.error("Не удалось перенести папку %s в %s: %s", old_path, new_path, exc, exc_info=True)
        QMessageBox.critical(parent, "Ошибка", f"Не удалось перенести папку:\n{exc}")


def move_part_folder_on_rename(old_name: str | None, old_sku: str | None,
                               new_name: str, new_sku: str, parent=None):
    _move_folder_on_rename(PARTS_FILES_DIR, old_name, old_sku, new_name, new_sku,
                           parent, "запчасти", "Без_артикула")


def move_equipment_folder_on_rename(old_name: str | None, old_sku: str | None,
                                    new_name: str, new_sku: str | None, parent=None):
    _move_folder_on_rename(EQUIPMENT_FILES_DIR, old_name, old_sku, new_name, new_sku,
                           parent, "оборудования", "без_артикула")

