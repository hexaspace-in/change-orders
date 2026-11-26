# change-orders

Change orders (variation orders) for interior and construction projects, after the client has signed the BOQ.

- **Build a change order** from three kinds of change: add an item, remove an item, or change a quantity. It works out the money difference (rates include GST), adds extra days, and records the reason (client request, site condition, design change)
- **Vendor guard**: lines already ordered from a vendor can't be removed or reduced. This is checked at draft time and again at approval
- **Apply** an approved change order to the BOQ. New lines are tagged CO-01, removed lines are marked, and quantities are updated
- **Shift the plan** by the client-approved days (open stages only)
- **Payment milestone** for extra cost, or a **credit** when the change saves money

Works with plain dicts and pairs well with [interior-boq](https://github.com/hexaspace-in/interior-boq). Built from the change-order flow Hexaspace runs on real projects.

## Example

```python
from change_orders import build_change_order, apply_change_order, co_number, milestone_for

co = build_change_order(boq, [
        {"action": "add", "name": "Study table", "room": "Bedroom", "category": "carpentry", "unit": "nos", "qty": 1, "rate": 25000},
        {"action": "qty", "line_id": "wardrobe-1", "qty": 50},
    ], number=co_number(0), title="Bedroom changes", days=5, ordered=ids_already_ordered)

co["delta"]                       # money difference incl. GST
new_boq = apply_change_order(boq, co, ordered=ids_already_ordered)
milestone_for(co)                 # {'label': 'Change order CO-01', 'amount': ..., 'kind': 'extra'}
```

## Licence

MIT. Maintained by [Hexaspace](https://hexaspace.in).
