import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableView, QHeaderView,
                             QAbstractItemView, QGroupBox, QDateEdit, QComboBox,
                             QPushButton, QMessageBox, QMenu, QHBoxLayout, QLabel)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, QDate
from PySide6.QtGui import QAction

from .edit_replacement_dialog import EditReplacementDialog
from .utils import db_string_to_ui_string, qdate_to_db_string

class ReplacementsTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Дата", "Оборудование", "Запчасть (Наименование)", "Артикул", "Категория", "Кол-во", "Причина"]
        self._data = []

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
            if col == 0: return db_string_to_ui_string(row_data['date'])
            if col == 1: return row_data['equipment_name']
            if col == 2: return row_data['part_name']
            if col == 3: return row_data['part_sku']
            if col == 4: return row_data.get('part_category_name', '')
            if col == 5: return str(row_data['qty'])
            if col == 6: return row_data['reason']
        
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

class ReplacementHistoryTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.init_ui()
        self.load_combobox_data()
        self.connect_events()
        self.refresh_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        filters_group = QGroupBox("Фильтры")
        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(16)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.part_category_combo = QComboBox()
        self.equipment_combo = QComboBox()
        
        self.delete_button = QPushButton("Удалить запись")
        self.delete_button.clicked.connect(self.delete_selected_replacement)

        period_container = QWidget()
        period_container_layout = QVBoxLayout(period_container)
        period_container_layout.setContentsMargins(0, 0, 0, 0)
        period_container_layout.setSpacing(4)
        period_label = QLabel("Период")
        period_label.setStyleSheet("font-weight: 500;")
        period_inputs_layout = QHBoxLayout()
        period_inputs_layout.setContentsMargins(0, 0, 0, 0)
        period_inputs_layout.setSpacing(6)
        period_inputs_layout.addWidget(QLabel("с:"))
        period_inputs_layout.addWidget(self.start_date_edit)
        period_inputs_layout.addWidget(QLabel("по:"))
        period_inputs_layout.addWidget(self.end_date_edit)
        period_container_layout.addWidget(period_label)
        period_container_layout.addLayout(period_inputs_layout)

        def build_single_filter(label_text, widget):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: 500;")
            container_layout.addWidget(label)
            container_layout.addWidget(widget)
            return container

        filters_layout.addWidget(period_container)
        filters_layout.addWidget(build_single_filter("Категория запчасти", self.part_category_combo))
        filters_layout.addWidget(build_single_filter("Оборудование", self.equipment_combo))
        filters_layout.addStretch()
        filters_layout.addWidget(self.delete_button)
        
        filters_group.setLayout(filters_layout)

        self.model = ReplacementsTableModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.create_context_menu)
        self.table.doubleClicked.connect(self.edit_selected_replacement)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

        main_layout.addWidget(filters_group)
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)

    def load_combobox_data(self):
        self.part_category_combo.clear()
        self.part_category_combo.addItem("Все категории", 0)
        for cat in self.db.get_part_categories():
            self.part_category_combo.addItem(cat['name'], cat['id'])

        self.equipment_combo.clear()
        self.equipment_combo.addItem("Все оборудование", 0)
        for eq in self.db.get_all_equipment():
            self.equipment_combo.addItem(eq['name'], eq['id'])

    def connect_events(self):
        self.start_date_edit.dateChanged.connect(self.refresh_data)
        self.end_date_edit.dateChanged.connect(self.refresh_data)
        self.part_category_combo.currentIndexChanged.connect(self.refresh_data)
        self.equipment_combo.currentIndexChanged.connect(self.refresh_data)
        self.event_bus.subscribe("replacements.changed", self.refresh_data)
        self.event_bus.subscribe("equipment.changed", self.load_combobox_data)
        self.event_bus.subscribe("parts.changed", self.load_combobox_data)

    def refresh_data(self):
        start_date = qdate_to_db_string(self.start_date_edit.date())
        end_date = qdate_to_db_string(self.end_date_edit.date())
        part_category_id = self.part_category_combo.currentData()
        equipment_id = self.equipment_combo.currentData()
        
        data = self.db.get_all_replacements_filtered(start_date, end_date, part_category_id, equipment_id)
        self.model.load_data(data)

    def get_selected_replacement_id(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            proxy_index = selected_rows[0]
            source_index = self.proxy_model.mapToSource(proxy_index)
            return self.model.data(source_index, Qt.UserRole)
        return None

    def edit_selected_replacement(self):
        replacement_id = self.get_selected_replacement_id()
        if replacement_id:
            dialog = EditReplacementDialog(self.db, self.event_bus, replacement_id, self)
            dialog.exec()
        else:
            QMessageBox.information(self, "Внимание", "Выберите запись для редактирования.")

    def delete_selected_replacement(self):
        replacement_id = self.get_selected_replacement_id()
        if not replacement_id:
            QMessageBox.warning(self, "Внимание", "Выберите запись для удаления.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления",
                                     "Вы уверены, что хотите удалить эту запись из истории?\n\n"
                                     "<b>Внимание:</b> это действие НЕ вернет запчасть на склад.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success, message = self.db.delete_replacement(replacement_id)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.event_bus.emit("replacements.changed")
            else:
                QMessageBox.critical(self, "Ошибка", message)

    def create_context_menu(self, position):
        if not self.get_selected_replacement_id():
            return

        menu = QMenu()
        edit_action = menu.addAction("Редактировать")
        delete_action = menu.addAction("Удалить")
        
        action = menu.exec(self.table.viewport().mapToGlobal(position))

        if action == edit_action:
            self.edit_selected_replacement()
        elif action == delete_action:
            self.delete_selected_replacement()

