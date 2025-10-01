from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QDateEdit,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import QDate

from .utils import qdate_to_db_string, db_string_to_qdate


class PeriodicTaskDialog(QDialog):
    def __init__(self, db, event_bus, task_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.task_id = task_id
        self._loading = False

        self.setWindowTitle(
            "Редактирование периодической работы" if task_id else "Новая периодическая работа"
        )

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.title_edit = QLineEdit()
        form_layout.addRow("Название*:", self.title_edit)

        self.equipment_combo = QComboBox()
        self.equipment_combo.addItem("Не выбрано", None)
        form_layout.addRow("Аппарат:", self.equipment_combo)

        self.part_combo = QComboBox()
        self.part_combo.addItem("Не выбрана", None)
        self.part_combo.setEnabled(False)
        form_layout.addRow("Запчасть:", self.part_combo)

        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 3650)
        self.period_spin.setValue(30)
        form_layout.addRow("Периодичность (дн.)*:", self.period_spin)

        self.last_date_checkbox = QCheckBox("Указать дату последнего выполнения")
        self.last_date_edit = QDateEdit(QDate.currentDate())
        self.last_date_edit.setCalendarPopup(True)
        self.last_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.last_date_edit.setVisible(False)
        self.last_date_checkbox.toggled.connect(self.last_date_edit.setVisible)
        form_layout.addRow(self.last_date_checkbox, self.last_date_edit)

        layout.addLayout(form_layout)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.equipment_combo.currentIndexChanged.connect(self._on_equipment_changed)

        self._load_equipment_items()

        if self.task_id:
            self._load_task()
        else:
            self._load_parts_for_equipment(None)

    def _load_equipment_items(self):
        for equipment in self.db.get_all_equipment():
            name = equipment['name']
            sku = equipment.get('sku')
            display = f"{name} ({sku})" if sku else name
            self.equipment_combo.addItem(display, equipment['id'])

    def _load_parts_for_equipment(self, equipment_id):
        self.part_combo.blockSignals(True)
        self.part_combo.clear()
        self.part_combo.addItem("Не выбрана", None)

        if equipment_id:
            parts = self.db.get_parts_for_equipment(equipment_id)
            for part in parts:
                part_name = part.get('part_name') or "Без названия"
                sku = part.get('part_sku')
                qty = part.get('installed_qty')
                fragments = []
                if sku:
                    fragments.append(sku)
                if qty:
                    fragments.append(f"{qty} шт.")
                if fragments:
                    part_name = f"{part_name} ({', '.join(fragments)})"
                data = (part.get('equipment_part_id'), part.get('equipment_id'))
                self.part_combo.addItem(part_name, data)

        self.part_combo.setEnabled(bool(equipment_id))
        self.part_combo.blockSignals(False)

    def _load_task(self):
        task = self.db.get_periodic_task_by_id(self.task_id)
        if not task:
            QMessageBox.critical(self, "Ошибка", "Периодическая работа не найдена.")
            self.reject()
            return

        self._loading = True
        self.title_edit.setText(task.get('title') or "")
        self.period_spin.setValue(int(task.get('period_days') or 1))

        equipment_id = task.get('equipment_id')
        if equipment_id and self.equipment_combo.findData(equipment_id) == -1:
            display_name = task.get('equipment_name') or f"Оборудование #{equipment_id}"
            self.equipment_combo.addItem(display_name, equipment_id)

        if equipment_id:
            index = self.equipment_combo.findData(equipment_id)
            if index != -1:
                self.equipment_combo.setCurrentIndex(index)
        self._loading = False

        self._load_parts_for_equipment(equipment_id)

        equipment_part_id = task.get('equipment_part_id')
        if equipment_part_id:
            data = (equipment_part_id, equipment_id)
            part_index = self.part_combo.findData(data)
            if part_index != -1:
                self.part_combo.setCurrentIndex(part_index)
            else:
                part_name = task.get('part_name') or f"Запчасть #{equipment_part_id}"
                sku = task.get('part_sku')
                if sku:
                    part_name = f"{part_name} ({sku})"
                self.part_combo.addItem(part_name, data)
                self.part_combo.setCurrentIndex(self.part_combo.count() - 1)
                self.part_combo.setEnabled(True)

        last_completed = task.get('last_completed_date')
        if last_completed:
            self.last_date_checkbox.setChecked(True)
            self.last_date_edit.setDate(db_string_to_qdate(last_completed))

    def _on_equipment_changed(self, index):
        if self._loading:
            return
        equipment_id = self.equipment_combo.itemData(index)
        self._load_parts_for_equipment(equipment_id)

    def accept(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Периодическая работа", "Укажите название работы.")
            return

        period_days = self.period_spin.value()
        equipment_id = self.equipment_combo.currentData()
        part_data = self.part_combo.currentData()
        equipment_part_id = None

        if isinstance(part_data, tuple) and part_data[0]:
            equipment_part_id = part_data[0]
            if not equipment_id:
                equipment_id = part_data[1]

        last_date = None
        if self.last_date_checkbox.isChecked():
            last_date = qdate_to_db_string(self.last_date_edit.date())

        if self.task_id:
            success, message = self.db.update_periodic_task(
                self.task_id,
                title,
                period_days,
                equipment_id,
                equipment_part_id,
                last_date,
            )
        else:
            success, message = self.db.add_periodic_task(
                title,
                period_days,
                equipment_id,
                equipment_part_id,
                last_date,
            )

        if not success:
            QMessageBox.warning(self, "Периодическая работа", message)
            return

        self.event_bus.emit("periodic_tasks.changed")
        super().accept()
