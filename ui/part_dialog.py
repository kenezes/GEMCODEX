import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                               QPushButton, QMessageBox, QSpinBox, QDoubleSpinBox,
                               QComboBox, QHBoxLayout)
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCore import QLocale

class PartDialog(QDialog):
    def __init__(self, db, event_bus, part_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.part_id = part_id

        self.setWindowTitle("Редактирование запчасти" if self.part_id else "Добавление запчасти")
        
        # Layouts
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # Fields
        self.name_input = QLineEdit()
        self.sku_input = QLineEdit()
        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 999999)
        self.min_qty_input = QSpinBox()
        self.min_qty_input.setRange(0, 999999)
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0.0, 999999999.99)
        self.price_input.setDecimals(2)
        self.price_input.setGroupSeparatorShown(True)
        # Используем QLocale для корректной валидации в разных системах
        c_locale = QLocale(QLocale.Language.C)
        c_locale.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)
        self.price_input.setLocale(c_locale)

        self.category_combo = QComboBox()

        self.form_layout.addRow("Наименование*:", self.name_input)
        self.form_layout.addRow("Артикул*:", self.sku_input)
        self.form_layout.addRow("Остаток, шт.*:", self.qty_input)
        self.form_layout.addRow("Минимум, шт.*:", self.min_qty_input)
        self.form_layout.addRow("Цена*:", self.price_input)
        self.form_layout.addRow("Категория:", self.category_combo)

        self.layout.addLayout(self.form_layout)

        # Buttons
        self.button_box = QHBoxLayout()
        self.ok_button = QPushButton("Сохранить")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.button_box.addStretch()
        self.button_box.addWidget(self.ok_button)
        self.button_box.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_box)

        self.load_categories()
        if self.part_id:
            self.load_part_data()

    def load_categories(self):
        self.category_combo.clear()
        self.category_combo.addItem("", None) # Add an empty option
        categories = self.db.get_part_categories()
        for category in categories:
            self.category_combo.addItem(category['name'], category['id'])

    def load_part_data(self):
        part = self.db.get_part_by_id(self.part_id)
        if part:
            self.name_input.setText(part['name'])
            self.sku_input.setText(part['sku'])
            self.qty_input.setValue(part['qty'])
            self.min_qty_input.setValue(part['min_qty'])
            self.price_input.setValue(part['price'])
            
            category_id = part.get('category_id')
            if category_id:
                index = self.category_combo.findData(category_id)
                if index >= 0:
                    self.category_combo.setCurrentIndex(index)
            else:
                 self.category_combo.setCurrentIndex(0) # Select empty if no category

    def accept(self):
        name = self.name_input.text().strip()
        sku = self.sku_input.text().strip()
        qty = self.qty_input.value()
        min_qty = self.min_qty_input.value()
        price = self.price_input.value()
        category_id = self.category_combo.currentData()

        if not name or not sku:
            QMessageBox.warning(self, "Ошибка валидации", "Поля 'Наименование' и 'Артикул' обязательны.")
            return

        try:
            if self.part_id:
                # Update existing part
                success, message = self.db.update_part(
                    self.part_id, name, sku, qty, min_qty, price, category_id
                )
            else:
                # Add new part
                success, message = self.db.add_part(
                    name, sku, qty, min_qty, price, category_id
                )

            if success:
                logging.info(f"Part data saved successfully for ID: {self.part_id or 'new'}")
                # Используем правильное имя метода 'emit'
                self.event_bus.emit("parts.changed")
                super().accept()
            else:
                QMessageBox.warning(self, "Ошибка сохранения", message)
        except Exception as e:
            logging.error(f"Ошибка сохранения данных запчасти: {e}", exc_info=True)
            QMessageBox.critical(self, "Критическая ошибка", f"Произошла непредвиденная ошибка: {e}")

