import logging
from functools import partial
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QTableWidget, 
                             QHeaderView, QAbstractItemView, QTableWidgetItem,
                             QPushButton, QMessageBox, QMenu)
from PySide6.QtGui import QColor, QBrush, QAction
from PySide6.QtCore import Qt

from ui.order_dialog import OrderDialog
from ui.utils import db_string_to_ui_string

class DashboardTab(QWidget):
    def __init__(self, db, event_bus, main_window):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.main_window = main_window
        self.init_ui()
        self.connect_events()
        self.refresh_all_tables()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Блок "Запчасти к заказу"
        parts_group = QGroupBox("Запчасти к заказу (Остаток < Минимума)")
        parts_layout = QVBoxLayout()
        self.parts_table = self._create_parts_table()
        self.order_parts_button = QPushButton("Заказать выбранные")
        self.order_parts_button.clicked.connect(self.order_selected_parts)
        parts_layout.addWidget(self.parts_table)
        parts_layout.addWidget(self.order_parts_button, alignment=Qt.AlignRight)
        parts_group.setLayout(parts_layout)

        # Блок "Активные задачи"
        tasks_group = QGroupBox("Активные задачи")
        tasks_layout = QVBoxLayout()
        self.tasks_table = self._create_tasks_table()
        self.tasks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tasks_table.customContextMenuRequested.connect(self.show_tasks_context_menu)
        tasks_layout.addWidget(self.tasks_table)
        tasks_group.setLayout(tasks_layout)
        
        # Блок "Заказы в пути"
        orders_group = QGroupBox("Заказы в пути")
        orders_layout = QVBoxLayout()
        self.orders_table = self._create_orders_table()
        self.orders_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.orders_table.customContextMenuRequested.connect(self.show_orders_context_menu)
        orders_layout.addWidget(self.orders_table)
        orders_group.setLayout(orders_layout)

        main_layout.addWidget(parts_group, 1)
        main_layout.addWidget(tasks_group, 1)
        main_layout.addWidget(orders_group, 1)

    def _create_parts_table(self):
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Наименование", "Артикул", "Ост.", "Мин.", "Цена", "К заказу"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        return table

    def _create_tasks_table(self):
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["Задача", "Оборудование", "Исполнитель", "Срок", "Статус", "Приоритет", "Комментарий"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        return table

    def _create_orders_table(self):
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Контрагент", "Счёт №", "Дата счёта", "Дата поставки", "Статус", "Комментарий"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        return table

    def connect_events(self):
        self.event_bus.subscribe("parts.changed", self.refresh_parts_table)
        self.event_bus.subscribe("orders.changed", self.refresh_orders_table)
        self.event_bus.subscribe("tasks.changed", self.refresh_tasks_table)

    def refresh_all_tables(self):
        self.refresh_parts_table()
        self.refresh_tasks_table()
        self.refresh_orders_table()

    def refresh_parts_table(self):
        self.parts_table.setRowCount(0)
        parts = self.db.get_parts_to_order()
        for row, part in enumerate(parts):
            self.parts_table.insertRow(row)
            
            name_item = QTableWidgetItem(part['name'])
            name_item.setData(Qt.UserRole, part['id'])
            self.parts_table.setItem(row, 0, name_item)
            
            self.parts_table.setItem(row, 1, QTableWidgetItem(part['sku']))
            self.parts_table.setItem(row, 2, QTableWidgetItem(str(part['qty'])))
            self.parts_table.setItem(row, 3, QTableWidgetItem(str(part['min_qty'])))
            self.parts_table.setItem(row, 4, QTableWidgetItem(f"{part['price']:.2f}"))
            
            to_order_qty = part['min_qty'] - part['qty']
            to_order_item = QTableWidgetItem(str(to_order_qty))
            if to_order_qty <= 0:
                to_order_item.setBackground(QColor("#ffcccb"))
            self.parts_table.setItem(row, 5, to_order_item)

    def refresh_tasks_table(self):
        self.tasks_table.setRowCount(0)
        tasks = self.db.get_active_tasks()
        priority_colors = {"высокий": QColor("#FFCCCC"), "средний": QColor("#FFE5CC"), "низкий": QColor("#FFFFCC")}
        for row, task in enumerate(tasks):
            self.tasks_table.insertRow(row)
            
            title_item = QTableWidgetItem(task['title'])
            title_item.setData(Qt.UserRole, task['id'])
            self.tasks_table.setItem(row, 0, title_item)
            
            self.tasks_table.setItem(row, 1, QTableWidgetItem(task.get('equipment_name', '')))
            self.tasks_table.setItem(row, 2, QTableWidgetItem(task.get('assignee_name', '')))
            self.tasks_table.setItem(row, 3, QTableWidgetItem(db_string_to_ui_string(task.get('due_date'))))
            self.tasks_table.setItem(row, 4, QTableWidgetItem(task['status']))
            self.tasks_table.setItem(row, 5, QTableWidgetItem(task['priority']))
            self.tasks_table.setItem(row, 6, QTableWidgetItem(task.get('description', '')))
            
            color = priority_colors.get(task['priority'])
            if color:
                for col in range(self.tasks_table.columnCount()):
                    self.tasks_table.item(row, col).setBackground(QBrush(color))

    def refresh_orders_table(self):
        self.orders_table.setRowCount(0)
        orders = self.db.get_active_orders()
        for row, order in enumerate(orders):
            self.orders_table.insertRow(row)

            cp_item = QTableWidgetItem(order['counterparty_name'])
            cp_item.setData(Qt.UserRole, order['id'])
            self.orders_table.setItem(row, 0, cp_item)

            self.orders_table.setItem(row, 1, QTableWidgetItem(order.get('invoice_no', '')))
            self.orders_table.setItem(row, 2, QTableWidgetItem(db_string_to_ui_string(order.get('invoice_date'))))
            self.orders_table.setItem(row, 3, QTableWidgetItem(db_string_to_ui_string(order.get('delivery_date'))))
            self.orders_table.setItem(row, 4, QTableWidgetItem(order['status']))
            self.orders_table.setItem(row, 5, QTableWidgetItem(order.get('comment', '')))

    def order_selected_parts(self):
        selected_rows = sorted(list(set(item.row() for item in self.parts_table.selectedItems())))
        if not selected_rows:
            QMessageBox.warning(self, "Внимание", "Выберите запчасти для создания заказа.")
            return
            
        initial_items = []
        for row in selected_rows:
            part_id = self.parts_table.item(row, 0).data(Qt.UserRole)
            part = self.db.get_part_by_id(part_id)
            to_order_qty = part['min_qty'] - part['qty']
            if to_order_qty <= 0:
                reply = QMessageBox.warning(self, "Внимание", f"Запчасть '{part['name']}' не требует заказа.\nВсе равно добавить в заказ?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No: continue
            
            initial_items.append({'part_id': part['id'], 'name': part['name'], 'sku': part['sku'], 'qty': to_order_qty if to_order_qty > 0 else 1, 'price': part['price']})

        if not initial_items: return
        order_dialog = OrderDialog(self.db, self.event_bus, parent=self.main_window, initial_items=initial_items)
        order_dialog.exec()

    def show_tasks_context_menu(self, position):
        row = self.tasks_table.rowAt(position.y())
        if row < 0: return

        task_id = self.tasks_table.item(row, 0).data(Qt.UserRole)
        menu = QMenu()
        status_menu = menu.addMenu("Изменить статус")
        
        statuses = ['в работе', 'выполнена', 'отменена', 'на стопе']
        for status in statuses:
            action = status_menu.addAction(status)
            action.triggered.connect(partial(self.change_task_status, task_id, status))
            
        menu.exec(self.tasks_table.viewport().mapToGlobal(position))

    def change_task_status(self, task_id, new_status):
        success, message = self.db.update_task_status(task_id, new_status)
        if success:
            self.event_bus.emit("tasks.changed")
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def show_orders_context_menu(self, position):
        row = self.orders_table.rowAt(position.y())
        if row < 0: return

        order_id = self.orders_table.item(row, 0).data(Qt.UserRole)
        menu = QMenu(self)
        status_menu = menu.addMenu("Изменить статус")
        
        statuses = ['создан', 'в пути', 'принят', 'отменён']
        for status in statuses:
            action = status_menu.addAction(status)
            action.triggered.connect(partial(self.change_order_status, order_id, status))

        menu.addSeparator()
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(partial(self.delete_order_from_dashboard, order_id))
        menu.addAction(delete_action)
            
        menu.exec(self.orders_table.viewport().mapToGlobal(position))

    def change_order_status(self, order_id, new_status):
        # Особый случай для приемки
        if new_status == 'принят':
            reply = QMessageBox.question(self, "Подтверждение", 
                                       "Приемка поставки пополнит остатки на складе. Продолжить?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No: return
            success, message = self.db.accept_delivery(order_id)
        else:
            success, message = self.db.update_order_status(order_id, new_status)
        
        if success:
            self.event_bus.emit("orders.changed")
            if new_status == 'принят':
                self.event_bus.emit("parts.changed")
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def delete_order_from_dashboard(self, order_id):
        reply = QMessageBox.question(self, "Подтверждение удаления",
                                     "Вы уверены, что хотите удалить этот заказ? Это действие необратимо.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, message = self.db.delete_order(order_id)
            if success:
                QMessageBox.information(self, "Успех", "Заказ успешно удален.")
                self.event_bus.emit("orders.changed")
            else:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить заказ: {message}")

