from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCloseEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHeaderView,
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
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

        self.right_tabs = QTabWidget(frame)
        self.right_tabs.addTab(self._build_current_category_tab(), "Current Category")
        self.right_tabs.addTab(self._build_all_items_tab(), "All Items")
        layout.addWidget(self.right_tabs, stretch=1)
        return frame

    def _build_current_category_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.current_category_title = QLabel("Select a category", tab)
        self.current_category_title.setObjectName("panelTitle")
        layout.addWidget(self.current_category_title)

        self.current_category_summary_label = QLabel("Select a category to see total count.", tab)
        self.current_category_summary_label.setObjectName("hintLabel")
        layout.addWidget(self.current_category_summary_label)

        self.empty_state_label = QLabel("No subcategories yet. Add one to start tracking.", tab)
        self.empty_state_label.setObjectName("hintLabel")
        layout.addWidget(self.empty_state_label)

        self.subcategory_table = QTableWidget(0, 7, tab)
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
        self.add_subcategory_button = QPushButton("Add Subcategory", tab)
        self.bulk_add_subcategory_button = QPushButton("Bulk Add", tab)
        button_row.addWidget(self.add_subcategory_button)
        button_row.addWidget(self.bulk_add_subcategory_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        return tab

    def _build_all_items_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.all_items_title = QLabel("All Categories Overview", tab)
        self.all_items_title.setObjectName("panelTitle")
        layout.addWidget(self.all_items_title)

        self.all_items_hint_label = QLabel(
            "Double-click a row to jump back to that category.",
            tab,
        )
        self.all_items_hint_label.setObjectName("hintLabel")
        layout.addWidget(self.all_items_hint_label)

        self.all_items_table = QTableWidget(0, 6, tab)
        self.all_items_table.setHorizontalHeaderLabels(
            ["Category", "Subcategory", "Count", "-1", "+1", "Status"]
        )
        self.all_items_table.verticalHeader().setVisible(False)
        self.all_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.all_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.all_items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.all_items_table.setAlternatingRowColors(False)
        self.all_items_table.setShowGrid(False)
        self.all_items_table.setWordWrap(False)
        self.all_items_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.all_items_table.horizontalHeader().setStretchLastSection(False)
        self.all_items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.all_items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.all_items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.all_items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.all_items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.all_items_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.all_items_table, stretch=1)
        return tab

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
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #eef3fb;
                color: #31425b;
                padding: 8px 14px;
                margin-right: 6px;
                border: 1px solid #c9d4e3;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #d7e8ff;
                color: #173b72;
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
        self.all_items_table.itemDoubleClicked.connect(self.on_all_items_row_activated)

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
        self.refresh_all_items_table()
        self.update_action_states()
        self.update_window_title()

    def refresh_category_list(self) -> None:
        selected_id = self.state.selected_category_id
        unbalanced_ids = self.state.unbalanced_category_ids()
        category_totals = self.state.category_total_counts()
        target_total = self.state.balance_target_total()

        self.category_list.blockSignals(True)
        self.category_list.clear()
        selected_row = -1
        for row, category in enumerate(self.state.categories):
            item = QListWidgetItem(category.name)
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            item.setForeground(QColor("#21314b"))
            total_count = category_totals.get(category.id, category.total_count())
            has_total_mismatch = category.id in unbalanced_ids
            item.setToolTip(
                self._build_category_total_message(
                    total_count=total_count,
                    has_total_mismatch=has_total_mismatch,
                    target_total=target_total,
                )
            )
            if has_total_mismatch:
                item.setForeground(QColor("#b42318"))
                item.setBackground(QColor("#fdecec"))
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
        unbalanced_ids = self.state.unbalanced_category_ids()
        category_totals = self.state.category_total_counts()
        target_total = self.state.balance_target_total()
        self.subcategory_table.setRowCount(0)

        if category is None:
            self.current_category_title.setText("Select a category")
            self._update_current_category_balance_summary()
            self.empty_state_label.setText("Create a category first, then add subcategories.")
            self.empty_state_label.setVisible(True)
            self.subcategory_table.setDisabled(True)
            return

        self.current_category_title.setText(category.name)
        self._update_current_category_balance_summary(
            total_count=category_totals.get(category.id, category.total_count()),
            has_total_mismatch=category.id in unbalanced_ids,
            target_total=target_total,
        )
        self.subcategory_table.setDisabled(False)

        if not category.items:
            self.empty_state_label.setText("No subcategories yet. Add one to start tracking.")
            self.empty_state_label.setVisible(True)
            return

        self.empty_state_label.setVisible(False)
        lowest_ids = category.lowest_item_ids()
        below_average_ids = category.below_average_item_ids()
        self.subcategory_table.setRowCount(len(category.items))

        for row, item in enumerate(category.items):
            self.subcategory_table.setRowHeight(row, 48)
            is_lowest = item.id in lowest_ids
            is_below_average = item.id in below_average_ids

            name_item = QTableWidgetItem(item.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            count_item = QTableWidgetItem(str(item.count))
            count_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            count_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            badge_item = QTableWidgetItem(self._build_status_text(is_lowest, is_below_average))
            badge_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            badge_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

            self._apply_status_style(
                name_item,
                count_item,
                badge_item,
                is_lowest=is_lowest,
                is_below_average=is_below_average,
            )
            self.subcategory_table.setItem(row, 0, name_item)
            self.subcategory_table.setItem(row, 1, count_item)
            self.subcategory_table.setCellWidget(
                row,
                2,
                self._build_table_button(
                    self.subcategory_table,
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
                self._build_table_button(
                    self.subcategory_table,
                    "+",
                    lambda _checked=False, category_id=category.id, item_id=item.id: self.increment_subcategory(
                        category_id, item_id
                    ),
                ),
            )
            self.subcategory_table.setCellWidget(
                row,
                4,
                self._build_table_button(
                    self.subcategory_table,
                    "Rename",
                    lambda _checked=False, category_id=category.id, item_id=item.id: self.rename_subcategory(
                        category_id, item_id
                    ),
                ),
            )
            self.subcategory_table.setCellWidget(
                row,
                5,
                self._build_table_button(
                    self.subcategory_table,
                    "Delete",
                    lambda _checked=False, category_id=category.id, item_id=item.id: self.delete_subcategory(
                        category_id, item_id
                    ),
                ),
            )
            self.subcategory_table.setItem(row, 6, badge_item)

        self.subcategory_table.verticalScrollBar().setValue(scroll_value)

    def refresh_all_items_table(self) -> None:
        scroll_value = self.all_items_table.verticalScrollBar().value()
        unbalanced_ids = self.state.unbalanced_category_ids()
        category_totals = self.state.category_total_counts()
        target_total = self.state.balance_target_total()
        self.all_items_table.setRowCount(0)

        if not self.state.categories:
            self.all_items_hint_label.setText("Create a category first to see the full hierarchy.")
            return

        hint_text = "Double-click a row to jump back to that category."
        if unbalanced_ids:
            mismatch_text = "Red-highlighted categories have mismatched total counts."
            if target_total is not None:
                mismatch_text = (
                    f"Red-highlighted categories differ from the expected total count ({target_total})."
                )
            hint_text = f"{mismatch_text} {hint_text}"
        self.all_items_hint_label.setText(hint_text)

        total_rows = sum(max(1, len(category.items)) for category in self.state.categories)
        self.all_items_table.setRowCount(total_rows)

        row = 0
        for category in self.state.categories:
            lowest_ids = category.lowest_item_ids()
            below_average_ids = category.below_average_item_ids()
            has_total_mismatch = category.id in unbalanced_ids
            total_count = category_totals.get(category.id, category.total_count())

            if not category.items:
                self._set_overview_row(
                    row=row,
                    category_id=category.id,
                    category_name=category.name,
                    item_id=None,
                    subcategory_name="—",
                    count_text="—",
                    status_text=self._build_status_text(
                        is_lowest=False,
                        is_below_average=False,
                        has_total_mismatch=has_total_mismatch,
                        empty_text="No subcategories",
                    ),
                    has_total_mismatch=has_total_mismatch,
                    total_count=total_count,
                    target_total=target_total,
                    muted=True,
                )
                row += 1
                continue

            for item in category.items:
                is_lowest = item.id in lowest_ids
                is_below_average = item.id in below_average_ids
                self._set_overview_row(
                    row=row,
                    category_id=category.id,
                    category_name=category.name,
                    item_id=item.id,
                    subcategory_name=item.name,
                    count_text=str(item.count),
                    status_text=self._build_status_text(
                        is_lowest=is_lowest,
                        is_below_average=is_below_average,
                        has_total_mismatch=has_total_mismatch,
                    ),
                    has_total_mismatch=has_total_mismatch,
                    total_count=total_count,
                    target_total=target_total,
                    is_lowest=is_lowest,
                    is_below_average=is_below_average,
                )
                row += 1

        self.all_items_table.verticalScrollBar().setValue(scroll_value)

    def _build_category_total_message(
        self,
        total_count: int | None,
        has_total_mismatch: bool,
        target_total: int | None,
    ) -> str:
        if total_count is None:
            return "Select a category to see total count."
        if has_total_mismatch:
            if target_total is None:
                return f"Total count: {total_count} | balance mismatch"
            return f"Total count: {total_count} | expected total: {target_total}"
        if target_total is None:
            return f"Total count: {total_count} | balanced"
        return f"Total count: {total_count} | balanced (target: {target_total})"

    def _update_current_category_balance_summary(
        self,
        total_count: int | None = None,
        has_total_mismatch: bool = False,
        target_total: int | None = None,
    ) -> None:
        self.current_category_summary_label.setText(
            self._build_category_total_message(
                total_count=total_count,
                has_total_mismatch=has_total_mismatch,
                target_total=target_total,
            )
        )

        title_color = "#b42318" if has_total_mismatch else "#24324a"
        summary_color = "#b42318" if has_total_mismatch else "#6a778b"
        summary_weight = "600" if has_total_mismatch else "400"
        self.current_category_title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {title_color};"
        )
        self.current_category_summary_label.setStyleSheet(
            f"color: {summary_color}; font-size: 13px; font-weight: {summary_weight};"
        )

    def _build_status_text(
        self,
        is_lowest: bool,
        is_below_average: bool,
        has_total_mismatch: bool = False,
        empty_text: str = "",
    ) -> str:
        status_parts: list[str] = []
        if has_total_mismatch:
            status_parts.append("TOTAL MISMATCH")
        if is_lowest:
            status_parts.append("LOWEST")
        if is_below_average:
            status_parts.append("BELOW AVG")
        if not status_parts:
            return empty_text
        return " / ".join(status_parts)

    def _set_overview_row(
        self,
        row: int,
        category_id: str,
        category_name: str,
        item_id: str | None,
        subcategory_name: str,
        count_text: str,
        status_text: str,
        has_total_mismatch: bool = False,
        total_count: int | None = None,
        target_total: int | None = None,
        is_lowest: bool = False,
        is_below_average: bool = False,
        muted: bool = False,
    ) -> None:
        category_item = QTableWidgetItem(category_name)
        subcategory_item = QTableWidgetItem(subcategory_name)
        count_item = QTableWidgetItem(count_text)
        status_item = QTableWidgetItem(status_text)

        category_item.setData(Qt.ItemDataRole.UserRole, category_id)
        subcategory_item.setData(Qt.ItemDataRole.UserRole, item_id)
        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        for item in (category_item, subcategory_item, count_item, status_item):
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(QColor("#21314b"))

        tooltip_text = self._build_category_total_message(
            total_count=total_count,
            has_total_mismatch=has_total_mismatch,
            target_total=target_total,
        )
        category_item.setToolTip(tooltip_text)
        status_item.setToolTip(tooltip_text)

        if muted:
            muted_color = QColor("#7a8799")
            subcategory_item.setForeground(muted_color)
            count_item.setForeground(muted_color)
            status_item.setForeground(muted_color)

        if is_lowest:
            row_background = QColor("#fff4ce")
            strong_color = QColor("#7b5200")
            for item in (category_item, subcategory_item, count_item):
                item.setBackground(row_background)
                item.setForeground(strong_color)
            status_item.setBackground(QColor("#ffe29a"))
            status_item.setForeground(strong_color)
        elif is_below_average:
            status_item.setBackground(QColor("#dbeafe"))
            status_item.setForeground(QColor("#1d4ed8"))

        if has_total_mismatch:
            mismatch_background = QColor("#fdecec")
            mismatch_color = QColor("#b42318")
            category_item.setBackground(mismatch_background)
            category_item.setForeground(mismatch_color)
            category_font = QFont()
            category_font.setBold(True)
            category_item.setFont(category_font)

            if not is_lowest and not is_below_average:
                status_item.setBackground(mismatch_background)
                status_item.setForeground(mismatch_color)

        self.all_items_table.setItem(row, 0, category_item)
        self.all_items_table.setItem(row, 1, subcategory_item)
        self.all_items_table.setItem(row, 2, count_item)
        if item_id is None:
            self.all_items_table.setItem(row, 3, self._create_empty_overview_action_item())
            self.all_items_table.setItem(row, 4, self._create_empty_overview_action_item())
        else:
            self.all_items_table.setCellWidget(
                row,
                3,
                self._build_table_button(
                    self.all_items_table,
                    "−",
                    lambda _checked=False, category_id=category_id, item_id=item_id: self.decrement_subcategory(
                        category_id, item_id
                    ),
                    enabled=count_text != "0",
                ),
            )
            self.all_items_table.setCellWidget(
                row,
                4,
                self._build_table_button(
                    self.all_items_table,
                    "+",
                    lambda _checked=False, category_id=category_id, item_id=item_id: self.increment_subcategory(
                        category_id, item_id
                    ),
                ),
            )
        self.all_items_table.setItem(row, 5, status_item)

    def _create_empty_overview_action_item(self) -> QTableWidgetItem:
        item = QTableWidgetItem("")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        return item

    def _apply_status_style(
        self,
        name_item: QTableWidgetItem,
        count_item: QTableWidgetItem,
        badge_item: QTableWidgetItem,
        is_lowest: bool,
        is_below_average: bool,
    ) -> None:
        count_font = QFont()
        count_font.setBold(True)
        count_item.setFont(count_font)
        default_text_color = QColor("#21314b")
        name_item.setForeground(default_text_color)
        count_item.setForeground(default_text_color)
        badge_item.setForeground(default_text_color)

        if not is_lowest and not is_below_average:
            return

        badge_font = QFont()
        badge_font.setBold(True)
        badge_item.setFont(badge_font)

        if is_lowest:
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
            return

        badge_item.setBackground(QColor("#dbeafe"))
        badge_item.setForeground(QColor("#1d4ed8"))

    def _build_table_button(
        self,
        table: QTableWidget,
        text: str,
        callback,
        enabled: bool = True,
    ) -> QWidget:
        container = QWidget(table)
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

    def on_all_items_row_activated(self, item: QTableWidgetItem) -> None:
        category_item = self.all_items_table.item(item.row(), 0)
        if category_item is None:
            return

        category_id = category_item.data(Qt.ItemDataRole.UserRole)
        if not category_id:
            return

        self.state.selected_category_id = category_id
        self.refresh_category_list()
        self.refresh_subcategory_table()
        self.update_action_states()
        self.right_tabs.setCurrentIndex(0)

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
        self.refresh_all_items_table()
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
        self.refresh_all_items_table()
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
        self.refresh_all_items_table()
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
        self.refresh_all_items_table()
        self.update_window_title()
        self.statusBar().showMessage(f"Deleted subcategory: {item.name}", 3000)

    def increment_subcategory(self, category_id: str, item_id: str) -> None:
        self.state.increment_subcategory(category_id, item_id)
        self.refresh_subcategory_table()
        self.refresh_all_items_table()
        self.update_window_title()

    def decrement_subcategory(self, category_id: str, item_id: str) -> None:
        self.state.decrement_subcategory(category_id, item_id)
        self.refresh_subcategory_table()
        self.refresh_all_items_table()
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
