from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableView, QHeaderView, QMessageBox, QAbstractItemView)

from .utils import db_string_to_ui_string


class KnifeSharpenHistoryModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Дата", "Комплект", "Артикул", "Комментарий"]
        self._data: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        record = self._data[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return db_string_to_ui_string(record.get("date"))
            if column == 1:
                return record.get("part_name", "")
            if column == 2:
                return record.get("part_sku", "")
            if column == 3:
                return record.get("comment", "")

        if role == Qt.UserRole:
            return record.get("id")

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, rows: list[dict]):
        self.beginResetModel()
        self._data = rows
        self.endResetModel()


class KnifeSharpenHistoryDialog(QDialog):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus

        self.setWindowTitle("История заточек")
        self.resize(800, 400)

        layout = QVBoxLayout(self)

        controls_layout = QHBoxLayout()
        self.delete_button = QPushButton("Удалить запись")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_entry)
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh_data)
        controls_layout.addWidget(self.delete_button)
        controls_layout.addStretch()
        controls_layout.addWidget(refresh_button)

        self.model = KnifeSharpenHistoryModel(self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)

        layout.addLayout(controls_layout)
        layout.addWidget(self.table)

        self.refresh_data()

    def refresh_data(self):
        rows = self.db.get_knife_sharpen_history()
        self.model.load_data(rows)
        self.delete_button.setEnabled(False)

    def on_selection_changed(self, selected, deselected):
        self.delete_button.setEnabled(bool(selected.indexes()))

    def _current_entry_id(self):
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return None
        index = selection[0]
        return self.model.data(index, Qt.UserRole)

    def delete_selected_entry(self):
        entry_id = self._current_entry_id()
        if not entry_id:
            return

        reply = QMessageBox.question(
            self,
            "Удаление записи",
            "Удалить выбранную запись из истории заточек?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        success, message = self.db.delete_knife_sharpen_entry(entry_id)
        if success:
            self.event_bus.emit("knives.changed")
            self.refresh_data()
            QMessageBox.information(self, "Готово", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)
