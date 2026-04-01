from __future__ import annotations

import json
from pathlib import Path

from models import ProjectState
from validators import validate_simple_json_structure


def format_simple_json(payload: dict[str, dict[str, int]]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def save_state_to_file(state: ProjectState, file_path: str) -> None:
    path = Path(file_path)
    path.write_text(format_simple_json(state.to_simple_json()), encoding="utf-8")


def load_state_from_file(file_path: str) -> ProjectState:
    path = Path(file_path)
    raw_text = path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)
    normalized_payload = validate_simple_json_structure(payload)
    return ProjectState.from_simple_json(
        normalized_payload,
        current_file_path=str(path),
    )
