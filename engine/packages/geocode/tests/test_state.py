from now_geocode.state import StateRecord, StateStore, now_iso


def _record(place_key="k1", final=True, status="resolved", lat=-6.2, lng=106.8):
    return StateRecord(
        place_key=place_key,
        final=final,
        rung="address_geocode",
        status=status,
        lat=lat,
        lng=lng,
        google_place_id=None,
        confidence=0.8,
        location_type="ROOFTOP",
        note=None,
        attempted_at=now_iso(),
    )


def test_missing_file_starts_empty(tmp_path):
    store = StateStore(tmp_path / "state.jsonl")
    assert store.get("anything") is None
    assert len(store) == 0


def test_final_record_is_returned_on_get():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "state.jsonl"
        store = StateStore(path)
        store.record(_record(final=True))
        assert store.get("k1") is not None


def test_non_final_record_is_not_returned_so_it_retries(tmp_path):
    store = StateStore(tmp_path / "state.jsonl")
    store.record(_record(final=False, status="unresolved", lat=None, lng=None))
    assert store.get("k1") is None  # caller should re-attempt


def test_reload_from_disk_folds_to_latest_record(tmp_path):
    path = tmp_path / "state.jsonl"
    store1 = StateStore(path)
    store1.record(_record(place_key="k1", final=False, status="unresolved", lat=None, lng=None))
    store1.record(_record(place_key="k1", final=True, status="resolved"))

    store2 = StateStore(path)  # simulates a fresh process resuming a batch
    record = store2.get("k1")
    assert record is not None
    assert record.status == "resolved"


def test_append_only_preserves_history_on_disk(tmp_path):
    path = tmp_path / "state.jsonl"
    store = StateStore(path)
    store.record(_record(place_key="k1", final=False, status="unresolved", lat=None, lng=None))
    store.record(_record(place_key="k1", final=True, status="resolved"))
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # both attempts on disk, not overwritten
