import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QCheckBox, QHeaderView, QAbstractItemView, QMenu, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QAction

from .colleagues_manager_dialog import ColleaguesManagerDialog
from .task_dialog import TaskDialog
from .utils import db_string_to_ui_string

class TasksTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.statuses = ['в работе', 'выполнена', 'отменена', 'на стопе']
        self.priority_colors = {
            'высокий': QColor("#ffcdd2"),
            'средний': QColor("#ffecb3"),
            'низкий': QColor("#fff9c4")
        }
        self.init_ui()
        self.refresh_data()
        self.event_bus.subscribe("tasks.changed", self.refresh_data)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Панель управления
        controls_layout = QHBoxLayout()
        self.create_task_button = QPushButton("Создать задачу")
        self.manage_colleagues_button = QPushButton("Коллеги...")
        self.hide_completed_checkbox = QCheckBox("Скрыть завершённые")
        self.refresh_button = QPushButton("Обновить")
        
        controls_layout.addWidget(self.create_task_button)
        controls_layout.addWidget(self.manage_colleagues_button)
        self.delete_tasks_button = QPushButton("Удалить выбранные")

        controls_layout.addWidget(self.delete_tasks_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.hide_completed_checkbox)
        controls_layout.addWidget(self.refresh_button)
        layout.addLayout(controls_layout)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Задача",
            "Комментарий",
            "Оборудование",
            "Исполнитель",
            "Создана",
            "Срок",
            "Статус",
            "Действия",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

        # Подключения
        self.create_task_button.clicked.connect(self.create_task)
        self.manage_colleagues_button.clicked.connect(self.manage_colleagues)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.hide_completed_checkbox.toggled.connect(self.filter_tasks)
        self.delete_tasks_button.clicked.connect(self.delete_selected_tasks)
        self.table.doubleClicked.connect(self.edit_task)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def refresh_data(self, *args, **kwargs):
        self.table.setSortingEnabled(False) # Отключаем сортировку на время загрузки
        self.table.setRowCount(0)
        tasks = self.db.get_all_tasks()

        for row, task in enumerate(tasks):
            self.table.insertRow(row)

            task_id = task['id']
            title_text = task['title']
            if task.get('is_replacement'):
                title_text = f"[Замена] {title_text}"

            title_item = QTableWidgetItem(title_text)
            description_item = QTableWidgetItem(task.get('description') or "")
            equipment_item = QTableWidgetItem(task.get('equipment_name') or "")
            assignee_item = QTableWidgetItem(task.get('assignee_name') or "")

            created_at = task.get('created_at')
            created_date_str = db_string_to_ui_string(created_at.split(" ")[0]) if created_at else ""
            created_item = QTableWidgetItem(created_date_str)

            due_date_str = db_string_to_ui_string(task['due_date']) if task['due_date'] else ""
            due_item = QTableWidgetItem(due_date_str)
            status_item = QTableWidgetItem(task['status'])

            items = [
                title_item,
                description_item,
                equipment_item,
                assignee_item,
                created_item,
                due_item,
                status_item,
            ]

            for col, item in enumerate(items):
                item.setData(Qt.UserRole, task_id)
                self.table.setItem(row, col, item)

            action_placeholder = QTableWidgetItem("")
            action_placeholder.setData(Qt.UserRole, task_id)
            action_placeholder.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, 7, action_placeholder)

            color = self.priority_colors.get(task['priority'])
            if color:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item = item.clone()
                        item.setBackground(QBrush(color))
                        item.setData(Qt.UserRole, task_id)
                        self.table.setItem(row, col, item)

            action_button = QPushButton("Исполнить задачу")
            action_button.setStyleSheet(
                "QPushButton { background-color: #28a745; color: white; }"
                "QPushButton:hover { background-color: #218838; }"
            )
            action_button.setEnabled(task['status'] != 'выполнена')
            action_button.clicked.connect(lambda _, t_id=task_id: self.complete_task(t_id))
            self.table.setCellWidget(row, 7, action_button)



        self.table.setSortingEnabled(True)
        self.filter_tasks()

    def filter_tasks(self):
        hide = self.hide_completed_checkbox.isChecked()
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 6)
            is_completed = status_item and status_item.text() in ['выполнена', 'отменена']
            self.table.setRowHidden(row, hide and is_completed)
            
    def create_task(self):
        dialog = TaskDialog(self.db, self.event_bus, parent=self)
        dialog.exec()
        
    def edit_task(self, index):
        if not index.isValid(): return
        task_id = self.table.item(index.row(), 0).data(Qt.UserRole)
        if task_id:
            dialog = TaskDialog(self.db, self.event_bus, task_id=task_id, parent=self)
            dialog.exec()
            
    def manage_colleagues(self):
        dialog = ColleaguesManagerDialog(self.db, self)
        if dialog.exec():
            self.event_bus.emit("tasks.changed") # Обновляем задачи, т.к. могли измениться исполнители

    def show_context_menu(self, pos):
        clicked_item = self.table.itemAt(pos)
        if not clicked_item:
            return

        row = clicked_item.row()
        selected_rows = self._get_selected_rows()
        if row not in selected_rows:
            self.table.selectRow(row)
            selected_rows = self._get_selected_rows()

        menu = QMenu(self)

        if len(selected_rows) == 1:
            task_id = self.table.item(row, 0).data(Qt.UserRole)
            if not task_id:
                return

            status_menu = menu.addMenu("Изменить статус")
            for status in self.statuses:
                action = QAction(status, self)
                action.triggered.connect(lambda checked=False, s=status, t_id=task_id: self.change_task_status(t_id, s))
                status_menu.addAction(action)

            menu.addSeparator()

        delete_label = "Удалить задачу" if len(selected_rows) == 1 else f"Удалить {len(selected_rows)} задач"
        delete_action = QAction(delete_label, self)
        if len(selected_rows) == 1:
            title_item = self.table.item(row, 0)
            task_id = title_item.data(Qt.UserRole) if title_item else None
            task_title = title_item.text() if title_item else ""
            delete_action.triggered.connect(
                lambda checked=False, t_id=task_id, t_title=task_title: self._delete_tasks([t_id], [t_title])
            )
        else:
            delete_action.triggered.connect(self.delete_selected_tasks)
        menu.addAction(delete_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def change_task_status(self, task_id, new_status):
        success, message, events = self.db.update_task_status(task_id, new_status)
        if success:
            self._handle_task_events(events)
            self.event_bus.emit("tasks.changed")
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def complete_task(self, task_id):
        if not task_id:
            return
        self.change_task_status(task_id, 'выполнена')

    def _handle_task_events(self, events: dict):
        equipment_ids = set(events.get('equipment_ids', []))
        for equipment_id in equipment_ids:
            self.event_bus.emit("equipment_parts_changed", equipment_id)

        if events.get('parts_changed'):
            self.event_bus.emit("parts.changed")
        if events.get('replacements_changed'):
            self.event_bus.emit("replacements.changed")

    def delete_selected_tasks(self):
        rows = self._get_selected_rows()
        if not rows:
            QMessageBox.information(self, "Удаление задач", "Не выбрано ни одной задачи.")
            return

        task_ids = []
        titles = []
        for row in rows:
            item = self.table.item(row, 0)
            if not item:
                continue
            task_id = item.data(Qt.UserRole)
            if not task_id:
                continue
            task_ids.append(task_id)
            titles.append(item.text())

        if not task_ids:
            return

        self._delete_tasks(task_ids, titles)

    def _get_selected_rows(self):
        return sorted({index.row() for index in self.table.selectedIndexes()})

    def _delete_tasks(self, task_ids, titles):
        if not task_ids:
            return

        valid_pairs = [(t_id, title) for t_id, title in zip(task_ids, titles) if t_id]
        if not valid_pairs:
            return

        task_ids = [pair[0] for pair in valid_pairs]
        titles = [pair[1] for pair in valid_pairs]

        if len(task_ids) == 1:
            prompt = f"Вы уверены, что хотите удалить задачу '{titles[0]}'?"
        else:
            previews = '\n'.join(f"• {title}" for title in titles[:5])
            if len(titles) > 5:
                previews += "\n…"
            prompt = (
                f"Удалить выбранные задачи ({len(task_ids)} шт.)?\n\n" + previews
            )

        reply = QMessageBox.question(
            self,
            "Удаление задач",
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        affected_equipment_ids = set()

        for task_id in task_ids:
            success, message, events = self.db.delete_task(task_id)
            if not success:
                QMessageBox.critical(self, "Ошибка", message)
                break
            affected_equipment_ids.update(events.get('equipment_ids', []))
        else:
            if affected_equipment_ids:
                self._handle_task_events({'equipment_ids': affected_equipment_ids})
            self.event_bus.emit("tasks.changed")

