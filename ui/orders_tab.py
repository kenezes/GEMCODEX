import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QTableView, QAbstractItemView,
                             QHeaderView, QMessageBox, QCheckBox, QHBoxLayout, QMenu, QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QAction

from .order_dialog import OrderDialog
from ui.utils import db_string_to_ui_string

class OrdersTableModel(QAbstractTableModel):
    """Модель данных для таблицы заказов."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Контрагент", "Счёт №", "Дата счёта", "Дата поставки", "Дата создания", "Статус", "Комментарий"]
        self._data = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row_data = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return row_data['counterparty_name']
            if col == 1: return f"{row_data.get('invoice_no', '')}"
            if col == 2: return db_string_to_ui_string(row_data.get('invoice_date'))
            if col == 3: return db_string_to_ui_string(row_data.get('delivery_date'))
            if col == 4: return db_string_to_ui_string(row_data.get('created_at', '').split(' ')[0]) # Только дата
            if col == 5: return row_data['status']
            if col == 6: return row_data.get('comment', '')
            
        if role == Qt.UserRole:
            return row_data['id']
            
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

class OrdersFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hide_completed = False

    def set_hide_completed(self, hide):
        self._hide_completed = hide
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._hide_completed:
            return True
        
        index = self.sourceModel().index(source_row, 5, source_parent) # 5 - колонка статуса
        status = self.sourceModel().data(index)
        return status not in ('принят', 'отменён')

class OrdersTab(QWidget):
    """Вкладка для управления заказами."""
    def __init__(self, db, event_bus, main_window):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.main_window = main_window
        
        self.init_ui()
        self.event_bus.subscribe("orders.changed", self.refresh_data)
        self.event_bus.subscribe("counterparties.changed", self.refresh_data) # На случай переименования
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._setup_toolbar()
        self._setup_table()
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.table_view)

    def _setup_toolbar(self):
        self.toolbar = QToolBar()
        
        self.new_order_button = QPushButton("Новый заказ")
        self.edit_order_button = QPushButton("Редактировать")
        self.delete_order_button = QPushButton("Удалить") # Новая кнопка
        self.accept_delivery_button = QPushButton("Принять поставку")
        self.refresh_button = QPushButton("Обновить")
        
        self.hide_completed_checkbox = QCheckBox("Скрыть завершенные")
        
        self.toolbar.addWidget(self.new_order_button)
        self.toolbar.addWidget(self.edit_order_button)
        self.toolbar.addWidget(self.delete_order_button) # Добавляем кнопку
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.accept_delivery_button)
        self.toolbar.addSeparator()
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        spacer.setFixedWidth(20)
        self.toolbar.addWidget(spacer)
        
        self.toolbar.addWidget(self.hide_completed_checkbox)
        
        widget = QWidget() # Spacer
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(widget)
        
        self.toolbar.addWidget(self.refresh_button)

        self.new_order_button.clicked.connect(self.create_new_order)
        self.edit_order_button.clicked.connect(self.edit_selected_order)
        self.delete_order_button.clicked.connect(self.delete_selected_order) # Подключаем сигнал
        self.accept_delivery_button.clicked.connect(self.accept_delivery_for_selected)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.hide_completed_checkbox.stateChanged.connect(self.toggle_hide_completed)

    def _setup_table(self):
        self.base_model = OrdersTableModel()
        self.proxy_model = OrdersFilterProxyModel()
        self.proxy_model.setSourceModel(self.base_model)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(True)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._create_context_menu)
        self.table_view.doubleClicked.connect(self.edit_selected_order)
        
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

    def refresh_data(self):
        logging.info("Обновление данных на вкладке 'Заказы'")
        orders_data = self.db.get_all_orders_with_counterparty()
        self.base_model.load_data(orders_data)

    def toggle_hide_completed(self, state):
        self.proxy_model.set_hide_completed(state == Qt.Checked)

    def create_new_order(self):
        dialog = OrderDialog(self.db, self.event_bus, parent=self.main_window)
        dialog.exec()

    def get_selected_order_id(self):
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if selected_indexes:
            proxy_index = selected_indexes[0]
            source_index = self.proxy_model.mapToSource(proxy_index)
            return self.base_model.data(source_index, Qt.UserRole)
        return None

    def edit_selected_order(self):
        order_id = self.get_selected_order_id()
        if order_id:
            dialog = OrderDialog(self.db, self.event_bus, order_id=order_id, parent=self.main_window)
            dialog.exec()
        else:
            QMessageBox.information(self, "Информация", "Выберите заказ для редактирования.")
            
    def delete_selected_order(self):
        order_id = self.get_selected_order_id()
        if not order_id:
            QMessageBox.warning(self, "Внимание", "Выберите заказ для удаления.")
            return

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


    def accept_delivery_for_selected(self):
        order_id = self.get_selected_order_id()
        if order_id:
            reply = QMessageBox.question(self, "Подтверждение",
                                       "Принять поставку по этому заказу? Остатки на складе будут увеличены.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                success, message = self.db.accept_delivery(order_id)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.event_bus.emit("orders.changed")
                    self.event_bus.emit("parts.changed")
                else:
                    QMessageBox.warning(self, "Внимание", message)
        else:
            QMessageBox.information(self, "Информация", "Выберите заказ для приемки.")

    def _create_context_menu(self, position):
        menu = QMenu()
        edit_action = QAction("Редактировать", self)
        delete_action = QAction("Удалить", self) # Новый пункт
        accept_action = QAction("Принять поставку", self)
        
        edit_action.triggered.connect(self.edit_selected_order)
        delete_action.triggered.connect(self.delete_selected_order) # Подключаем
        accept_action.triggered.connect(self.accept_delivery_for_selected)
        
        menu.addAction(edit_action)
        menu.addAction(delete_action) # Добавляем
        menu.addSeparator()
        menu.addAction(accept_action)
        
        menu.exec(self.table_view.viewport().mapToGlobal(position))

