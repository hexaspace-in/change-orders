"""Change orders after a BOQ is signed: add items, remove items, change quantities.

Rules (from real interior projects):
* Each change order (CO-01, CO-02 ...) lists what is added, removed or changed in quantity, with the money
  difference (rates include GST) and any extra days of work.
* Nothing already ordered from a vendor can be removed or reduced: settle it with the vendor first.
  This is checked when the CO is drafted and again when it is approved.
* On approval the BOQ gets the new lines (tagged with the CO), removed lines drop out, quantities change, and
  open stages and tasks move by the agreed days (a client-approved delay, not the team's).
* An approved CO with extra cost becomes its own payment milestone; a CO that reduces cost is a credit.
"""
import uuid
from datetime import date, timedelta
from typing import Iterable, List, Optional

REASONS = {"client_request": "Client asked for it", "site_condition": "Site condition", "design_change": "Design change",
           "other": "Other"}


class ChangeOrderError(ValueError):
    """Raised with a message you can show to the team."""


def _nid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def co_number(existing: int) -> str:
    """co_number(0) -> 'CO-01'"""
    return f"CO-{existing + 1:02d}"


def build_change_order(boq: List[dict], changes: List[dict], *, number: str, title: str, days: int = 0,
                       reason_kind: str = "client_request", reason: str = "",
                       ordered: Iterable[str] = ()) -> dict:
    """boq: current signed lines ({"id", "code"?, "name", "room", "unit", "qty", "rate"}).
    changes: {"action": "add", "name", "room", "category", "unit", "qty", "rate", "cost_rate"?}
             | {"action": "remove", "line_id"} | {"action": "qty", "line_id", "qty"}.
    ordered: ids of BOQ lines already ordered from a vendor."""
    if len(title.strip()) < 3:
        raise ChangeOrderError("Give the change order a title")
    if reason_kind not in REASONS:
        raise ChangeOrderError("Unknown reason")
    if not changes:
        raise ChangeOrderError("Add at least one change")
    by_id, done = {l["id"]: l for l in boq}, set(ordered)
    rows = []
    for x in changes:
        act = x.get("action")
        if act == "add":
            qty, rate = float(x.get("qty") or 0), float(x.get("rate") or 0)
            if len(str(x.get("name", "")).strip()) < 2 or len(str(x.get("room", "")).strip()) < 2 or rate <= 0 or qty <= 0:
                raise ChangeOrderError("A new item needs a name, room, quantity and rate")
            row = {"id": _nid("cl"), "action": "add", "name": x["name"].strip(), "room": x["room"].strip(),
                   "category": x.get("category"), "unit": x.get("unit"), "qty": qty, "rate": rate,
                   "cost_rate": x.get("cost_rate"), "gst_pct": float(x.get("gst_pct") or 18), "delta": round(rate * qty, 2)}
        elif act in ("remove", "qty"):
            l = by_id.get(x.get("line_id") or "")
            if not l:
                raise ChangeOrderError("Pick a line from the current BOQ")
            label = l.get("code") or l["name"]
            if l["id"] in done:
                raise ChangeOrderError(f"{label} is already ordered from a vendor; settle it with the vendor before changing it")
            if act == "remove":
                row = {"id": _nid("cl"), "action": "remove", "line_id": l["id"], "name": l["name"], "room": l.get("room"),
                       "qty": l["qty"], "rate": l["rate"], "delta": -round(l["rate"] * l["qty"], 2)}
            else:
                new = float(x.get("qty") or 0)
                if new <= 0 or new == l["qty"]:
                    raise ChangeOrderError(f"Give a new quantity for {label}")
                row = {"id": _nid("cl"), "action": "qty", "line_id": l["id"], "name": l["name"], "room": l.get("room"),
                       "old_qty": l["qty"], "qty": new, "rate": l["rate"], "delta": round(l["rate"] * (new - l["qty"]), 2)}
        else:
            raise ChangeOrderError("Each change is add, remove or qty")
        rows.append(row)
    delta = round(sum(r["delta"] for r in rows), 2)
    return {"id": _nid("co"), "no": number, "title": title.strip(), "reason_kind": reason_kind,
            "reason_label": REASONS[reason_kind], "reason": reason, "days": int(days), "lines": rows, "delta": delta,
            "status": "draft"}


def apply_change_order(boq: List[dict], co: dict, ordered: Iterable[str] = ()) -> List[dict]:
    """Return the new BOQ after an approved CO. Re-checks that nothing was ordered meanwhile."""
    done = set(ordered)
    for l in co["lines"]:
        if l["action"] != "add" and l["line_id"] in done:
            raise ChangeOrderError(f"{l['name']} was ordered after this change order was drafted; draft a new one")
    out = [dict(l) for l in boq]
    idx = {l["id"]: l for l in out}
    for l in co["lines"]:
        if l["action"] == "add":
            out.append({"id": _nid("bl"), "room": l["room"], "category": l.get("category"), "name": l["name"],
                        "unit": l.get("unit"), "qty": l["qty"], "rate": l["rate"], "gst_pct": l.get("gst_pct", 18),
                        "cost_rate": l.get("cost_rate"), "status": "ok", "co_no": co["no"]})
        elif l["action"] == "remove":
            idx[l["line_id"]].update(status="removed", removed_by_co=co["no"])
        else:
            idx[l["line_id"]].update(qty=l["qty"], qty_changed_by_co=co["no"])
    return out


def shift_plan(stages: List[dict], days: int) -> List[dict]:
    """Move open stages by the client-approved days. Stage: {"key", "status": pending|active|done, "planned_start", "due"}."""
    if not days:
        return stages
    d = timedelta(days=days)
    out = []
    for s in stages:
        s = dict(s)
        if s["status"] == "pending":
            s["planned_start"] = (date.fromisoformat(s["planned_start"]) + d).isoformat()
        if s["status"] in ("pending", "active"):
            s["due"] = (date.fromisoformat(s["due"]) + d).isoformat()
        out.append(s)
    return out


def milestone_for(co: dict, stage_key: Optional[str] = None) -> Optional[dict]:
    """A payment milestone (extra cost) or credit (saving) for an approved CO, or None if the difference is under 1."""
    if abs(co["delta"]) < 1:
        return None
    extra = co["delta"] > 0
    return {"key": f"co_{co['no'].lower()}", "label": f"Change order {co['no']}" if extra else f"Credit from {co['no']}",
            "amount": round(co["delta"]), "kind": "extra" if extra else "credit", "stage": stage_key}
