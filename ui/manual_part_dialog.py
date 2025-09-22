from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QMessageBox, QSpinBox
)
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCore import QLocale

class ManualPartDialog(QDialog):
    """Диалоговое окно для ручного ввода новой позиции в заказ."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить позицию вручную")
        
        # Используем QLocale.c() для точки в качестве разделителя - это более надежно
        self.validator = QDoubleValidator(0, 9999999.99, 2)
        self.validator.setLocale(QLocale.c()) # Замена locale на QLocale

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.sku_edit = QLineEdit()
        self.qty_spinbox = QSpinBox()
        self.qty_spinbox.setRange(1, 99999)
        self.price_edit = QLineEdit("0.00") # Устанавливаем значение по умолчанию
        self.price_edit.setValidator(self.validator)

        form_layout.addRow("Наименование*:", self.name_edit)
        form_layout.addRow("Артикул*:", self.sku_edit)
        form_layout.addRow("Количество*:", self.qty_spinbox)
        form_layout.addRow("Цена*:", self.price_edit)
        
        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def accept(self):
        """Проверяет данные перед закрытием."""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Поле 'Наименование' обязательно.")
            return
        if not self.sku_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Поле 'Артикул' обязательно.")
            return
        if not self.price_edit.text().strip():
             QMessageBox.warning(self, "Ошибка", "Поле 'Цена' обязательно.")
             return
        try:
            # Дополнительная проверка, что цена может быть преобразована в число
            float(self.price_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Поле 'Цена' должно быть числом.")
            return
        super().accept()

    def get_data(self):
        """Возвращает введенные данные."""
        try:
            # QDoubleValidator с QLocale.c() уже гарантирует точку как разделитель
            price = round(float(self.price_edit.text()), 2)
        except ValueError:
            price = 0.0

        return {
            "name": self.name_edit.text().strip(),
            "sku": self.sku_edit.text().strip(),
            "qty": self.qty_spinbox.value(),
            "price": price
        }

