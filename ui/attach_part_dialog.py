import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTableView, QMessageBox, QAbstractItemView,
                               QSpinBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem

from .part_dialog import PartDialog
from .utils import apply_table_compact_style

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
        self.table_view.setSortingEnabled(False)

        self.table_model = QStandardItemModel(self)
        self.table_model.setHorizontalHeaderLabels(["Наименование", "Артикул", "На складе, шт."])
        self.table_view.setModel(self.table_model)
        apply_table_compact_style(self.table_view)
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
        self.all_parts = []
        self._row_types: list[str] = []
        self.load_parts()

    def load_parts(self):
        """Загружает список НЕПРИВЯЗАННЫХ запчастей из БД в таблицу."""
        parts = self.db.get_unattached_parts(self.equipment_id)
        self.all_parts = parts
        self._display_parts(parts)

    def filter_parts(self, text):
        self._display_parts(self.all_parts, text)

    def _display_parts(self, parts, filter_text=""):
        self.table_model.removeRows(0, self.table_model.rowCount())
        self._row_types = []
        filter_text = (filter_text or "").strip().lower()

        current_category = None
        for part in parts:
            searchable_text = f"{part['name']} {part['sku'] or ''}".lower()
            if filter_text and filter_text not in searchable_text:
                continue

            category_name = part.get('category_name') or "Без категории"
            if category_name != current_category:
                header_item = QStandardItem(category_name)
                header_font = header_item.font()
                header_font.setBold(True)
                header_item.setFont(header_font)
                header_item.setFlags(Qt.ItemIsEnabled)

                placeholders = [QStandardItem(""), QStandardItem("")]
                for item in placeholders:
                    item.setFlags(Qt.ItemIsEnabled)

                self.table_model.appendRow([header_item, *placeholders])
                self._row_types.append('header')
                current_category = category_name

            row = [
                QStandardItem(part['name']),
                QStandardItem(part['sku'] or ""),
                QStandardItem(str(part['qty']))
            ]
            row[0].setData(part['id'], Qt.UserRole)
            self.table_model.appendRow(row)
            self._row_types.append('part')

        self.table_view.resizeColumnsToContents()
        self._update_vertical_header_numbers()

    def _update_vertical_header_numbers(self):
        part_counter = 1
        for row, row_type in enumerate(self._row_types):
            if row_type == 'header':
                label = ""
            else:
                label = str(part_counter)
                part_counter += 1
            self.table_model.setHeaderData(row, Qt.Vertical, label, Qt.DisplayRole)
            if label:
                self.table_model.setHeaderData(row, Qt.Vertical, Qt.AlignCenter, Qt.TextAlignmentRole)
            else:
                self.table_model.setHeaderData(row, Qt.Vertical, Qt.AlignLeft, Qt.TextAlignmentRole)

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

        item = self.table_model.itemFromIndex(selected_indexes[0])
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

