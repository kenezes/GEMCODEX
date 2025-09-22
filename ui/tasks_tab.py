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
        controls_layout.addStretch()
        controls_layout.addWidget(self.hide_completed_checkbox)
        controls_layout.addWidget(self.refresh_button)
        layout.addLayout(controls_layout)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Задача", "Комментарий", "Оборудование", "Исполнитель", "Срок", "Статус"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
        # Подключения
        self.create_task_button.clicked.connect(self.create_task)
        self.manage_colleagues_button.clicked.connect(self.manage_colleagues)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.hide_completed_checkbox.toggled.connect(self.filter_tasks)
        self.table.doubleClicked.connect(self.edit_task)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def refresh_data(self, *args, **kwargs):
        self.table.setSortingEnabled(False) # Отключаем сортировку на время загрузки
        self.table.setRowCount(0)
        tasks = self.db.get_all_tasks()

        for row, task in enumerate(tasks):
            self.table.insertRow(row)
            
            # Сохраняем ID в первом столбце
            id_item = QTableWidgetItem()
            id_item.setData(Qt.UserRole, task['id'])
            self.table.setItem(row, 0, id_item)
            
            # Заполняем видимые данные
            self.table.setItem(row, 0, QTableWidgetItem(task['title']))
            self.table.setItem(row, 1, QTableWidgetItem(task['description']))
            self.table.setItem(row, 2, QTableWidgetItem(task['equipment_name']))
            self.table.setItem(row, 3, QTableWidgetItem(task['assignee_name']))
            due_date_str = db_string_to_ui_string(task['due_date']) if task['due_date'] else ""
            self.table.setItem(row, 4, QTableWidgetItem(due_date_str))
            self.table.setItem(row, 5, QTableWidgetItem(task['status']))

            # Устанавливаем цвет
            color = self.priority_colors.get(task['priority'])
            if color:
                for col in range(self.table.columnCount()):
                    # Важно: клонировать итем, чтобы не перезаписать данные UserRole
                    item = self.table.item(row, col).clone()
                    item.setBackground(QBrush(color))
                    self.table.setItem(row, col, item)
            
            # Передаем ID в UserRole для всех ячеек, чтобы работало после сортировки
            task_id = task['id']
            for col in range(self.table.columnCount()):
                self.table.item(row, col).setData(Qt.UserRole, task_id)


        self.table.setSortingEnabled(True)
        self.filter_tasks()

    def filter_tasks(self):
        hide = self.hide_completed_checkbox.isChecked()
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 5)
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
        selected_item = self.table.itemAt(pos)
        if not selected_item:
            return

        row = selected_item.row()
        task_id = self.table.item(row, 0).data(Qt.UserRole)
        if not task_id:
            return

        menu = QMenu(self)
        
        status_menu = menu.addMenu("Изменить статус")
        for status in self.statuses:
            action = QAction(status, self)
            action.triggered.connect(lambda checked=False, s=status, t_id=task_id: self.change_task_status(t_id, s))
            status_menu.addAction(action)

        menu.addSeparator()

        delete_action = QAction("Удалить задачу", self)
        delete_action.triggered.connect(lambda: self.delete_task(task_id, row))
        menu.addAction(delete_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def change_task_status(self, task_id, new_status):
        success, message = self.db.update_task_status(task_id, new_status)
        if success:
            self.event_bus.emit("tasks.changed")
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def delete_task(self, task_id, row):
        title_item = self.table.item(row, 0)
        title = title_item.text() if title_item else ""

        reply = QMessageBox.question(self, "Удаление задачи",
                                   f"Вы уверены, что хотите удалить задачу '{title}'?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.delete_task(task_id)
            if success:
                self.event_bus.emit("tasks.changed")
            else:
                QMessageBox.critical(self, "Ошибка", message)

