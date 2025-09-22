import logging
from functools import partial
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QTableView, QAbstractItemView,
                             QHeaderView, QMessageBox, QMenu, QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QAction

from ui.utils import db_string_to_ui_string
from .sharpen_knives_dialog import SharpenKnivesDialog

class KnivesTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Наименование", "Артикул", "Кол-во (склад)", "Статус", "Последняя заточка", "Интервал, дней"]
        self._data = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)
    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        row_data = self._data[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0: return row_data['name']
            if col == 1: return row_data['sku']
            if col == 2: return str(row_data['qty'])
            if col == 3: return row_data['status'] or 'не отслеживается'
            if col == 4: return db_string_to_ui_string(row_data['last_sharpen_date'])
            if col == 5: return str(row_data['last_interval_days']) if row_data['last_interval_days'] is not None else ''
        if role == Qt.UserRole:
            return row_data['id']
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

class KnivesTab(QWidget):
    def __init__(self, db, event_bus, main_window):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.main_window = main_window
        
        self.init_ui()
        self.event_bus.subscribe("knives.changed", self.refresh_data)
        self.event_bus.subscribe("parts.changed", self.refresh_data) # На случай изменения имени или кол-ва
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._setup_toolbar()
        self._setup_table()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.table_view)

    def _setup_toolbar(self):
        self.toolbar = QToolBar()
        self.sharpen_button = QPushButton("Отправить на заточку...")
        self.refresh_button = QPushButton("Обновить")
        self.toolbar.addWidget(self.sharpen_button)
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(widget)
        self.toolbar.addWidget(self.refresh_button)
        self.sharpen_button.clicked.connect(self.sharpen_selected_knives)
        self.refresh_button.clicked.connect(self.refresh_data)

    def _setup_table(self):
        self.table_model = KnivesTableModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(True)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.create_context_menu)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        # Сортировка по умолчанию: статус, затем дата заточки
        self.table_view.sortByColumn(3, Qt.AscendingOrder) 

    def refresh_data(self):
        logging.info("Обновление данных на вкладке 'Ножи'")
        data = self.db.get_all_knives_data()
        self.table_model.load_data(data)

    def get_selected_part_ids(self):
        selected_rows = self.table_view.selectionModel().selectedRows()
        if not selected_rows: return []
        return [self.proxy_model.mapToSource(index).data(Qt.UserRole) for index in selected_rows]

    def sharpen_selected_knives(self):
        part_ids = self.get_selected_part_ids()
        if not part_ids:
            QMessageBox.warning(self, "Внимание", "Выберите один или несколько ножей для заточки.")
            return
        
        dialog = SharpenKnivesDialog(len(part_ids), self)
        if dialog.exec():
            data = dialog.get_data()
            success, message = self.db.sharpen_knives(part_ids, data['date'], data['comment'])
            if success:
                QMessageBox.information(self, "Успех", message)
                self.event_bus.emit("knives.changed")
            else:
                QMessageBox.critical(self, "Ошибка", message)

    def create_context_menu(self, position):
        part_ids = self.get_selected_part_ids()
        if not part_ids: return

        menu = QMenu()
        status_menu = menu.addMenu("Изменить статус")
        
        statuses = ['в работе', 'наточен', 'затуплен']
        for status in statuses:
            action = status_menu.addAction(status)
            action.triggered.connect(partial(self.change_status_for_selected, status))
            
        menu.exec(self.table_view.viewport().mapToGlobal(position))

    def change_status_for_selected(self, new_status):
        part_ids = self.get_selected_part_ids()
        if not part_ids: return

        # Выполняем смену статуса для каждого ножа индивидуально
        for part_id in part_ids:
            success, message = self.db.update_knife_status(part_id, new_status)
            if not success:
                QMessageBox.critical(self, "Ошибка", f"Не удалось изменить статус для ножа ID {part_id}: {message}")
                # Прерываемся при первой ошибке
                break
        
        self.event_bus.emit("knives.changed")

