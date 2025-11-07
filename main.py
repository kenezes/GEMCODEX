import os
import sys
import logging
from datetime import datetime, timedelta
from logging import handlers
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QMessageBox,
    QStyle,
)
from PySide6.QtCore import QTimer

from database import Database
from event_bus import EventBus
from ui.dashboard_tab import DashboardTab
from ui.warehouse_tab import WarehouseTab
from ui.counterparties_tab import CounterpartiesTab
from ui.orders_tab import OrdersTab
from ui.equipment_tab import EquipmentTab
from ui.replacement_history_tab import ReplacementHistoryTab
from ui.tasks_tab import TasksTab
from ui.sharpening_tab import SharpeningTab
from ui.log_tab import LogTab
from backup_utils import create_application_backup, get_latest_backup_time

def setup_logging_and_paths():
    """Настраивает логирование и создает необходимые каталоги.

    Returns:
        Path: Путь к основному файлу журнала приложения.
    """
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(process)d:%(thread)d - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            handlers.RotatingFileHandler(
                log_file, maxBytes=5*1024*1024, backupCount=10, encoding='utf-8'
            )
        ]
    )
    Path("./data").mkdir(exist_ok=True)
    Path("./backup").mkdir(exist_ok=True)
    return log_file

class MainWindow(QMainWindow):
    def __init__(self, db, event_bus, log_file: Path, app_root: Path):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.log_file = Path(log_file)
        self.app_root = Path(app_root)
        self.backup_dir = Path(self.db.backup_dir)
        self.setWindowTitle("Система управления запчастями")
        self.setGeometry(100, 100, 1200, 800)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.init_tabs()
        self.setup_backup_timer()

    def init_tabs(self):
        self.dashboard_tab = DashboardTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.dashboard_tab, "Панель")
        
        self.orders_tab = OrdersTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.orders_tab, "Заказы")

        self.counterparties_tab = CounterpartiesTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.counterparties_tab, "Контрагенты")
        
        self.equipment_tab = EquipmentTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.equipment_tab, "Оборудование")

        self.warehouse_tab = WarehouseTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.warehouse_tab, "Склад")

        self.replacement_history_tab = ReplacementHistoryTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.replacement_history_tab, "История замен")
        
        self.tasks_tab = TasksTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.tasks_tab, "Задачи")
        
        self.sharpening_tab = SharpeningTab(self.db, self.event_bus, self)
        self.tabs.addTab(self.sharpening_tab, "Заточка")

        backup_icon = self.style().standardIcon(QStyle.SP_DialogSaveButton)
        self.log_tab = LogTab(
            self.log_file,
            self,
            backup_handler=self.perform_manual_backup,
            backup_icon=backup_icon,
        )
        self.tabs.addTab(self.log_tab, "Логи")

    def setup_backup_timer(self):
        self.backup_timer = QTimer(self)
        self.backup_timer.setInterval(24 * 60 * 60 * 1000)
        self.backup_timer.timeout.connect(lambda: self.perform_backup(auto=True))
        self.backup_timer.start()
        self.ensure_daily_backup()

    def ensure_daily_backup(self):
        last_backup = get_latest_backup_time(self.backup_dir)
        if not last_backup or datetime.now() - last_backup >= timedelta(days=1):
            self.perform_backup(auto=True)
        else:
            logging.info("Автоматический бекап не требуется. Последний: %s", last_backup)

    def perform_manual_backup(self):
        self.perform_backup(auto=False)

    def perform_backup(self, auto: bool):
        success, message, archive_path = create_application_backup(self.app_root, self.backup_dir)
        if success:
            if auto:
                logging.info("Создан автоматический бекап: %s", archive_path)
            else:
                QMessageBox.information(self, "Резервное копирование", message)
        else:
            if auto:
                logging.error("Автоматический бекап не выполнен: %s", message)
            else:
                QMessageBox.critical(self, "Ошибка резервного копирования", message)

    def closeEvent(self, event):
        logging.info("Application closing...")
        self.db.disconnect()
        event.accept()

def main():
    app = QApplication(sys.argv)

    log_file = setup_logging_and_paths()
    logging.info("Application starting...")

    db_path = Path('./data/app.db')
    backup_dir = Path('./backup')
    api_base_url = os.getenv('API_BASE_URL')
    api_token = os.getenv('API_TOKEN')

    try:
        db = Database(
            db_path=str(db_path),
            backup_dir=str(backup_dir),
            api_base_url=api_base_url,
            api_token=api_token,
        )
        db.connect()
    except Exception as e:
        logging.critical(f"Критическая ошибка при инициализации базы данных: {e}", exc_info=True)
        QMessageBox.critical(None, "Ошибка базы данных", f"Не удалось инициализировать базу данных.\n\n{e}\n\nСм. лог-файл для подробностей.")
        sys.exit(1)
    
    event_bus = EventBus()

    window = MainWindow(db, event_bus, log_file, Path.cwd())
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()

