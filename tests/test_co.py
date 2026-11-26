import pytest

from change_orders import ChangeOrderError, apply_change_order, build_change_order, co_number, milestone_for, shift_plan

BOQ = [{"id": "a", "code": "CP-001", "name": "Wardrobe", "room": "Bedroom", "unit": "sqft", "qty": 40, "rate": 1500, "status": "ok"},
       {"id": "b", "code": "EL-001", "name": "Profile light", "room": "Living", "unit": "rft", "qty": 20, "rate": 800, "status": "ok"}]


def test_build_and_apply():
    co = build_change_order(BOQ, [
        {"action": "add", "name": "Study table", "room": "Bedroom", "category": "carpentry", "unit": "nos", "qty": 1, "rate": 25000},
        {"action": "qty", "line_id": "a", "qty": 50},
        {"action": "remove", "line_id": "b"}], number=co_number(0), title="Bedroom changes", days=5)
    assert co["no"] == "CO-01" and co["delta"] == 25000 + 15000 - 16000
    new = apply_change_order(BOQ, co)
    assert len(new) == 3 and new[0]["qty"] == 50 and new[1]["status"] == "removed" and new[2]["co_no"] == "CO-01"
    assert milestone_for(co)["kind"] == "extra"


def test_ordered_lines_are_guarded():
    with pytest.raises(ChangeOrderError):
        build_change_order(BOQ, [{"action": "remove", "line_id": "b"}], number="CO-02", title="Drop light", ordered=["b"])
    co = build_change_order(BOQ, [{"action": "remove", "line_id": "b"}], number="CO-02", title="Drop light")
    with pytest.raises(ChangeOrderError):
        apply_change_order(BOQ, co, ordered=["b"])
    assert milestone_for(co)["kind"] == "credit"


def test_shift_plan():
    st = [{"key": "site", "status": "active", "planned_start": "2026-12-01", "due": "2026-12-20"},
          {"key": "handover", "status": "pending", "planned_start": "2026-12-21", "due": "2026-12-25"},
          {"key": "brief", "status": "done", "planned_start": "2026-10-01", "due": "2026-10-05"}]
    out = shift_plan(st, 5)
    assert out[0]["due"] == "2026-12-25" and out[0]["planned_start"] == "2026-12-01"
    assert out[1]["planned_start"] == "2026-12-26" and out[2]["due"] == "2026-10-05"
