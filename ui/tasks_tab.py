import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QCheckBox,
    QHeaderView,
    QAbstractItemView,
    QMenu,
    QMessageBox,
    QTabWidget,
    QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QAction

from .colleagues_manager_dialog import ColleaguesManagerDialog
from .task_dialog import TaskDialog
from .periodic_task_dialog import PeriodicTaskDialog
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
        self.event_bus.subscribe("periodic_tasks.changed", self.refresh_data)

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Основные задачи
        self.regular_tab = QWidget()
        regular_layout = QVBoxLayout(self.regular_tab)
        regular_layout.setContentsMargins(0, 0, 0, 0)
        self._init_regular_tasks_ui(regular_layout)
        self.tab_widget.addTab(self.regular_tab, "Задачи")

        # Периодические задачи
        self.periodic_tab = QWidget()
        periodic_layout = QVBoxLayout(self.periodic_tab)
        periodic_layout.setContentsMargins(0, 0, 0, 0)
        self._init_periodic_tasks_ui(periodic_layout)
        self.tab_widget.addTab(self.periodic_tab, "Периодические")

    def refresh_data(self, *args, **kwargs):
        self._refresh_regular_tasks()
        self._refresh_periodic_sections()

    def _refresh_regular_tasks(self):
        self.table.setSortingEnabled(False)  # Отключаем сортировку на время загрузки
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

            action_button = QPushButton("Выполнить")
            is_completed = task['status'] == 'выполнена'
            if is_completed:
                style = (
                    "QPushButton { background-color: #2e7d32; color: white; }"
                    "QPushButton:hover { background-color: #1b5e20; }"
                    "QPushButton:disabled { background-color: #2e7d32; color: white; }"
                )
            else:
                style = (
                    "QPushButton { background-color: #c62828; color: white; }"
                    "QPushButton:hover { background-color: #b71c1c; }"
                    "QPushButton:disabled { background-color: #c62828; color: white; }"
                )
            action_button.setStyleSheet(style)
            action_button.setEnabled(not is_completed)
            action_button.clicked.connect(lambda _, t_id=task_id: self.complete_task(t_id))
            self.table.setCellWidget(row, 7, action_button)

        self.table.setSortingEnabled(True)
        self.filter_tasks()

    def _refresh_periodic_sections(self):
        due_tasks = self.db.get_due_periodic_tasks()
        self._populate_periodic_table(self.periodic_due_table, due_tasks, enable_sorting=False)
        self.periodic_due_container.setVisible(bool(due_tasks))

        all_tasks = self.db.get_all_periodic_tasks()
        self._populate_periodic_table(self.periodic_table, all_tasks, enable_sorting=True)

    def _populate_periodic_table(self, table: QTableWidget, tasks: list[dict], enable_sorting: bool):
        table.setSortingEnabled(False)
        table.setRowCount(0)

        for row, task in enumerate(tasks):
            table.insertRow(row)
            self._set_periodic_row(table, row, task)

        if enable_sorting:
            table.setSortingEnabled(True)

        table.resizeColumnsToContents()

    def _set_periodic_row(self, table: QTableWidget, row: int, task: dict):
        task_id = task.get('id')
        subject_text = self._periodic_subject_text(task)
        period_days = task.get('period_days') or ""
        last_date = db_string_to_ui_string(task.get('last_completed_date')) if task.get('last_completed_date') else ""
        next_due = db_string_to_ui_string(task.get('next_due_date')) if task.get('next_due_date') else ""
        days_until_due = task.get('days_until_due')
        days_text = self._format_days_until_due(days_until_due)

        values = [
            task.get('title') or "",
            subject_text,
            str(period_days),
            last_date,
            next_due,
            days_text,
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setData(Qt.UserRole, task_id)
            table.setItem(row, col, item)

        action_button = QPushButton("Выполнить")
        action_button.setCursor(Qt.PointingHandCursor)
        self._set_periodic_button_style(action_button, days_until_due)
        if task_id is not None:
            action_button.clicked.connect(lambda _, t_id=task_id: self.complete_periodic_task(t_id))
        table.setCellWidget(row, 6, action_button)

    @staticmethod
    def _periodic_subject_text(task: dict) -> str:
        equipment_name = task.get('equipment_name') or ""
        part_name = task.get('part_name')
        part_sku = task.get('part_sku')

        if part_name:
            if part_sku:
                part_display = f"{part_name} ({part_sku})"
            else:
                part_display = part_name
            if equipment_name:
                return f"{equipment_name} → {part_display}"
            return part_display

        return equipment_name or "—"

    @staticmethod
    def _format_days_until_due(days_until_due):
        if days_until_due is None:
            return "—"
        if days_until_due < 0:
            return f"Просрочено на {abs(days_until_due)} дн."
        if days_until_due == 0:
            return "Сегодня"
        return f"{days_until_due} дн."

    @staticmethod
    def _set_periodic_button_style(button: QPushButton, days_until_due):
        if days_until_due is None or days_until_due <= 7:
            style = (
                "QPushButton { background-color: #c62828; color: white; }"
                "QPushButton:hover { background-color: #b71c1c; }"
            )
        else:
            style = (
                "QPushButton { background-color: #2e7d32; color: white; }"
                "QPushButton:hover { background-color: #1b5e20; }"
            )
        button.setStyleSheet(style)

    def create_periodic_task(self):
        dialog = PeriodicTaskDialog(self.db, self.event_bus, parent=self)
        dialog.exec()

    def edit_periodic_task(self, task_id=None):
        if task_id is None:
            task_id = self._get_first_selected_periodic_task_id()
        if not task_id:
            QMessageBox.information(self, "Редактирование работы", "Выберите работу для редактирования.")
            return
        dialog = PeriodicTaskDialog(self.db, self.event_bus, task_id=task_id, parent=self)
        dialog.exec()

    def delete_periodic_tasks(self):
        task_ids, titles = self._get_selected_periodic_tasks()
        if not task_ids:
            QMessageBox.information(self, "Удаление работ", "Выберите периодические работы для удаления.")
            return

        if len(task_ids) == 1:
            prompt = f"Удалить работу '{titles[0]}'?"
        else:
            previews = '\n'.join(f"• {title}" for title in titles[:5])
            if len(titles) > 5:
                previews += "\n…"
            prompt = f"Удалить выбранные работы ({len(task_ids)} шт.)?\n\n{previews}"

        reply = QMessageBox.question(
            self,
            "Удаление работ",
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        success, message = self.db.delete_periodic_tasks(task_ids)
        if success:
            QMessageBox.information(self, "Удаление работ", message)
            self.event_bus.emit("periodic_tasks.changed")
        else:
            QMessageBox.warning(self, "Удаление работ", message)

    def complete_periodic_task(self, task_id):
        if not task_id:
            return
        success, message, _ = self.db.complete_periodic_task(task_id)
        if success:
            QMessageBox.information(self, "Периодическая работа", message)
            self.event_bus.emit("periodic_tasks.changed")
        else:
            QMessageBox.warning(self, "Периодическая работа", message)

    def _get_selected_periodic_tasks(self) -> tuple[list[int], list[str]]:
        selected_rows = {index.row() for index in self.periodic_table.selectedIndexes()}
        task_ids: list[int] = []
        titles: list[str] = []
        for row in sorted(selected_rows):
            item = self.periodic_table.item(row, 0)
            if not item:
                continue
            task_id = item.data(Qt.UserRole)
            if not task_id:
                continue
            task_ids.append(task_id)
            titles.append(item.text())
        return task_ids, titles

    def _get_first_selected_periodic_task_id(self):
        task_ids, _ = self._get_selected_periodic_tasks()
        return task_ids[0] if task_ids else None

    def _on_periodic_table_double_clicked(self, index):
        if not index.isValid():
            return
        item = self.periodic_table.item(index.row(), 0)
        task_id = item.data(Qt.UserRole) if item else None
        if task_id:
            self.edit_periodic_task(task_id)

    def _on_periodic_due_double_clicked(self, index):
        if not index.isValid():
            return
        item = self.periodic_due_table.item(index.row(), 0)
        task_id = item.data(Qt.UserRole) if item else None
        if task_id:
            self.edit_periodic_task(task_id)

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

    def _init_regular_tasks_ui(self, layout: QVBoxLayout):
        controls_layout = QHBoxLayout()
        self.create_task_button = QPushButton("Создать задачу")
        self.manage_colleagues_button = QPushButton("Коллеги...")
        self.hide_completed_checkbox = QCheckBox("Скрыть завершённые")
        self.refresh_button = QPushButton("Обновить")
        self.delete_tasks_button = QPushButton("Удалить выбранные")

        controls_layout.addWidget(self.create_task_button)
        controls_layout.addWidget(self.manage_colleagues_button)
        controls_layout.addWidget(self.delete_tasks_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.hide_completed_checkbox)
        controls_layout.addWidget(self.refresh_button)
        layout.addLayout(controls_layout)

        self.periodic_due_container = QWidget()
        due_layout = QVBoxLayout(self.periodic_due_container)
        due_layout.setContentsMargins(0, 0, 0, 0)
        due_layout.setSpacing(6)
        self.periodic_due_label = QLabel("Периодические задачи (до выполнения ≤ 7 дней)")
        self.periodic_due_label.setStyleSheet("font-weight: 600;")
        due_layout.addWidget(self.periodic_due_label)

        self.periodic_due_table = QTableWidget()
        self.periodic_due_table.setColumnCount(7)
        self.periodic_due_table.setHorizontalHeaderLabels([
            "Работа",
            "Предмет",
            "Период (дн.)",
            "Последняя дата",
            "Следующая дата",
            "Осталось",
            "Действие",
        ])
        self.periodic_due_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.periodic_due_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.periodic_due_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.periodic_due_table.setAlternatingRowColors(True)
        self.periodic_due_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.periodic_due_table.horizontalHeader().setStretchLastSection(False)
        self.periodic_due_table.verticalHeader().setVisible(False)
        due_layout.addWidget(self.periodic_due_table)
        self.periodic_due_container.setVisible(False)
        layout.addWidget(self.periodic_due_container)

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

        self.create_task_button.clicked.connect(self.create_task)
        self.manage_colleagues_button.clicked.connect(self.manage_colleagues)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.hide_completed_checkbox.toggled.connect(self.filter_tasks)
        self.delete_tasks_button.clicked.connect(self.delete_selected_tasks)
        self.table.doubleClicked.connect(self.edit_task)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.periodic_due_table.doubleClicked.connect(self._on_periodic_due_double_clicked)

    def _init_periodic_tasks_ui(self, layout: QVBoxLayout):
        controls_layout = QHBoxLayout()
        self.create_periodic_button = QPushButton("Создать работу")
        self.edit_periodic_button = QPushButton("Редактировать")
        self.delete_periodic_button = QPushButton("Удалить")
        self.refresh_periodic_button = QPushButton("Обновить")

        controls_layout.addWidget(self.create_periodic_button)
        controls_layout.addWidget(self.edit_periodic_button)
        controls_layout.addWidget(self.delete_periodic_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.refresh_periodic_button)
        layout.addLayout(controls_layout)

        self.periodic_table = QTableWidget()
        self.periodic_table.setColumnCount(7)
        self.periodic_table.setHorizontalHeaderLabels([
            "Работа",
            "Предмет",
            "Период (дн.)",
            "Последняя дата",
            "Следующая дата",
            "Осталось",
            "Действие",
        ])
        self.periodic_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.periodic_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.periodic_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.periodic_table.setAlternatingRowColors(True)
        self.periodic_table.setSortingEnabled(True)
        self.periodic_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.periodic_table.horizontalHeader().setStretchLastSection(False)
        self.periodic_table.verticalHeader().setVisible(False)

        layout.addWidget(self.periodic_table)

        self.create_periodic_button.clicked.connect(self.create_periodic_task)
        self.edit_periodic_button.clicked.connect(self.edit_periodic_task)
        self.delete_periodic_button.clicked.connect(self.delete_periodic_tasks)
        self.refresh_periodic_button.clicked.connect(self.refresh_data)
        self.periodic_table.doubleClicked.connect(self._on_periodic_table_double_clicked)
