from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit,
                             QComboBox, QDateEdit, QCheckBox, QDialogButtonBox, QMessageBox)
from PySide6.QtCore import QDate, Qt
from .utils import db_string_to_qdate, qdate_to_db_string

class TaskDialog(QDialog):
    def __init__(self, db, event_bus, task_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.task_id = task_id
        
        self.setWindowTitle("Редактирование задачи" if self.task_id else "Новая задача")
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.title_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.priority_combo = QComboBox()
        self.status_combo = QComboBox()
        self.assignee_combo = QComboBox()
        self.equipment_combo = QComboBox()
        
        self.due_date_checkbox = QCheckBox("Установить срок")
        self.due_date_edit = QDateEdit(QDate.currentDate().addDays(7))
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.due_date_edit.setVisible(False)
        self.due_date_checkbox.toggled.connect(self.due_date_edit.setVisible)

        # Populate combos
        self.priority_combo.addItems(['низкий', 'средний', 'высокий'])
        self.status_combo.addItems(['в работе', 'выполнена', 'отменена', 'на стопе'])
        
        form_layout.addRow("Задача*:", self.title_edit)
        form_layout.addRow("Описание:", self.description_edit)
        form_layout.addRow("Приоритет*:", self.priority_combo)
        form_layout.addRow("Статус*:", self.status_combo)
        form_layout.addRow(self.due_date_checkbox, self.due_date_edit)
        form_layout.addRow("Исполнитель:", self.assignee_combo)
        form_layout.addRow("Оборудование:", self.equipment_combo)

        layout.addLayout(form_layout)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.load_combos_data()
        if self.task_id:
            self.load_task_data()

    def load_combos_data(self):
        self.assignee_combo.addItem("Не назначен", None)
        for c in self.db.get_all_colleagues():
            self.assignee_combo.addItem(c['name'], c['id'])
            
        self.equipment_combo.addItem("Не выбрано", None)
        for e in self.db.get_all_equipment():
            self.equipment_combo.addItem(f"{e['name']} ({e['sku'] or 'б/а'})", e['id'])

    def load_task_data(self):
        task = self.db.get_task_by_id(self.task_id)
        if not task:
            QMessageBox.critical(self, "Ошибка", "Задача не найдена.")
            self.reject()
            return
            
        self.title_edit.setText(task['title'])
        self.description_edit.setText(task['description'])
        self.priority_combo.setCurrentText(task['priority'])
        self.status_combo.setCurrentText(task['status'])
        
        if task['due_date']:
            self.due_date_checkbox.setChecked(True)
            self.due_date_edit.setDate(db_string_to_qdate(task['due_date']))

        if task['assignee_id']:
            assignee_index = self.assignee_combo.findData(task['assignee_id'])
            if assignee_index != -1: self.assignee_combo.setCurrentIndex(assignee_index)
            
        if task['equipment_id']:
            eq_index = self.equipment_combo.findData(task['equipment_id'])
            if eq_index != -1: self.equipment_combo.setCurrentIndex(eq_index)

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

        if self.task_id:
            success, message = self.db.update_task(self.task_id, title, description, priority, due_date, assignee_id, equipment_id, status)
        else:
            success, message = self.db.add_task(title, description, priority, due_date, assignee_id, equipment_id, status)

        if success:
            self.event_bus.emit("tasks.changed")
            super().accept()
        else:
            QMessageBox.critical(self, "Ошибка базы данных", message)
