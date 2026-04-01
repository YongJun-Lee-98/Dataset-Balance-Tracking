from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


SimpleJson = dict[str, dict[str, int]]


def _new_id() -> str:
    return uuid4().hex


@dataclass(slots=True)
class SubcategoryItem:
    id: str
    name: str
    count: int = 0

    def increment(self) -> None:
        self.count += 1

    def decrement(self) -> bool:
        if self.count == 0:
            return False
        self.count -= 1
        return True

    def rename(self, new_name: str) -> None:
        self.name = new_name


@dataclass(slots=True)
class Category:
    id: str
    name: str
    items: list[SubcategoryItem] = field(default_factory=list)

    def get_item(self, item_id: str) -> SubcategoryItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def item_name_exists(self, name: str, exclude_item_id: str | None = None) -> bool:
        return any(
            item.name == name and item.id != exclude_item_id
            for item in self.items
        )

    def add_item(self, name: str) -> SubcategoryItem:
        if self.item_name_exists(name):
            raise ValueError(f"Subcategory '{name}' already exists in '{self.name}'.")
        item = SubcategoryItem(id=_new_id(), name=name, count=0)
        self.items.append(item)
        return item

    def remove_item(self, item_id: str) -> SubcategoryItem:
        for index, item in enumerate(self.items):
            if item.id == item_id:
                return self.items.pop(index)
        raise KeyError(f"Unknown subcategory id: {item_id}")

    def rename(self, new_name: str) -> None:
        self.name = new_name

    def lowest_item_ids(self) -> set[str]:
        if not self.items:
            return set()
        minimum = min(item.count for item in self.items)
        return {item.id for item in self.items if item.count == minimum}

    def to_simple_mapping(self) -> dict[str, int]:
        return {item.name: item.count for item in self.items}


@dataclass(slots=True)
class ProjectState:
    categories: list[Category] = field(default_factory=list)
    selected_category_id: str | None = None
    dirty: bool = False
    current_file_path: str | None = None

    def __post_init__(self) -> None:
        self.ensure_valid_selection()

    def ensure_valid_selection(self) -> None:
        valid_ids = {category.id for category in self.categories}
        if self.selected_category_id in valid_ids:
            return
        self.selected_category_id = self.categories[0].id if self.categories else None

    def mark_dirty(self) -> None:
        self.dirty = True

    def mark_clean(self, current_file_path: str | None = None) -> None:
        if current_file_path is not None:
            self.current_file_path = current_file_path
        self.dirty = False

    def get_category(self, category_id: str | None) -> Category | None:
        if category_id is None:
            return None
        for category in self.categories:
            if category.id == category_id:
                return category
        return None

    def get_selected_category(self) -> Category | None:
        return self.get_category(self.selected_category_id)

    def category_name_exists(self, name: str, exclude_category_id: str | None = None) -> bool:
        return any(
            category.name == name and category.id != exclude_category_id
            for category in self.categories
        )

    def add_category(self, name: str) -> Category:
        if self.category_name_exists(name):
            raise ValueError(f"Category '{name}' already exists.")
        category = Category(id=_new_id(), name=name)
        self.categories.append(category)
        self.selected_category_id = category.id
        self.mark_dirty()
        return category

    def rename_category(self, category_id: str, new_name: str) -> None:
        category = self.get_category(category_id)
        if category is None:
            raise KeyError(f"Unknown category id: {category_id}")
        if self.category_name_exists(new_name, exclude_category_id=category_id):
            raise ValueError(f"Category '{new_name}' already exists.")
        category.rename(new_name)
        self.mark_dirty()

    def remove_category(self, category_id: str) -> Category:
        for index, category in enumerate(self.categories):
            if category.id != category_id:
                continue
            removed = self.categories.pop(index)
            if self.categories:
                next_index = min(index, len(self.categories) - 1)
                self.selected_category_id = self.categories[next_index].id
            else:
                self.selected_category_id = None
            self.mark_dirty()
            return removed
        raise KeyError(f"Unknown category id: {category_id}")

    def add_subcategory(self, category_id: str, name: str) -> SubcategoryItem:
        category = self.get_category(category_id)
        if category is None:
            raise KeyError(f"Unknown category id: {category_id}")
        item = category.add_item(name)
        self.mark_dirty()
        return item

    def rename_subcategory(self, category_id: str, item_id: str, new_name: str) -> None:
        category = self.get_category(category_id)
        if category is None:
            raise KeyError(f"Unknown category id: {category_id}")
        if category.item_name_exists(new_name, exclude_item_id=item_id):
            raise ValueError(f"Subcategory '{new_name}' already exists in '{category.name}'.")
        item = category.get_item(item_id)
        if item is None:
            raise KeyError(f"Unknown subcategory id: {item_id}")
        item.rename(new_name)
        self.mark_dirty()

    def remove_subcategory(self, category_id: str, item_id: str) -> SubcategoryItem:
        category = self.get_category(category_id)
        if category is None:
            raise KeyError(f"Unknown category id: {category_id}")
        removed = category.remove_item(item_id)
        self.mark_dirty()
        return removed

    def increment_subcategory(self, category_id: str, item_id: str) -> int:
        category = self.get_category(category_id)
        if category is None:
            raise KeyError(f"Unknown category id: {category_id}")
        item = category.get_item(item_id)
        if item is None:
            raise KeyError(f"Unknown subcategory id: {item_id}")
        item.increment()
        self.mark_dirty()
        return item.count

    def decrement_subcategory(self, category_id: str, item_id: str) -> int:
        category = self.get_category(category_id)
        if category is None:
            raise KeyError(f"Unknown category id: {category_id}")
        item = category.get_item(item_id)
        if item is None:
            raise KeyError(f"Unknown subcategory id: {item_id}")
        changed = item.decrement()
        if changed:
            self.mark_dirty()
        return item.count

    def to_simple_json(self) -> SimpleJson:
        return {category.name: category.to_simple_mapping() for category in self.categories}

    @classmethod
    def from_simple_json(
        cls,
        payload: dict[str, dict[str, int]],
        current_file_path: str | None = None,
    ) -> ProjectState:
        categories: list[Category] = []
        for category_name, items in payload.items():
            category = Category(id=_new_id(), name=category_name)
            for item_name, count in items.items():
                category.items.append(SubcategoryItem(id=_new_id(), name=item_name, count=count))
            categories.append(category)
        return cls(
            categories=categories,
            selected_category_id=categories[0].id if categories else None,
            dirty=False,
            current_file_path=current_file_path,
        )

    def as_debug_dict(self) -> dict[str, Any]:
        return {
            "dirty": self.dirty,
            "current_file_path": self.current_file_path,
            "selected_category_id": self.selected_category_id,
            "categories": [
                {
                    "id": category.id,
                    "name": category.name,
                    "items": [
                        {"id": item.id, "name": item.name, "count": item.count}
                        for item in category.items
                    ],
                }
                for category in self.categories
            ],
        }
