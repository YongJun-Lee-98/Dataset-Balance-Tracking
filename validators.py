from __future__ import annotations

from collections.abc import Iterable

from models import Category


ERROR_MESSAGES = {
    "duplicate_category": "이미 존재하는 상위 목록 이름입니다.",
    "duplicate_subcategory": "같은 상위 목록 안에 이미 존재하는 하위 목록 이름입니다.",
    "invalid_name": "이름은 비어 있을 수 없습니다.",
    "invalid_json": "불러온 파일 형식이 올바르지 않습니다.",
    "save_failed": "파일 저장 중 오류가 발생했습니다.",
    "load_failed": "파일 불러오기 중 오류가 발생했습니다.",
    "clipboard_failed": "클립보드 복사 중 오류가 발생했습니다.",
}


class ValidationError(Exception):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, code)
        super().__init__(self.message)


def normalize_name(value: str) -> str:
    return value.strip()


def validate_non_empty_name(value: str) -> str:
    normalized = normalize_name(value)
    if not normalized:
        raise ValidationError("invalid_name")
    return normalized


def validate_category_name(
    value: str,
    categories: Iterable[Category],
    exclude_category_id: str | None = None,
) -> str:
    normalized = validate_non_empty_name(value)
    for category in categories:
        if category.id != exclude_category_id and category.name == normalized:
            raise ValidationError("duplicate_category")
    return normalized


def validate_subcategory_name(
    value: str,
    category: Category,
    exclude_item_id: str | None = None,
) -> str:
    normalized = validate_non_empty_name(value)
    if category.item_name_exists(normalized, exclude_item_id=exclude_item_id):
        raise ValidationError("duplicate_subcategory")
    return normalized


def prepare_bulk_names(multiline_text: str) -> list[str]:
    seen: set[str] = set()
    prepared: list[str] = []
    for raw_line in multiline_text.splitlines():
        name = normalize_name(raw_line)
        if not name or name in seen:
            continue
        seen.add(name)
        prepared.append(name)
    return prepared


def validate_simple_json_structure(payload: object) -> dict[str, dict[str, int]]:
    if not isinstance(payload, dict):
        raise ValidationError("invalid_json")

    normalized_payload: dict[str, dict[str, int]] = {}
    seen_categories: set[str] = set()

    for raw_category_name, raw_items in payload.items():
        if not isinstance(raw_category_name, str):
            raise ValidationError("invalid_json")
        category_name = validate_non_empty_name(raw_category_name)
        if category_name in seen_categories:
            raise ValidationError("invalid_json")
        if not isinstance(raw_items, dict):
            raise ValidationError("invalid_json")

        normalized_items: dict[str, int] = {}
        seen_items: set[str] = set()
        for raw_item_name, raw_count in raw_items.items():
            if not isinstance(raw_item_name, str):
                raise ValidationError("invalid_json")
            item_name = validate_non_empty_name(raw_item_name)
            if item_name in seen_items:
                raise ValidationError("invalid_json")
            if not isinstance(raw_count, int) or isinstance(raw_count, bool) or raw_count < 0:
                raise ValidationError("invalid_json")
            seen_items.add(item_name)
            normalized_items[item_name] = raw_count

        seen_categories.add(category_name)
        normalized_payload[category_name] = normalized_items

    return normalized_payload
