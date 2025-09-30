from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)


class EditAttachedPartDialog(QDialog):
    """Диалог редактирования привязанной запчасти."""

    def __init__(self, name: str, sku: str, installed_qty: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование привязанной запчасти")

        main_layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.name_input = QLineEdit(name)
        self.sku_input = QLineEdit(sku)
        self.qty_input = QSpinBox()
        self.qty_input.setMinimum(1)
        self.qty_input.setMaximum(999999)
        self.qty_input.setValue(max(1, installed_qty))

        form_layout.addRow("Наименование:", self.name_input)
        form_layout.addRow("Артикул:", self.sku_input)
        form_layout.addRow("Установлено, шт.:", self.qty_input)

        main_layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self._on_accept)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)

        main_layout.addLayout(buttons_layout)

    def _on_accept(self):
        name = self.name_input.text().strip()
        sku = self.sku_input.text().strip()

        if not name or not sku:
            QMessageBox.warning(self, "Ошибка валидации", "Наименование и артикул не могут быть пустыми.")
            return

        self.accept()

    def get_values(self) -> tuple[str, str, int]:
        return (
            self.name_input.text().strip(),
            self.sku_input.text().strip(),
            self.qty_input.value(),
        )

