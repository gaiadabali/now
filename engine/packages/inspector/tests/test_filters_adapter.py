from now_inspector import filters_adapter


def test_probe_reports_not_importable_when_package_absent():
    status = filters_adapter.probe()
    # As of this ticket engine/packages/filters (E3.2) does not exist in
    # this tree yet -- this asserts the honest degrade path, not a guess.
    assert status.importable is False


def test_get_fallback_rungs_never_raises_and_degrades():
    result = filters_adapter.get_fallback_rungs(["1", "2"])
    assert set(result.keys()) == {"1", "2"}
    for rail_infos in result.values():
        assert len(rail_infos) == len(filters_adapter.RAILS)
        for info in rail_infos:
            assert info.available is False
            assert info.rung_reached is None
