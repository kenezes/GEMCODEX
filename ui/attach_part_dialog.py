import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableView, QMessageBox, QAbstractItemView,
                               QSpinBox)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem

from .part_dialog import PartDialog

class AttachPartDialog(QDialog):
    def __init__(self, db, event_bus, equipment_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.equipment_id = equipment_id
        self.setWindowTitle("Привязка запчасти к оборудованию")
        self.setMinimumSize(600, 400)

        self.layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите наименование или артикул...")
        self.search_input.textChanged.connect(self.filter_parts)
        top_layout.addWidget(self.search_input)
        
        self.add_new_part_button = QPushButton("+ Новая запчасть")
        self.add_new_part_button.clicked.connect(self.add_new_part)
        top_layout.addWidget(self.add_new_part_button)
        
        self.layout.addLayout(top_layout)

        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_model = QStandardItemModel(self)
        self.table_model.setHorizontalHeaderLabels(["Наименование", "Артикул", "На складе, шт."])
        
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterKeyColumn(-1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.layout.addWidget(self.table_view)

        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Установленное количество, шт.:"))
        self.installed_qty_input = QSpinBox()
        self.installed_qty_input.setMinimum(1)
        self.installed_qty_input.setMaximum(999999)
        self.installed_qty_input.setValue(1)
        qty_layout.addWidget(self.installed_qty_input)
        qty_layout.addStretch()
        self.layout.addLayout(qty_layout)

        self.button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.button_box.addStretch()
        self.button_box.addWidget(self.ok_button)
        self.button_box.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_box)

        self.event_bus.subscribe("parts.changed", self.on_parts_changed)
        self.load_parts()
        
    def load_parts(self):
        """Загружает список НЕПРИВЯЗАННЫХ запчастей из БД в таблицу."""
        self.table_model.removeRows(0, self.table_model.rowCount())
        # Используем новый метод для получения только доступных для привязки запчастей
        parts = self.db.get_unattached_parts(self.equipment_id)
        for part in parts:
            row = [
                QStandardItem(part['name']),
                QStandardItem(part['sku']),
                QStandardItem(str(part['qty']))
            ]
            row[0].setData(part['id'], Qt.UserRole)
            self.table_model.appendRow(row)
        self.table_view.resizeColumnsToContents()

    def filter_parts(self, text):
        self.proxy_model.setFilterFixedString(text)
        
    def add_new_part(self):
        dialog = PartDialog(self.db, self.event_bus, parent=self)
        dialog.exec()

    def on_parts_changed(self):
        logging.info("AttachPartDialog received 'parts.changed' signal, reloading parts list.")
        self.load_parts()

    def get_selected_part_id(self):
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            return None
        
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        item = self.table_model.itemFromIndex(source_index)
        return item.data(Qt.UserRole)

    def accept(self):
        part_id = self.get_selected_part_id()
        if part_id is None:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите запчасть из списка.")
            return

        installed_qty = self.installed_qty_input.value()
        if installed_qty <= 0:
            QMessageBox.warning(self, "Ошибка", "Установленное количество должно быть больше нуля.")
            return

        success, message = self.db.attach_part_to_equipment(self.equipment_id, part_id, installed_qty)

        if success:
            logging.info(f"Part {part_id} attached to equipment {self.equipment_id}")
            self.event_bus.emit("equipment_parts_changed", self.equipment_id)
            super().accept()
        else:
            QMessageBox.warning(self, "Ошибка привязки", message)

    def closeEvent(self, event):
        self.event_bus.unsubscribe("parts.changed", self.on_parts_changed)
        super().closeEvent(event)

