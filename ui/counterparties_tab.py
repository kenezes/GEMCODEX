import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableView,
                             QPushButton, QLineEdit, QAbstractItemView,
                             QHeaderView, QMessageBox, QMenu)
from PySide6.QtCore import (Qt, QAbstractTableModel, QModelIndex,
                          QSortFilterProxyModel)
from PySide6.QtGui import QAction

from .counterparty_dialog import CounterpartyDialog

class CounterpartiesTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.init_ui()
        self.refresh_data()
        self.event_bus.subscribe('counterparties.changed', self.refresh_data)
        logging.info("Subscribed refresh_data to 'counterparties.changed'")

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Панель управления
        control_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по наименованию...")
        self.search_input.textChanged.connect(self.filter_data)
        
        add_button = QPushButton("Создать контрагента")
        add_button.clicked.connect(self.add_counterparty)
        
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh_data)

        control_layout.addWidget(self.search_input)
        control_layout.addStretch()
        control_layout.addWidget(add_button)
        control_layout.addWidget(refresh_button)
        layout.addLayout(control_layout)

        # Таблица
        self.table_view = QTableView()
        self.table_model = CounterpartyTableModel()
        
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterKeyColumn(0) # Фильтр по наименованию
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        
        self.table_view.setModel(self.proxy_model)
        self.setup_table_view()
        layout.addWidget(self.table_view)
        
    def setup_table_view(self):
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.handle_double_click)
        
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        
    def refresh_data(self, *args, **kwargs):
        counterparties = self.db.get_all_counterparties()
        self.table_model.set_data(counterparties)

    def filter_data(self, text):
        self.proxy_model.setFilterFixedString(text)

    def add_counterparty(self):
        dialog = CounterpartyDialog(self.db, self.event_bus, parent=self)
        if dialog.exec():
            self.refresh_data()

    def edit_counterparty(self, counterparty_id):
        dialog = CounterpartyDialog(self.db, self.event_bus, counterparty_id=counterparty_id, parent=self)
        if dialog.exec():
            # Сигнал уже отправлен из диалога, refresh_data вызовется автоматически
            pass

    def delete_counterparty(self, counterparty_id):
        counterparty = self.db.get_counterparty_by_id(counterparty_id)
        if not counterparty:
            QMessageBox.warning(self, "Ошибка", "Контрагент не найден.")
            return

        reply = QMessageBox.question(self, "Удаление контрагента",
            f"Вы уверены, что хотите удалить контрагента '{counterparty['name']}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success, message = self.db.delete_counterparty(counterparty_id)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.event_bus.emit("counterparties.changed") # Используем emit
            else:
                QMessageBox.warning(self, "Ошибка удаления", message)

    def handle_double_click(self, index):
        source_index = self.proxy_model.mapToSource(index)
        counterparty_id = self.table_model.get_id_from_index(source_index)
        if counterparty_id:
            self.edit_counterparty(counterparty_id)

    def show_context_menu(self, pos):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        counterparty_id = self.table_model.get_id_from_index(source_index)
        if not counterparty_id:
            return

        menu = QMenu(self)
        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(lambda: self.edit_counterparty(counterparty_id))
        menu.addAction(edit_action)

        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self.delete_counterparty(counterparty_id))
        menu.addAction(delete_action)
        
        menu.exec(self.table_view.viewport().mapToGlobal(pos))


class CounterpartyTableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = ["Наименование", "Адрес", "Контактное лицо", "Телефон", "Email", "Комментарий"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row_data = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return row_data.get('name')
            if col == 1: return row_data.get('address')
            if col == 2: return row_data.get('contact_person')
            if col == 3: return row_data.get('phone')
            if col == 4: return row_data.get('email')
            if col == 5: return row_data.get('note')
        
        if role == Qt.UserRole:
            return row_data.get('id')

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()
    
    def get_id_from_index(self, index):
        if not index.isValid():
            return None
        return self.data(index, role=Qt.UserRole)

