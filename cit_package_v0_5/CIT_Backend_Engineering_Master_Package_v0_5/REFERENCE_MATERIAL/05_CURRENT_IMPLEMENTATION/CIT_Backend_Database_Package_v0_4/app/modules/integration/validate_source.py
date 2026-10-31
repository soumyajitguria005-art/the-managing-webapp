from __future__ import annotations
import hashlib, json
from pathlib import Path
from .source_schemas import SourceDataset

EXPECTED_ROOT_KEYS = {
    "dataset_id", "institute", "calendar", "priority_order", "role_category_cap",
    "rooms", "room_unavailability", "faculty", "student_groups", "courses",
    "sessions", "booking_requests", "cancellations", "exams",
}

def load_source(path: str | Path) -> tuple[SourceDataset, str]:
    raw_bytes = Path(path).read_bytes()
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    payload = json.loads(raw_bytes)
    if set(payload) != EXPECTED_ROOT_KEYS:
        missing = sorted(EXPECTED_ROOT_KEYS - set(payload))
        extra = sorted(set(payload) - EXPECTED_ROOT_KEYS)
        raise ValueError(f"source root keys mismatch; missing={missing}, extra={extra}")
    dataset = SourceDataset.model_validate_json(raw_bytes)
    return dataset, checksum

def observed_counts(dataset: SourceDataset) -> dict[str, int]:
    return {name: len(getattr(dataset, name)) for name in (
        "rooms", "room_unavailability", "faculty", "student_groups", "courses",
        "sessions", "booking_requests", "cancellations", "exams"
    )}

def observed_ids(dataset: SourceDataset) -> dict[str, list[str]]:
    return {name: [item.id for item in getattr(dataset, name)] for name in (
        "rooms", "faculty", "student_groups", "courses", "sessions", "booking_requests", "exams"
    )}
