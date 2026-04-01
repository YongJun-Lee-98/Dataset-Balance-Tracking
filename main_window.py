from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCloseEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from clipboard_service import copy_text_to_clipboard
from dialogs import JsonPreviewDialog, MultilineTextDialog, TextInputDialog, confirm_action
from models import Category, ProjectState
from storage import format_simple_json, load_state_from_file, save_state_to_file
from validators import ERROR_MESSAGES, ValidationError, prepare_bulk_names, validate_category_name, validate_subcategory_name


class MainWindow(QMainWindow):
    WINDOW_TITLE = "Data Balance Tracking Sheet"

    def __init__(self) -> None:
        super().__init__()
        self.state = ProjectState()
        self._build_ui()
        self._connect_signals()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.setMinimumSize(1000, 700)

        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal, root)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, stretch=1)

        toolbar = self._build_bottom_toolbar()
        root_layout.addWidget(toolbar)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar(self))
        self._apply_styles()

    def _build_left_panel(self) -> QWidget:
        frame = QFrame(self)
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Categories", frame)
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self.category_list = QListWidget(frame)
        self.category_list.setAlternatingRowColors(True)
        layout.addWidget(self.category_list, stretch=1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.add_category_button = QPushButton("Add Category", frame)
        self.rename_category_button = QPushButton("Rename", frame)
        self.delete_category_button = QPushButton("Delete", frame)
        button_row.addWidget(self.add_category_button)
        button_row.addWidget(self.rename_category_button)
        button_row.addWidget(self.delete_category_button)
        layout.addLayout(button_row)
        return frame

    def _build_right_panel(self) -> QWidget:
        frame = QFrame(self)
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.current_category_title = QLabel("Select a category", frame)
        self.current_category_title.setObjectName("panelTitle")
        layout.addWidget(self.current_category_title)

        self.empty_state_label = QLabel("No subcategories yet. Add one to start tracking.", frame)
        self.empty_state_label.setObjectName("hintLabel")
        layout.addWidget(self.empty_state_label)

        self.subcategory_table = QTableWidget(0, 7, frame)
        self.subcategory_table.setHorizontalHeaderLabels(
            ["Subcategory", "Count", "-1", "+1", "Rename", "Delete", "Status"]
        )
        self.subcategory_table.verticalHeader().setVisible(False)
        self.subcategory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.subcategory_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.subcategory_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.subcategory_table.setAlternatingRowColors(False)
        self.subcategory_table.setShowGrid(False)
        self.subcategory_table.setWordWrap(False)
        self.subcategory_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.subcategory_table.horizontalHeader().setStretchLastSection(False)
        self.subcategory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.subcategory_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(2, 6):
            self.subcategory_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.subcategory_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.subcategory_table, stretch=1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.add_subcategory_button = QPushButton("Add Subcategory", frame)
        self.bulk_add_subcategory_button = QPushButton("Bulk Add", frame)
        button_row.addWidget(self.add_subcategory_button)
        button_row.addWidget(self.bulk_add_subcategory_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        return frame

    def _build_bottom_toolbar(self) -> QWidget:
        frame = QWidget(self)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.save_button = QPushButton("Save", frame)
        self.save_as_button = QPushButton("Save As", frame)
        self.load_button = QPushButton("Load", frame)
        self.preview_button = QPushButton("JSON Preview", frame)
        self.finish_button = QPushButton("Finish", frame)

        spacer = QWidget(frame)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout.addWidget(self.save_button)
        layout.addWidget(self.save_as_button)
        layout.addWidget(self.load_button)
        layout.addWidget(self.preview_button)
        layout.addWidget(spacer)
        layout.addWidget(self.finish_button)
        return frame

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f5f6fa;
            }
            QFrame#panel {
                background: #ffffff;
                border: 1px solid #d9dde7;
                border-radius: 12px;
            }
            QLabel#panelTitle {
                font-size: 22px;
                font-weight: 700;
                color: #24324a;
            }
            QLabel#hintLabel {
                color: #6a778b;
                font-size: 13px;
            }
            QListWidget {
                border: 1px solid #d9dde7;
                border-radius: 10px;
                padding: 6px;
                background: #fbfcff;
            }
            QListWidget::item {
                color: #21314b;
                background: transparent;
                padding: 8px 10px;
                border-radius: 8px;
            }
            QListWidget::item:alternate {
                background: #f5f8fd;
            }
            QListWidget::item:selected:active,
            QListWidget::item:selected:!active {
                background: #d7e8ff;
                color: #173b72;
            }
            QTableWidget {
                border: 1px solid #d9dde7;
                border-radius: 10px;
                background: #ffffff;
                color: #21314b;
                gridline-color: transparent;
            }
            QTableWidget::item {
                color: #21314b;
                background: #ffffff;
            }
            QTableWidget::item:selected:active,
            QTableWidget::item:selected:!active {
                background: #d7e8ff;
                color: #173b72;
            }
            QHeaderView::section {
                background: #eef2f7;
                color: #31425b;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #d9dde7;
                font-weight: 600;
            }
            QPushButton {
                background: #eef3fb;
                color: #21314b;
                border: 1px solid #c9d4e3;
                border-radius: 8px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: #e1ebf9;
            }
            QPushButton:disabled {
                color: #97a1b2;
                background: #f1f3f6;
            }
            """
        )

    def _connect_signals(self) -> None:
        self.category_list.itemSelectionChanged.connect(self.on_category_selection_changed)
        self.category_list.itemDoubleClicked.connect(lambda _: self.rename_selected_category())

        self.add_category_button.clicked.connect(self.add_category)
        self.rename_category_button.clicked.connect(self.rename_selected_category)
        self.delete_category_button.clicked.connect(self.delete_selected_category)

        self.add_subcategory_button.clicked.connect(self.add_subcategory)
        self.bulk_add_subcategory_button.clicked.connect(self.bulk_add_subcategories)

        self.save_button.clicked.connect(self.save_file)
        self.save_as_button.clicked.connect(self.save_file_as)
        self.load_button.clicked.connect(self.load_file)
        self.preview_button.clicked.connect(self.show_json_preview)
        self.finish_button.clicked.connect(self.finish_and_copy)

    def refresh_all(self) -> None:
        self.state.ensure_valid_selection()
        self.refresh_category_list()
        self.refresh_subcategory_table()
        self.update_action_states()
        self.update_window_title()

    def refresh_category_list(self) -> None:
        selected_id = self.state.selected_category_id

        self.category_list.blockSignals(True)
        self.category_list.clear()
        selected_row = -1
        for row, category in enumerate(self.state.categories):
            item = QListWidgetItem(category.name)
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            item.setForeground(QColor("#21314b"))
            self.category_list.addItem(item)
            if category.id == selected_id:
                selected_row = row
        self.category_list.blockSignals(False)

        if selected_row >= 0:
            self.category_list.setCurrentRow(selected_row)
        elif self.state.categories:
            self.category_list.setCurrentRow(0)
        else:
            self.state.selected_category_id = None

    def refresh_subcategory_table(self) -> None:
        category = self.state.get_selected_category()
        scroll_value = self.subcategory_table.verticalScrollBar().value()
        self.subcategory_table.setRowCount(0)

        if category is None:
            self.current_category_title.setText("Select a category")
            self.empty_state_label.setText("Create a category first, then add subcategories.")
            self.empty_state_label.setVisible(True)
            self.subcategory_table.setDisabled(True)
            return

        self.current_category_title.setText(category.name)
        self.subcategory_table.setDisabled(False)

        if not category.items:
            self.empty_state_label.setText("No subcategories yet. Add one to start tracking.")
            self.empty_state_label.setVisible(True)
            return

        self.empty_state_label.setVisible(False)
        lowest_ids = category.lowest_item_ids()
        self.subcategory_table.setRowCount(len(category.items))

        for row, item in enumerate(category.items):
            self.subcategory_table.setRowHeight(row, 48)
            is_lowest = item.id in lowest_ids

            name_item = QTableWidgetItem(item.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            count_item = QTableWidgetItem(str(item.count))
            count_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            count_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            badge_item = QTableWidgetItem("LOWEST" if is_lowest else "")
            badge_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            badge_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

            self._apply_lowest_style(name_item, count_item, badge_item, is_lowest)
            self.subcategory_table.setItem(row, 0, name_item)
            self.subcategory_table.setItem(row, 1, count_item)
            self.subcategory_table.setCellWidget(
                row,
                2,
                self._build_row_button(
                    "−",
                    lambda _checked=False, category_id=category.id, item_id=item.id: self.decrement_subcategory(
                        category_id, item_id
                    ),
                    enabled=item.count > 0,
                ),
            )
            self.subcategory_table.setCellWidget(
                row,
                3,
                self._build_row_button(
                    "+",
                    lambda _checked=False, category_id=category.id, item_id=item.id: self.increment_subcategory(
                        category_id, item_id
                    ),
                ),
            )
            self.subcategory_table.setCellWidget(
                row,
                4,
                self._build_row_button(
                    "Rename",
                    lambda _checked=False, category_id=category.id, item_id=item.id: self.rename_subcategory(
                        category_id, item_id
                    ),
                ),
            )
            self.subcategory_table.setCellWidget(
                row,
                5,
                self._build_row_button(
                    "Delete",
                    lambda _checked=False, category_id=category.id, item_id=item.id: self.delete_subcategory(
                        category_id, item_id
                    ),
                ),
            )
            self.subcategory_table.setItem(row, 6, badge_item)

        self.subcategory_table.verticalScrollBar().setValue(scroll_value)

    def _apply_lowest_style(
        self,
        name_item: QTableWidgetItem,
        count_item: QTableWidgetItem,
        badge_item: QTableWidgetItem,
        is_lowest: bool,
    ) -> None:
        count_font = QFont()
        count_font.setBold(True)
        count_item.setFont(count_font)
        default_text_color = QColor("#21314b")
        name_item.setForeground(default_text_color)
        count_item.setForeground(default_text_color)
        badge_item.setForeground(default_text_color)

        if not is_lowest:
            return

        row_background = QColor("#fff4ce")
        name_item.setBackground(row_background)
        count_item.setBackground(row_background)
        badge_item.setBackground(QColor("#ffe29a"))

        strong_color = QColor("#7b5200")
        name_font = QFont()
        name_font.setBold(True)
        name_item.setFont(name_font)
        name_item.setForeground(strong_color)
        count_item.setForeground(strong_color)
        badge_item.setForeground(strong_color)

    def _build_row_button(
        self,
        text: str,
        callback,
        enabled: bool = True,
    ) -> QWidget:
        container = QWidget(self.subcategory_table)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        button = QPushButton(text, container)
        button.setEnabled(enabled)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return container

    def update_action_states(self) -> None:
        has_category = self.state.get_selected_category() is not None
        self.rename_category_button.setEnabled(has_category)
        self.delete_category_button.setEnabled(has_category)
        self.add_subcategory_button.setEnabled(has_category)
        self.bulk_add_subcategory_button.setEnabled(has_category)
        self.preview_button.setEnabled(True)
        self.finish_button.setEnabled(True)

    def update_window_title(self) -> None:
        file_label = Path(self.state.current_file_path).name if self.state.current_file_path else "Untitled"
        dirty_marker = "*" if self.state.dirty else ""
        self.setWindowTitle(f"{dirty_marker}{self.WINDOW_TITLE} - {file_label}")

    def on_category_selection_changed(self) -> None:
        current_item = self.category_list.currentItem()
        self.state.selected_category_id = (
            current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        )
        self.refresh_subcategory_table()
        self.update_action_states()

    def add_category(self) -> None:
        value, accepted = TextInputDialog.get_value(self, "Add Category", "Category name:")
        if not accepted:
            return

        try:
            name = validate_category_name(value, self.state.categories)
            category = self.state.add_category(name)
        except ValidationError as exc:
            self.show_warning(exc.message)
            return
        except ValueError:
            self.show_warning(ERROR_MESSAGES["duplicate_category"])
            return

        self.refresh_all()
        self.statusBar().showMessage(f"Added category: {category.name}", 3000)

    def rename_selected_category(self) -> None:
        category = self.state.get_selected_category()
        if category is None:
            return

        value, accepted = TextInputDialog.get_value(
            self,
            "Rename Category",
            "Category name:",
            category.name,
        )
        if not accepted:
            return

        try:
            name = validate_category_name(value, self.state.categories, exclude_category_id=category.id)
            self.state.rename_category(category.id, name)
        except ValidationError as exc:
            self.show_warning(exc.message)
            return
        except ValueError:
            self.show_warning(ERROR_MESSAGES["duplicate_category"])
            return

        self.refresh_all()
        self.statusBar().showMessage(f"Renamed category to: {name}", 3000)

    def delete_selected_category(self) -> None:
        category = self.state.get_selected_category()
        if category is None:
            return

        confirmed = confirm_action(
            self,
            "Delete Category",
            f"'{category.name}' 상위 목록을 삭제하시겠습니까?",
            "해당 하위 목록과 count도 함께 삭제됩니다.",
        )
        if not confirmed:
            return

        self.state.remove_category(category.id)
        self.refresh_all()
        self.statusBar().showMessage(f"Deleted category: {category.name}", 3000)

    def add_subcategory(self) -> None:
        category = self.state.get_selected_category()
        if category is None:
            return

        value, accepted = TextInputDialog.get_value(self, "Add Subcategory", "Subcategory name:")
        if not accepted:
            return

        try:
            name = validate_subcategory_name(value, category)
            item = self.state.add_subcategory(category.id, name)
        except ValidationError as exc:
            self.show_warning(exc.message)
            return
        except ValueError:
            self.show_warning(ERROR_MESSAGES["duplicate_subcategory"])
            return

        self.refresh_subcategory_table()
        self.update_window_title()
        self.statusBar().showMessage(f"Added subcategory: {item.name}", 3000)

    def bulk_add_subcategories(self) -> None:
        category = self.state.get_selected_category()
        if category is None:
            return

        value, accepted = MultilineTextDialog.get_value(
            self,
            "Bulk Add Subcategories",
            "Enter one subcategory per line:",
        )
        if not accepted:
            return

        prepared_names = prepare_bulk_names(value)
        if not prepared_names:
            self.show_warning(ERROR_MESSAGES["invalid_name"])
            return

        existing_names = {item.name for item in category.items}
        added_names: list[str] = []
        skipped_names: list[str] = []

        for name in prepared_names:
            if name in existing_names:
                skipped_names.append(name)
                continue
            self.state.add_subcategory(category.id, name)
            existing_names.add(name)
            added_names.append(name)

        if not added_names:
            detail = "\n".join(skipped_names) if skipped_names else None
            self.show_warning(ERROR_MESSAGES["duplicate_subcategory"], detail)
            return

        self.refresh_subcategory_table()
        self.update_window_title()
        self.statusBar().showMessage(f"Added {len(added_names)} subcategories.", 3000)

        if skipped_names:
            QMessageBox.information(
                self,
                "Skipped Duplicates",
                "일부 항목은 중복되어 제외되었습니다.",
                QMessageBox.StandardButton.Ok,
            )

    def rename_subcategory(self, category_id: str, item_id: str) -> None:
        category = self.state.get_category(category_id)
        if category is None:
            return
        item = category.get_item(item_id)
        if item is None:
            return

        value, accepted = TextInputDialog.get_value(
            self,
            "Rename Subcategory",
            "Subcategory name:",
            item.name,
        )
        if not accepted:
            return

        try:
            name = validate_subcategory_name(value, category, exclude_item_id=item.id)
            self.state.rename_subcategory(category.id, item.id, name)
        except ValidationError as exc:
            self.show_warning(exc.message)
            return
        except ValueError:
            self.show_warning(ERROR_MESSAGES["duplicate_subcategory"])
            return

        self.refresh_subcategory_table()
        self.update_window_title()
        self.statusBar().showMessage(f"Renamed subcategory to: {name}", 3000)

    def delete_subcategory(self, category_id: str, item_id: str) -> None:
        category = self.state.get_category(category_id)
        if category is None:
            return
        item = category.get_item(item_id)
        if item is None:
            return

        confirmed = confirm_action(
            self,
            "Delete Subcategory",
            f"'{item.name}' 하위 목록을 삭제하시겠습니까?",
        )
        if not confirmed:
            return

        self.state.remove_subcategory(category.id, item.id)
        self.refresh_subcategory_table()
        self.update_window_title()
        self.statusBar().showMessage(f"Deleted subcategory: {item.name}", 3000)

    def increment_subcategory(self, category_id: str, item_id: str) -> None:
        self.state.increment_subcategory(category_id, item_id)
        self.refresh_subcategory_table()
        self.update_window_title()

    def decrement_subcategory(self, category_id: str, item_id: str) -> None:
        self.state.decrement_subcategory(category_id, item_id)
        self.refresh_subcategory_table()
        self.update_window_title()

    def save_file(self) -> bool:
        if not self.state.current_file_path:
            return self.save_file_as()

        try:
            save_state_to_file(self.state, self.state.current_file_path)
        except OSError as exc:
            self.show_warning(ERROR_MESSAGES["save_failed"], str(exc))
            return False

        self.state.mark_clean(self.state.current_file_path)
        self.update_window_title()
        self.statusBar().showMessage("Saved successfully.", 3000)
        return True

    def save_file_as(self) -> bool:
        suggested_path = self.state.current_file_path or "data-balance.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As",
            suggested_path,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return False
        if not file_path.lower().endswith(".json"):
            file_path = f"{file_path}.json"

        try:
            save_state_to_file(self.state, file_path)
        except OSError as exc:
            self.show_warning(ERROR_MESSAGES["save_failed"], str(exc))
            return False

        self.state.mark_clean(file_path)
        self.update_window_title()
        self.statusBar().showMessage("Saved successfully.", 3000)
        return True

    def load_file(self) -> None:
        if not self.can_discard_unsaved_changes():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load JSON File",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            self.state = load_state_from_file(file_path)
        except json.JSONDecodeError as exc:
            self.show_warning(ERROR_MESSAGES["invalid_json"], str(exc))
            return
        except ValidationError as exc:
            self.show_warning(exc.message)
            return
        except OSError as exc:
            self.show_warning(ERROR_MESSAGES["load_failed"], str(exc))
            return

        self.refresh_all()
        self.statusBar().showMessage("Loaded successfully.", 3000)

    def show_json_preview(self) -> None:
        dialog = JsonPreviewDialog(self, "JSON Preview", format_simple_json(self.state.to_simple_json()))
        dialog.exec()

    def finish_and_copy(self) -> None:
        try:
            copy_text_to_clipboard(format_simple_json(self.state.to_simple_json()))
        except Exception as exc:  # noqa: BLE001
            self.show_warning(ERROR_MESSAGES["clipboard_failed"], str(exc))
            return

        self.statusBar().showMessage("Copied JSON to clipboard.", 3000)
        QMessageBox.information(
            self,
            "Finish",
            "현재 구조가 JSON으로 클립보드에 복사되었습니다.",
            QMessageBox.StandardButton.Ok,
        )

    def can_discard_unsaved_changes(self) -> bool:
        if not self.state.dirty:
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved Changes")
        box.setText("저장되지 않은 변경사항이 있습니다.")
        box.setInformativeText("계속하기 전에 저장하시겠습니까?")

        save_button = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is save_button:
            return self.save_file()
        if clicked is discard_button:
            return True
        if clicked is cancel_button:
            return False
        return False

    def show_warning(self, message: str, detail: str | None = None) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Warning")
        box.setText(message)
        if detail:
            box.setInformativeText(detail)
        box.exec()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.can_discard_unsaved_changes():
            event.accept()
            return
        event.ignore()
