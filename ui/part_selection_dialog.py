import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QTableView, QHeaderView, 
    QDialogButtonBox
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

class PartSelectionTableModel(QAbstractTableModel):
    """Модель данных для таблицы выбора запчастей."""
    def __init__(self, db_conn, parent=None):
        super().__init__(parent)
        self.db = db_conn
        self._headers = ["Наименование", "Артикул", "Остаток"]
        self._data = [] # [id, name, sku, qty, price]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            # Отображаем только name, sku, qty
            return self._data[index.row()][index.column() + 1]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None
    
    def get_part_data(self, row):
        """Возвращает полные данные о запчасти по номеру строки."""
        if 0 <= row < len(self._data):
            part = self._data[row]
            return {"id": part[0], "name": part[1], "sku": part[2], "price": part[4]}
        return None

    def fetch_data(self, search_term=""):
        try:
            query = "SELECT id, name, sku, qty, price FROM parts"
            params = []
            if search_term:
                query += " WHERE name LIKE ? OR sku LIKE ?"
                params.extend([f"%{search_term}%", f"%{search_term}%"])
            query += " ORDER BY name"
            
            cursor = self.db.conn.cursor()
            cursor.execute(query, params)
            self.beginResetModel()
            self._data = cursor.fetchall()
            self.endResetModel()
        except Exception as e:
            logging.error(f"Ошибка поиска запчастей: {e}")


class PartSelectionDialog(QDialog):
    """Диалог для поиска и выбора запчасти со склада."""
    def __init__(self, db_conn, parent=None):
        super().__init__(parent)
        self.db = db_conn
        self.selected_part = None
        
        self.setWindowTitle("Выбор запчасти со склада")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по наименованию/артикулу...")
        self.search_input.textChanged.connect(self.on_search)
        
        self.table_model = PartSelectionTableModel(self.db)
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setEditTriggers(QTableView.NoEditTriggers)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.doubleClicked.connect(self.accept_selection)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept_selection)
        self.button_box.rejected.connect(self.reject)
        
        layout.addWidget(self.search_input)
        layout.addWidget(self.table_view)
        layout.addWidget(self.button_box)
        
        self.on_search("") # Initial load

    def on_search(self, text):
        self.table_model.fetch_data(text)

    def accept_selection(self):
        selected_rows = self.table_view.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        self.selected_part = self.table_model.get_part_data(selected_rows[0].row())
        self.accept()

    def get_selected_part(self):
        return self.selected_part
