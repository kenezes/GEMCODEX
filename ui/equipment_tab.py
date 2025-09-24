import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QMessageBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from .equipment_category_manager_dialog import EquipmentCategoryManagerDialog
from .equipment_dialog import EquipmentDialog
from .attach_part_dialog import AttachPartDialog
from .replacement_dialog import ReplacementDialog
from .utils import open_part_folder as open_part_folder_fs, open_equipment_folder as open_equipment_folder_fs

class EquipmentTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.current_equipment_id = None
        self.init_ui()
        self.load_tree_data()
        self.update_buttons_state()

        self.event_bus.subscribe('equipment_parts_changed', self.on_equipment_parts_changed)
        self.event_bus.subscribe('parts.changed', self.on_parts_changed)
        self.event_bus.subscribe('equipment.changed', self.load_tree_data)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Левая панель (дерево)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        tree_buttons_layout = QHBoxLayout()
        self.manage_categories_button = QPushButton("Категории...")
        self.add_equipment_button = QPushButton("+ Оборудование")
        self.edit_equipment_button = QPushButton("Редактировать")
        self.delete_equipment_button = QPushButton("Удалить")
        self.open_equipment_folder_button = QPushButton("Папка")
        tree_buttons_layout.addWidget(self.manage_categories_button)
        tree_buttons_layout.addWidget(self.add_equipment_button)
        tree_buttons_layout.addWidget(self.edit_equipment_button)
        tree_buttons_layout.addWidget(self.delete_equipment_button)
        tree_buttons_layout.addWidget(self.open_equipment_folder_button)
        tree_buttons_layout.addStretch()

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        
        left_layout.addLayout(tree_buttons_layout)
        left_layout.addWidget(self.tree)
        
        # Правая панель (таблица запчастей)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        parts_buttons_layout = QHBoxLayout()
        self.add_part_button = QPushButton("Добавить запчасть")
        parts_buttons_layout.addWidget(self.add_part_button)
        parts_buttons_layout.addStretch()
        
        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(5)
        self.parts_table.setHorizontalHeaderLabels(["Наименование", "Артикул", "Установлено, шт.", "Последняя замена", "Действия"])
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        header = self.parts_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        right_layout.addLayout(parts_buttons_layout)
        right_layout.addWidget(self.parts_table)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)

        # Подключения
        self.manage_categories_button.clicked.connect(self.manage_categories)
        self.add_equipment_button.clicked.connect(self.add_equipment)
        self.edit_equipment_button.clicked.connect(self.edit_equipment)
        self.delete_equipment_button.clicked.connect(self.delete_equipment)
        self.tree.currentItemChanged.connect(self.on_tree_selection_changed)
        self.add_part_button.clicked.connect(self.attach_part)
        self.open_equipment_folder_button.clicked.connect(self.open_selected_equipment_folder)

    def update_buttons_state(self):
        selected_item = self.tree.currentItem()
        is_item_selected = selected_item is not None
        item_data = selected_item.data(0, Qt.UserRole) if is_item_selected else {}
        
        is_category_selected = is_item_selected and item_data.get('type') == 'category'
        is_equipment_selected = is_item_selected and item_data.get('type') == 'equipment'

        self.edit_equipment_button.setEnabled(is_item_selected)
        self.delete_equipment_button.setEnabled(is_item_selected)
        self.add_part_button.setEnabled(is_equipment_selected)
        self.open_equipment_folder_button.setEnabled(is_equipment_selected)

    def load_tree_data(self, *args, **kwargs):
        self.tree.clear()
        categories = self.db.get_equipment_categories()
        equipment_list = self.db.get_all_equipment()

        equipment_by_parent = {}
        for eq in equipment_list:
            parent_id = eq['parent_id']
            if parent_id not in equipment_by_parent:
                equipment_by_parent[parent_id] = []
            equipment_by_parent[parent_id].append(eq)

        for cat in categories:
            cat_item = QTreeWidgetItem(self.tree, [cat['name']])
            cat_item.setData(0, Qt.UserRole, {'type': 'category', 'id': cat['id']})
            
            top_level_equipment = [eq for eq in equipment_list if eq['category_id'] == cat['id'] and eq['parent_id'] is None]
            
            for eq in top_level_equipment:
                self._add_equipment_node(cat_item, eq, equipment_by_parent)

        self.tree.expandAll()

    def _add_equipment_node(self, parent_item, equipment_data, equipment_by_parent):
        display_text = f"{equipment_data['name']} ({equipment_data['sku'] or 'б/а'})"
        eq_item = QTreeWidgetItem(parent_item, [display_text])
        eq_item.setData(0, Qt.UserRole, {
            'type': 'equipment',
            'id': equipment_data['id'],
            'name': equipment_data['name'],
            'sku': equipment_data.get('sku'),
        })

        children = equipment_by_parent.get(equipment_data['id'], [])
        for child in children:
            self._add_equipment_node(eq_item, child, equipment_by_parent)

    def on_tree_selection_changed(self, current, previous):
        self.update_buttons_state()
        if current:
            item_data = current.data(0, Qt.UserRole)
            if item_data and item_data.get('type') == 'equipment':
                self.current_equipment_id = item_data['id']
                self.load_parts_for_equipment(self.current_equipment_id)
            else:
                self.current_equipment_id = None
                self.parts_table.setRowCount(0)
        else:
            self.current_equipment_id = None
            self.parts_table.setRowCount(0)

    def load_parts_for_equipment(self, equipment_id):
        if equipment_id is None:
            self.parts_table.setRowCount(0)
            return

        parts = self.db.get_parts_for_equipment(equipment_id)
        self.parts_table.setRowCount(0)
        self.parts_table.clearSpans()

        current_category = None
        row_index = 0
        for part in parts:
            # Добавляем ID оборудования в словарь с данными о запчасти
            part['equipment_id'] = equipment_id

            category_name = part.get('category_name') or "Без категории"
            if category_name != current_category:
                self.parts_table.insertRow(row_index)
                header_item = QTableWidgetItem(category_name)
                header_font = header_item.font()
                header_font.setBold(True)
                header_item.setFont(header_font)
                header_item.setFlags(Qt.ItemIsEnabled)
                header_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.parts_table.setItem(row_index, 0, header_item)
                self.parts_table.setSpan(row_index, 0, 1, self.parts_table.columnCount())
                current_category = category_name
                row_index += 1

            self.parts_table.insertRow(row_index)
            self.parts_table.setItem(row_index, 0, QTableWidgetItem(part['part_name']))
            self.parts_table.setItem(row_index, 1, QTableWidgetItem(part['part_sku'] or ""))
            self.parts_table.setItem(row_index, 2, QTableWidgetItem(str(part['installed_qty'])))

            last_replacement_str = part.get('last_replacement_date', '')
            self.parts_table.setItem(row_index, 3, QTableWidgetItem(last_replacement_str))

            # Кнопки действий
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            replace_button = QPushButton("Заменить")
            detach_button = QPushButton("Удалить привязку")

            replace_button.clicked.connect(lambda _, p=part: self.replace_part(p))
            detach_button.clicked.connect(lambda _, epid=part['equipment_part_id'], pn=part['part_name']: self.detach_part(epid, pn))

            folder_button = QPushButton("Папка")
            folder_button.clicked.connect(lambda _, pn=part['part_name'], sku=part['part_sku']: self.open_part_folder_location(pn, sku))

            actions_layout.addWidget(replace_button)
            actions_layout.addWidget(detach_button)
            actions_layout.addWidget(folder_button)
            actions_layout.addStretch()

            self.parts_table.setCellWidget(row_index, 4, actions_widget)
            row_index += 1

    def manage_categories(self):
        dialog = EquipmentCategoryManagerDialog(self.db, self)
        if dialog.exec():
            self.load_tree_data()
            self.event_bus.emit('equipment.changed')

    def add_equipment(self):
        selected_item = self.tree.currentItem()
        category_id = None
        parent_id = None

        if not selected_item:
            QMessageBox.warning(self, "Внимание", "Сначала выберите категорию или оборудование-родителя.")
            return

        item_data = selected_item.data(0, Qt.UserRole)
        if item_data['type'] == 'category':
            category_id = item_data['id']
        elif item_data['type'] == 'equipment':
            parent_id = item_data['id']
            # Получаем категорию от родителя
            parent_data = self.db.fetchone("SELECT category_id FROM equipment WHERE id=?", (parent_id,))
            if parent_data:
                category_id = parent_data['category_id']
        
        if category_id is None:
            QMessageBox.critical(self, "Ошибка", "Не удалось определить категорию для нового оборудования.")
            return

        dialog = EquipmentDialog(self.db, self.event_bus, category_id=category_id, parent_id=parent_id, parent=self)
        if dialog.exec():
            self.load_tree_data()

    def edit_equipment(self):
        selected_item = self.tree.currentItem()
        if not selected_item: return

        item_data = selected_item.data(0, Qt.UserRole)
        if item_data.get('type') == 'category':
            self.manage_categories()
        elif item_data.get('type') == 'equipment':
            equipment_id = item_data['id']
            dialog = EquipmentDialog(self.db, self.event_bus, equipment_id=equipment_id, parent=self)
            if dialog.exec():
                self.load_tree_data()

    def delete_equipment(self):
        selected_item = self.tree.currentItem()
        if not selected_item: return

        item_data = selected_item.data(0, Qt.UserRole)
        item_type = item_data.get('type')
        item_id = item_data.get('id')
        item_name = selected_item.text(0)

        if item_type == 'category':
            reply = QMessageBox.question(self, "Удаление категории", 
                                       f"Вы уверены, что хотите удалить категорию '{item_name}'?\n"
                                       "Это действие необратимо.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                success, message = self.db.delete_equipment_category(item_id)
                QMessageBox.information(self, "Результат", message)
                if success: self.load_tree_data()
        
        elif item_type == 'equipment':
            reply = QMessageBox.question(self, "Удаление оборудования",
                                       f"Вы уверены, что хотите удалить оборудование '{item_name}'?\n"
                                       "Все вложенное оборудование также будет удалено. Это действие необратимо.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                success, message = self.db.delete_equipment(item_id)
                QMessageBox.information(self, "Результат", message)
                if success: self.load_tree_data()

    def attach_part(self):
        if self.current_equipment_id:
            dialog = AttachPartDialog(self.db, self.event_bus, self.current_equipment_id, self)
            dialog.exec()

    def detach_part(self, equipment_part_id, part_name):
        reply = QMessageBox.question(self, "Удаление привязки",
                                   f"Вы уверены, что хотите отвязать запчасть '{part_name}'?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.detach_part_from_equipment(equipment_part_id)
            QMessageBox.information(self, "Результат", message)
            if success:
                self.event_bus.emit("equipment_parts_changed", self.current_equipment_id)

    def replace_part(self, part_data):
        """Вызывает диалог замены запчасти."""
        dialog = ReplacementDialog(self.db, self.event_bus, part_data, self)
        dialog.exec()

    def open_part_folder_location(self, part_name, part_sku):
        open_part_folder_fs(part_name, part_sku)

    def open_selected_equipment_folder(self):
        selected_item = self.tree.currentItem()
        if not selected_item:
            return

        item_data = selected_item.data(0, Qt.UserRole) or {}
        if item_data.get('type') != 'equipment':
            QMessageBox.information(self, "Папка оборудования", "Выберите оборудование в списке.")
            return

        open_equipment_folder_fs(item_data.get('name'), item_data.get('sku'))

    def on_equipment_parts_changed(self, equipment_id):
        logging.info(f"Event 'equipment_parts_changed' received for equipment_id: {equipment_id}")
        if self.current_equipment_id == equipment_id:
             logging.info(f"Currently selected equipment matches ({self.current_equipment_id}). Refreshing parts list.")
             self.load_parts_for_equipment(self.current_equipment_id)

    def on_parts_changed(self):
         if self.current_equipment_id:
             self.load_parts_for_equipment(self.current_equipment_id)

