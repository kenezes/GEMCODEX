from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QDateEdit,
    QCheckBox,
    QDialogButtonBox,
    QMessageBox,
    QWidget,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QHBoxLayout,
    QAbstractItemView,
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QHeaderView

from .utils import db_string_to_qdate, qdate_to_db_string


class TaskDialog(QDialog):
    def __init__(self, db, event_bus, task_id=None, parent=None, preselected_parts=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.task_id = task_id
        self.preselected_parts = preselected_parts or []
        self._loaded_task_parts = []
        self._suspend_equipment_signal = False

        self.setWindowTitle("Редактирование задачи" if self.task_id else "Новая задача")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.title_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.priority_combo = QComboBox()
        self.status_combo = QComboBox()
        self.assignee_combo = QComboBox()
        self.equipment_combo = QComboBox()

        self.replacement_checkbox = QCheckBox("Задача на замену")
        self.replacement_checkbox.toggled.connect(self.on_replacement_toggled)

        self.due_date_checkbox = QCheckBox("Установить срок")
        self.due_date_edit = QDateEdit(QDate.currentDate().addDays(7))
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.due_date_edit.setVisible(False)
        self.due_date_checkbox.toggled.connect(self.due_date_edit.setVisible)

        self.priority_combo.addItems(['низкий', 'средний', 'высокий'])
        self.status_combo.addItems(['в работе', 'выполнена', 'отменена', 'на стопе'])

        form_layout.addRow("Задача*:", self.title_edit)
        form_layout.addRow("Описание:", self.description_edit)
        form_layout.addRow("Приоритет*:", self.priority_combo)
        form_layout.addRow("Статус*:", self.status_combo)
        form_layout.addRow(self.due_date_checkbox, self.due_date_edit)
        form_layout.addRow("Исполнитель:", self.assignee_combo)
        form_layout.addRow("Оборудование:", self.equipment_combo)
        form_layout.addRow("Тип задачи:", self.replacement_checkbox)

        layout.addLayout(form_layout)

        self.replacement_container = QWidget()
        replacement_layout = QVBoxLayout(self.replacement_container)
        replacement_layout.setContentsMargins(0, 0, 0, 0)

        hint_layout = QHBoxLayout()
        hint_layout.setContentsMargins(0, 0, 0, 0)
        self.replacement_hint_label = QLabel("Отметьте запчасти, которые требуется заменить.")
        hint_layout.addWidget(self.replacement_hint_label)
        hint_layout.addStretch()
        replacement_layout.addLayout(hint_layout)

        self.replacement_table = QTableWidget(0, 5)
        self.replacement_table.setHorizontalHeaderLabels([
            "Выбрать",
            "Запчасть",
            "Артикул",
            "Установлено",
            "Списать, шт.",
        ])
        self.replacement_table.verticalHeader().setVisible(False)
        self.replacement_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.replacement_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        replacement_layout.addWidget(self.replacement_table)

        self.replacement_container.setVisible(False)
        layout.addWidget(self.replacement_container)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.equipment_combo.currentIndexChanged.connect(self.on_equipment_changed)

        self.load_combos_data()

        if self.task_id:
            self.load_task_data()
        else:
            if self.preselected_parts:
                preselected_equipment_id = self.preselected_parts[0].get('equipment_id')
                if preselected_equipment_id:
                    self._set_equipment_selection(preselected_equipment_id)
                self.replacement_checkbox.setChecked(True)

    def load_combos_data(self):
        self.assignee_combo.addItem("Не назначен", None)
        for colleague in self.db.get_all_colleagues():
            self.assignee_combo.addItem(colleague['name'], colleague['id'])

        self.equipment_combo.addItem("Не выбрано", None)
        for equipment in self.db.get_all_equipment():
            self.equipment_combo.addItem(f"{equipment['name']} ({equipment['sku'] or 'б/а'})", equipment['id'])

    def load_task_data(self):
        task = self.db.get_task_by_id(self.task_id)
        if not task:
            QMessageBox.critical(self, "Ошибка", "Задача не найдена.")
            self.reject()
            return

        self.title_edit.setText(task['title'])
        self.description_edit.setPlainText(task.get('description') or "")
        self.priority_combo.setCurrentText(task['priority'])
        self.status_combo.setCurrentText(task['status'])

        if task['due_date']:
            self.due_date_checkbox.setChecked(True)
            self.due_date_edit.setDate(db_string_to_qdate(task['due_date']))

        if task['assignee_id']:
            assignee_index = self.assignee_combo.findData(task['assignee_id'])
            if assignee_index != -1:
                self.assignee_combo.setCurrentIndex(assignee_index)

        if task['equipment_id']:
            self._set_equipment_selection(task['equipment_id'])

        self._loaded_task_parts = self.db.get_task_parts(self.task_id)
        self.replacement_checkbox.setChecked(bool(task.get('is_replacement')))

    def _set_equipment_selection(self, equipment_id):
        index = self.equipment_combo.findData(equipment_id)
        if index != -1:
            self._suspend_equipment_signal = True
            self.equipment_combo.setCurrentIndex(index)
            self._suspend_equipment_signal = False
            self.on_equipment_changed(index)

    def on_equipment_changed(self, _index):
        if self._suspend_equipment_signal:
            return
        if not self.replacement_checkbox.isChecked():
            return
        equipment_id = self.equipment_combo.currentData()
        self.populate_replacement_table(equipment_id)

    def on_replacement_toggled(self, checked):
        self.replacement_container.setVisible(checked)
        if checked:
            equipment_id = self.equipment_combo.currentData()
            if not equipment_id:
                self.replacement_hint_label.setText("Выберите оборудование, чтобы добавить запчасти на замену.")
                self.replacement_table.setRowCount(0)
            else:
                self.replacement_hint_label.setText("Отметьте запчасти, которые требуется заменить.")
                self.populate_replacement_table(equipment_id)
        else:
            self.replacement_table.setRowCount(0)

    def _initial_replacement_parts_map(self):
        initial = {}
        for part in self.preselected_parts:
            equipment_part_id = part.get('equipment_part_id')
            if not equipment_part_id:
                continue
            qty = part.get('qty') or part.get('installed_qty') or 1
            initial[equipment_part_id] = max(1, int(qty))

        for part in self._loaded_task_parts:
            equipment_part_id = part.get('equipment_part_id')
            if not equipment_part_id:
                continue
            qty = part.get('qty') or 1
            initial[equipment_part_id] = max(1, int(qty))

        return initial

    def populate_replacement_table(self, equipment_id):
        self.replacement_table.setRowCount(0)
        if not equipment_id:
            return

        parts = self.db.get_parts_for_equipment(equipment_id)
        if not parts:
            self.replacement_hint_label.setText("На выбранном оборудовании нет привязанных запчастей.")
            return

        initial_map = self._initial_replacement_parts_map()
        self.replacement_hint_label.setText("Отметьте запчасти, которые требуется заменить.")

        for row, part in enumerate(parts):
            self.replacement_table.insertRow(row)

            checkbox = QCheckBox()
            self.replacement_table.setCellWidget(row, 0, checkbox)

            part_item = QTableWidgetItem(part['part_name'])
            part_item.setData(Qt.UserRole, {
                'equipment_part_id': part['equipment_part_id'],
                'part_id': part['part_id'],
            })
            self.replacement_table.setItem(row, 1, part_item)

            sku_item = QTableWidgetItem(part.get('part_sku') or "")
            self.replacement_table.setItem(row, 2, sku_item)

            installed_qty = part.get('installed_qty') or 1
            installed_item = QTableWidgetItem(str(installed_qty))
            installed_item.setTextAlignment(Qt.AlignCenter)
            self.replacement_table.setItem(row, 3, installed_item)

            spinbox = QSpinBox()
            initial_qty = initial_map.get(part['equipment_part_id'], installed_qty)
            max_qty = max(installed_qty, initial_qty)
            spinbox.setRange(1, max_qty)
            spinbox.setValue(initial_qty)
            self.replacement_table.setCellWidget(row, 4, spinbox)

            if part['equipment_part_id'] in initial_map:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)

    def collect_replacement_parts(self):
        parts = []
        for row in range(self.replacement_table.rowCount()):
            checkbox = self.replacement_table.cellWidget(row, 0)
            if not checkbox or not checkbox.isChecked():
                continue

            part_item = self.replacement_table.item(row, 1)
            if not part_item:
                continue
            part_data = part_item.data(Qt.UserRole) or {}

            spinbox = self.replacement_table.cellWidget(row, 4)
            qty = spinbox.value() if isinstance(spinbox, QSpinBox) else 0

            parts.append({
                'equipment_part_id': part_data.get('equipment_part_id'),
                'part_id': part_data.get('part_id'),
                'qty': qty,
            })

        return parts

    def accept(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Ошибка валидации", "Поле 'Задача' обязательно для заполнения.")
            return

        description = self.description_edit.toPlainText().strip()
        priority = self.priority_combo.currentText()
        status = self.status_combo.currentText()
        due_date = qdate_to_db_string(self.due_date_edit.date()) if self.due_date_checkbox.isChecked() else None
        assignee_id = self.assignee_combo.currentData()
        equipment_id = self.equipment_combo.currentData()
        is_replacement = self.replacement_checkbox.isChecked()

        replacement_parts = []
        if is_replacement:
            if not equipment_id:
                QMessageBox.warning(self, "Ошибка валидации", "Для задачи на замену необходимо выбрать оборудование.")
                return
            replacement_parts = self.collect_replacement_parts()
            if not replacement_parts:
                QMessageBox.warning(self, "Ошибка валидации", "Выберите хотя бы одну запчасть для замены.")
                return

        if self.task_id:
            success, message, events = self.db.update_task(
                self.task_id,
                title,
                description,
                priority,
                due_date,
                assignee_id,
                equipment_id,
                status,
                is_replacement,
                replacement_parts,
            )
        else:
            success, message, events = self.db.add_task(
                title,
                description,
                priority,
                due_date,
                assignee_id,
                equipment_id,
                status,
                is_replacement,
                replacement_parts,
            )

        if success:
            equipment_ids = set(events.get('equipment_ids', []))
            for equipment_id in equipment_ids:
                self.event_bus.emit("equipment_parts_changed", equipment_id)

            if events.get('parts_changed'):
                self.event_bus.emit("parts.changed")
            if events.get('replacements_changed'):
                self.event_bus.emit("replacements.changed")

            self.event_bus.emit("tasks.changed")
            super().accept()
        else:
            QMessageBox.critical(self, "Ошибка", message)
