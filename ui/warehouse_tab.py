import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableView,
                             QPushButton, QLineEdit, QComboBox, QAbstractItemView,
                             QHeaderView, QMessageBox, QMenu)
from PySide6.QtCore import (Qt, QAbstractTableModel, QModelIndex,
                          QSortFilterProxyModel)
from PySide6.QtGui import QAction

from .part_dialog import PartDialog
from .category_manager_dialog import CategoryManagerDialog

class WarehouseTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.init_ui()
        self.refresh_data()
        self.event_bus.subscribe('parts.changed', self.refresh_data)
        self.event_bus.subscribe('equipment_parts_changed', self.refresh_data)
        self.event_bus.subscribe('replacements.changed', self.refresh_data)
        logging.info("Subscribed WarehouseTab to 'parts.changed', 'equipment_parts_changed', 'replacements.changed'")

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Панель управления
        control_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по наименованию/артикулу...")
        self.search_input.textChanged.connect(self.filter_data)
        
        self.category_filter = QComboBox()
        self.category_filter.currentIndexChanged.connect(self.filter_data)

        add_button = QPushButton("Добавить запчасть")
        add_button.clicked.connect(self.add_part)

        category_button = QPushButton("Категории...")
        category_button.clicked.connect(self.manage_categories)
        
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh_data)

        control_layout.addWidget(self.search_input)
        control_layout.addWidget(self.category_filter)
        control_layout.addStretch()
        control_layout.addWidget(category_button)
        control_layout.addWidget(add_button)
        control_layout.addWidget(refresh_button)
        layout.addLayout(control_layout)

        # Таблица
        self.table_view = QTableView()
        self.table_model = TableModel()
        
        self.proxy_model = CustomSortFilterProxyModel(self.db, self)
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        
        self.table_view.setModel(self.proxy_model)
        self._setup_table()
        layout.addWidget(self.table_view)

    def _setup_table(self):
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.edit_part_from_table)
        
        # Автоширина колонок
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

    def load_categories(self):
        current_cat = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("Все категории", -1)
        categories = self.db.get_part_categories()
        for cat in categories:
            self.category_filter.addItem(cat['name'], cat['id'])
        
        # Восстанавливаем выбор
        index = self.category_filter.findData(current_cat)
        if index != -1:
            self.category_filter.setCurrentIndex(index)
        self.category_filter.blockSignals(False)
    
    def refresh_data(self, *args, **kwargs):
        logging.info("Refreshing warehouse data...")
        self.load_categories()
        parts_data = self.db.get_all_parts()
        self.table_model.set_data(parts_data)
        self.filter_data() # Применяем фильтры после обновления
        logging.info("Warehouse data refreshed.")

    def filter_data(self):
        search_text = self.search_input.text()
        category_id = self.category_filter.currentData()

        self.proxy_model.set_search_text(search_text)
        self.proxy_model.set_category_id(category_id)
        self.proxy_model.invalidateFilter()
    
    def add_part(self):
        dialog = PartDialog(self.db, self.event_bus, parent=self)
        if dialog.exec():
            self.refresh_data()

    def edit_part_from_table(self, index: QModelIndex):
        proxy_index = self.proxy_model.mapToSource(index)
        part_id = self.table_model.get_id_from_index(proxy_index)
        if part_id is not None:
            dialog = PartDialog(self.db, self.event_bus, part_id=part_id, parent=self)
            if dialog.exec():
                self.refresh_data()

    def delete_part(self, part_id):
        part = self.db.get_part_by_id(part_id)
        if not part:
            QMessageBox.warning(self, "Ошибка", "Запчасть не найдена.")
            return

        reply = QMessageBox.question(self, "Удаление запчасти",
            f"Вы уверены, что хотите удалить запчасть '{part['name']} ({part['sku']})'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success, message = self.db.delete_part(part_id)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.event_bus.emit('parts.changed')
            else:
                QMessageBox.warning(self, "Ошибка удаления", message)

    def manage_categories(self):
        dialog = CategoryManagerDialog(self.db, self)
        if dialog.exec():
            self.event_bus.emit('parts.changed') # Обновляем всё, так как категории могли измениться

    def show_context_menu(self, pos):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        proxy_index = self.proxy_model.mapToSource(index)
        part_id = self.table_model.get_id_from_index(proxy_index)
        if part_id is None:
            return

        menu = QMenu(self)
        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(lambda: self.edit_part_from_table(index))
        menu.addAction(edit_action)

        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self.delete_part(part_id))
        menu.addAction(delete_action)
        
        menu.exec(self.table_view.viewport().mapToGlobal(pos))


class TableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = ['Наименование', 'Артикул', 'Остаток, шт.', 'Минимум, шт.', 'Цена', 'Категория', 'Оборудование']

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
            if col == 1: return row_data.get('sku')
            if col == 2: return row_data.get('qty')
            if col == 3: return row_data.get('min_qty')
            if col == 4: return f"{row_data.get('price', 0):.2f}"
            if col == 5: return row_data.get('category_name')
            if col == 6: return row_data.get('equipment_list', 'нет')
        
        if role == Qt.UserRole:
            return row_data.get('id')

        if role == Qt.TextAlignmentRole:
            if col in [2, 3, 4]:
                return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_id_from_index(self, index: QModelIndex):
        if not index.isValid():
            return None
        return self.data(index, role=Qt.UserRole)

class CustomSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.category_id = -1
        self._db = db

    def set_search_text(self, text):
        self.search_text = text.lower()

    def set_category_id(self, cat_id):
        self.category_id = cat_id

    def filterAcceptsRow(self, source_row, source_parent):
        # Категория
        category_match = True
        if self.category_id != -1:
            cat_index = self.sourceModel().index(source_row, 5, source_parent)
            cat_name = self.sourceModel().data(cat_index)
            # Необходимо получить ID категории из данных, если это возможно,
            # но для простоты фильтруем по имени категории
            categories = self._db.get_part_categories() if self._db else []
            current_category_name = ""
            for cat in categories:
                if cat['id'] == self.category_id:
                    current_category_name = cat['name']
                    break
            category_match = (cat_name == current_category_name)
        
        # Текст
        text_match = True
        if self.search_text:
            name_index = self.sourceModel().index(source_row, 0, source_parent)
            sku_index = self.sourceModel().index(source_row, 1, source_parent)
            name_data = str(self.sourceModel().data(name_index)).lower()
            sku_data = str(self.sourceModel().data(sku_index)).lower()
            text_match = (self.search_text in name_data) or (self.search_text in sku_data)

        return category_match and text_match

