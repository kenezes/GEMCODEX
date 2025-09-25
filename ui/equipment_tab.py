import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QMessageBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                             QTableWidget, QTableWidgetItem, QHeaderView, QToolButton,
                             QLabel, QPlainTextEdit, QStyle, QCheckBox)
from PySide6.QtCore import Qt, QSize

from .equipment_category_manager_dialog import EquipmentCategoryManagerDialog
from .equipment_dialog import EquipmentDialog
from .attach_part_dialog import AttachPartDialog
from .replacement_dialog import ReplacementDialog
from .task_dialog import TaskDialog
from .utils import open_part_folder as open_part_folder_fs, open_equipment_folder as open_equipment_folder_fs

class EquipmentTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.current_equipment_id = None
        self._comment_updating = False
        self._comment_dirty = False
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
        tree_buttons_layout.setSpacing(4)

        icon_size = QSize(24, 24)

        def _create_tool_button(icon: QStyle.StandardPixmap, tooltip: str) -> QToolButton:
            button = QToolButton()
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(tooltip)
            button.setAutoRaise(True)
            button.setIconSize(icon_size)
            return button

        self.manage_categories_button = _create_tool_button(QStyle.SP_FileDialogDetailedView, "Управление категориями")
        self.add_equipment_button = _create_tool_button(QStyle.SP_FileDialogNewFolder, "Добавить оборудование")
        self.edit_equipment_button = _create_tool_button(QStyle.SP_FileDialogContentsView, "Редактировать выбранный элемент")
        self.delete_equipment_button = _create_tool_button(QStyle.SP_TrashIcon, "Удалить выбранный элемент")
        self.open_equipment_folder_button = _create_tool_button(QStyle.SP_DirOpenIcon, "Открыть папку оборудования")

        tree_buttons_layout.addWidget(self.manage_categories_button)
        tree_buttons_layout.addWidget(self.add_equipment_button)
        tree_buttons_layout.addWidget(self.edit_equipment_button)
        tree_buttons_layout.addWidget(self.delete_equipment_button)
        tree_buttons_layout.addWidget(self.open_equipment_folder_button)
        tree_buttons_layout.addStretch()

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        left_layout.addLayout(tree_buttons_layout)

        self.only_requires_equipment_checkbox = QCheckBox("Только оборудование с требующей замену запчастью")
        self.only_requires_equipment_checkbox.setToolTip(
            "Отображать только те аппараты, у которых есть помеченные как требующие замены запчасти."
        )
        left_layout.addWidget(self.only_requires_equipment_checkbox)
        left_layout.addWidget(self.tree)

        comment_controls_layout = QHBoxLayout()
        self.comment_label = QLabel("Комментарий:")
        self.save_comment_button = _create_tool_button(QStyle.SP_DialogSaveButton, "Сохранить комментарий")
        self.save_comment_button.setEnabled(False)
        comment_controls_layout.addWidget(self.comment_label)
        comment_controls_layout.addStretch()
        comment_controls_layout.addWidget(self.save_comment_button)

        self.comment_edit = QPlainTextEdit()
        self.comment_edit.setPlaceholderText("Введите комментарий к выбранному оборудованию")
        self.comment_edit.setMaximumHeight(100)
        self.comment_edit.setEnabled(False)

        left_layout.addLayout(comment_controls_layout)
        left_layout.addWidget(self.comment_edit)

        # Правая панель (таблица запчастей)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        parts_buttons_layout = QHBoxLayout()
        self.add_part_button = QPushButton("Добавить запчасть")
        parts_buttons_layout.addWidget(self.add_part_button)
        parts_buttons_layout.addStretch()
        
        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(5)
        self.parts_table.setHorizontalHeaderLabels([
            "Наименование",
            "Артикул",
            "Установлено, шт.",
            "Последняя замена",
            "Действия",
        ])
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        header = self.parts_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

        self.only_requires_parts_checkbox = QCheckBox("Только требующие замену")
        self.only_requires_parts_checkbox.setToolTip(
            "Скрыть элементы, которые не помечены как требующие замены."
        )
        parts_buttons_layout.addWidget(self.only_requires_parts_checkbox)
        right_layout.addLayout(parts_buttons_layout)
        right_layout.addWidget(self.parts_table)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        left_panel.setMinimumWidth(180)
        splitter.setSizes([240, 760])
        main_layout.addWidget(splitter)

        # Подключения
        self.manage_categories_button.clicked.connect(self.manage_categories)
        self.add_equipment_button.clicked.connect(self.add_equipment)
        self.edit_equipment_button.clicked.connect(self.edit_equipment)
        self.delete_equipment_button.clicked.connect(self.delete_equipment)
        self.tree.currentItemChanged.connect(self.on_tree_selection_changed)
        self.add_part_button.clicked.connect(self.attach_part)
        self.open_equipment_folder_button.clicked.connect(self.open_selected_equipment_folder)
        self.comment_edit.textChanged.connect(self.on_comment_text_changed)
        self.save_comment_button.clicked.connect(self.save_equipment_comment)
        self.only_requires_equipment_checkbox.toggled.connect(self.on_equipment_filter_toggled)
        self.only_requires_parts_checkbox.toggled.connect(self.on_parts_filter_toggled)

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

    def on_equipment_filter_toggled(self, checked):
        self.load_tree_data()

    def on_parts_filter_toggled(self, checked):
        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)
        else:
            self.parts_table.setRowCount(0)

    def load_tree_data(self, *args, **kwargs):
        selected_equipment_id = self.current_equipment_id
        self.tree.clear()
        self.update_comment_panel(None)

        categories = self.db.get_equipment_categories()
        equipment_list = self.db.get_all_equipment()
        filter_active = self.only_requires_equipment_checkbox.isChecked()
        equipment_with_flags = self.db.get_equipment_ids_with_replacement_flag()

        equipment_by_parent = {}
        for eq in equipment_list:
            parent_id = eq['parent_id']
            equipment_by_parent.setdefault(parent_id, []).append(eq)

        for cat in categories:
            cat_item = QTreeWidgetItem(self.tree, [cat['name']])
            cat_item.setData(0, Qt.UserRole, {'type': 'category', 'id': cat['id']})

            top_level_equipment = [
                eq for eq in equipment_list if eq['category_id'] == cat['id'] and eq['parent_id'] is None
            ]

            has_children = False
            for eq in top_level_equipment:
                if self._add_equipment_node(cat_item, eq, equipment_by_parent, equipment_with_flags, filter_active):
                    has_children = True

            if not has_children:
                index = self.tree.indexOfTopLevelItem(cat_item)
                self.tree.takeTopLevelItem(index)

        self.tree.expandAll()

        if selected_equipment_id:
            item = self._find_tree_item_by_equipment_id(selected_equipment_id)
            if item:
                self.tree.setCurrentItem(item)
                self.current_equipment_id = selected_equipment_id
                self.update_comment_panel(item)
                self.load_parts_for_equipment(selected_equipment_id)
            else:
                self.current_equipment_id = None
                self.parts_table.setRowCount(0)
        else:
            self.current_equipment_id = None
            self.parts_table.setRowCount(0)

        self.update_buttons_state()

    def _add_equipment_node(
        self,
        parent_item,
        equipment_data,
        equipment_by_parent,
        equipment_with_flags,
        filter_active,
    ):
        if filter_active and not self._equipment_matches_filter(
            equipment_data['id'], equipment_by_parent, equipment_with_flags
        ):
            return False

        display_text = f"{equipment_data['name']} ({equipment_data['sku'] or 'б/а'})"
        eq_item = QTreeWidgetItem(parent_item, [display_text])
        eq_item.setData(0, Qt.UserRole, {
            'type': 'equipment',
            'id': equipment_data['id'],
            'name': equipment_data['name'],
            'sku': equipment_data.get('sku'),
            'comment': equipment_data.get('comment')
        })

        children = equipment_by_parent.get(equipment_data['id'], [])
        for child in children:
            self._add_equipment_node(eq_item, child, equipment_by_parent, equipment_with_flags, filter_active)

        return True

    def _equipment_matches_filter(self, equipment_id, equipment_by_parent, equipment_with_flags):
        if equipment_id in equipment_with_flags:
            return True

        for child in equipment_by_parent.get(equipment_id, []):
            if self._equipment_matches_filter(child['id'], equipment_by_parent, equipment_with_flags):
                return True

        return False

    def _find_tree_item_by_equipment_id(self, equipment_id):
        if equipment_id is None:
            return None

        def _iter_items(parent):
            count = parent.childCount()
            for index in range(count):
                yield parent.child(index)

        stack = []
        for index in range(self.tree.topLevelItemCount()):
            stack.append(self.tree.topLevelItem(index))

        while stack:
            item = stack.pop()
            item_data = item.data(0, Qt.UserRole) or {}
            if item_data.get('type') == 'equipment' and item_data.get('id') == equipment_id:
                return item
            stack.extend(_iter_items(item))

        return None

    def on_tree_selection_changed(self, current, previous):
        self.update_buttons_state()
        self.update_comment_panel(current)
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

    def update_comment_panel(self, current_item):
        self._comment_updating = True
        try:
            if not current_item:
                self.comment_edit.clear()
                self.comment_edit.setEnabled(False)
                self.comment_label.setText("Комментарий (выберите оборудование):")
                self.save_comment_button.setEnabled(False)
                self._comment_dirty = False
                return

            item_data = current_item.data(0, Qt.UserRole) or {}
            if item_data.get('type') == 'equipment':
                comment_text = item_data.get('comment') or ""
                self.comment_edit.setPlainText(comment_text)
                self.comment_edit.setEnabled(True)
                self.comment_label.setText("Комментарий:")
                self._comment_dirty = False
                self.save_comment_button.setEnabled(False)
            else:
                self.comment_edit.clear()
                self.comment_edit.setEnabled(False)
                self.comment_label.setText("Комментарий (выберите оборудование):")
                self.save_comment_button.setEnabled(False)
                self._comment_dirty = False
        finally:
            self._comment_updating = False

    def on_comment_text_changed(self):
        if self._comment_updating or not self.comment_edit.isEnabled():
            return
        self._comment_dirty = True
        self.save_comment_button.setEnabled(True)

    def save_equipment_comment(self):
        if not self.current_equipment_id or not self._comment_dirty:
            return

        comment_text = self.comment_edit.toPlainText().strip()
        success, message = self.db.update_equipment_comment(self.current_equipment_id, comment_text)
        if success:
            selected_item = self.tree.currentItem()
            if selected_item:
                item_data = selected_item.data(0, Qt.UserRole) or {}
                item_data['comment'] = comment_text
                selected_item.setData(0, Qt.UserRole, item_data)
            self._comment_dirty = False
            self.save_comment_button.setEnabled(False)
            QMessageBox.information(self, "Комментарий сохранен", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def load_parts_for_equipment(self, equipment_id):
        if equipment_id is None:
            self.parts_table.setRowCount(0)
            return

        parts = self.db.get_parts_for_equipment(equipment_id)
        self.parts_table.setRowCount(0)
        self.parts_table.clearSpans()

        filter_active = self.only_requires_parts_checkbox.isChecked()
        parts_to_display = []
        for part in parts:
            part['equipment_id'] = equipment_id
            if filter_active and not part.get('requires_replacement'):
                continue
            parts_to_display.append(part)

        current_category = None
        row_index = 0
        part_row_number = 1
        for part in parts_to_display:
            
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
                header_row_item = QTableWidgetItem("")
                header_row_item.setFlags(Qt.ItemIsEnabled)
                self.parts_table.setVerticalHeaderItem(row_index, header_row_item)
                current_category = category_name
                row_index += 1

            self.parts_table.insertRow(row_index)
            self.parts_table.setItem(row_index, 0, QTableWidgetItem(part['part_name']))
            self.parts_table.setItem(row_index, 1, QTableWidgetItem(part['part_sku'] or ""))
            self.parts_table.setItem(row_index, 2, QTableWidgetItem(str(part['installed_qty'])))

            last_replacement_str = part.get('last_replacement_date', '')
            self.parts_table.setItem(row_index, 3, QTableWidgetItem(last_replacement_str))

            requires_button = QPushButton()
            self._update_requires_replacement_button(requires_button, part)
            requires_button.clicked.connect(
                lambda _, p=part, b=requires_button: self.on_requires_replacement_button_clicked(p, b)
            )

            row_number_item = QTableWidgetItem(str(part_row_number))
            row_number_item.setTextAlignment(Qt.AlignCenter)
            row_number_item.setFlags(Qt.ItemIsEnabled)
            self.parts_table.setVerticalHeaderItem(row_index, row_number_item)
            part_row_number += 1

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
            actions_layout.addWidget(requires_button)

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

    def on_requires_replacement_button_clicked(self, part_data, button):
        new_state = not bool(part_data.get('requires_replacement'))
        self._set_part_requires_replacement(part_data, button, new_state)

    def _set_part_requires_replacement(self, part_data, button, requires):
        success, equipment_id, message = self.db.set_equipment_part_requires_replacement(
            part_data['equipment_part_id'], requires
        )
        if not success:
            QMessageBox.critical(self, "Ошибка", message)
            self._update_requires_replacement_button(button, part_data)
            return

        part_data['requires_replacement'] = requires
        self._update_requires_replacement_button(button, part_data)

        if equipment_id:
            self.event_bus.emit("equipment_parts_changed", equipment_id)
        self.event_bus.emit("parts.changed")

        if requires:
            self._prompt_create_replacement_task(part_data)

    def _update_requires_replacement_button(self, button, part_data):
        requires = bool(part_data.get('requires_replacement'))
        if requires:
            button.setText("Требует замены")
            button.setStyleSheet(
                "QPushButton { background-color: #dc3545; color: white; }"
                "QPushButton:hover { background-color: #c82333; }"
            )
            button.setToolTip("Запчасть помечена как требующая замены")
        else:
            button.setText("Не требует замены")
            button.setStyleSheet(
                "QPushButton { background-color: #28a745; color: white; }"
                "QPushButton:hover { background-color: #218838; }"
            )
            button.setToolTip("Запчасть не помечена как требующая замены")

    def _prompt_create_replacement_task(self, part_data):
        part_name = part_data.get('part_name') or ""
        part_sku = part_data.get('part_sku') or "б/а"
        equipment_id = part_data.get('equipment_id')
        equipment = (
            self.db.fetchone("SELECT name, sku FROM equipment WHERE id = ?", (equipment_id,))
            if equipment_id
            else None
        )

        equipment_name = equipment['name'] if equipment else ""
        equipment_sku = equipment['sku'] if equipment else None
        equipment_sku = equipment_sku or "б/а"

        part_label = f"{part_name} ({part_sku})"
        equipment_label = f"{equipment_name} ({equipment_sku})"

        default_title = f"Замена {part_label} на {equipment_label}"

        reply = QMessageBox.question(
            self,
            "Создать задачу",
            f"Создать задачу «{default_title}»?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply != QMessageBox.Yes:
            return

        dialog = TaskDialog(self.db, self.event_bus, parent=self)
        dialog.title_edit.setText(default_title)

        if equipment_id is not None:
            index = dialog.equipment_combo.findData(equipment_id)
            if index != -1:
                dialog.equipment_combo.setCurrentIndex(index)

        dialog.exec()

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
        self.load_tree_data()
        if self.current_equipment_id == equipment_id:
            logging.info(
                f"Currently selected equipment matches ({self.current_equipment_id}). Parts list refreshed."
            )

    def on_parts_changed(self):
        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)

