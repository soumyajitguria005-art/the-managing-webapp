from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.modules.integration.validate_source import load_source, observed_counts, observed_ids

SOURCE = ROOT / "tests" / "fixtures" / "cit_public.json"

def test_official_source_validates_and_counts_are_observed():
    dataset, checksum = load_source(SOURCE)
    assert dataset.dataset_id == "cit-public-v1"
    assert len(checksum) == 64
    counts = observed_counts(dataset)
    assert counts["rooms"] == 27
    assert counts["faculty"] == 40
    assert counts["student_groups"] == 14
    assert counts["courses"] == 62
    assert counts["sessions"] == 189
    assert counts["booking_requests"] == 25
    assert counts["cancellations"] == 1
    assert counts["exams"] == 41

def test_source_ids_are_unique_and_preserved():
    dataset, _ = load_source(SOURCE)
    ids = observed_ids(dataset)
    for values in ids.values():
        assert len(values) == len(set(values))
