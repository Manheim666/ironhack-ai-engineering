# Assessment Submission — Multi-Tool Order Assistant

## Scenario & tools
**Order assistant.** Three tools, chosen because the goal genuinely needs all
three chained and no single one answers it:

| Tool | Job |
|---|---|
| `lookup_order(order_id)` | item, unit price, purchase date, warranty months |
| `check_warranty(order_id)` | is it under warranty *today* + expiry date (real date math) |
| `calculate(expression)` | exact arithmetic (models are unreliable at math) |

**Goal:** *"I want two more of order A1001 — total cost, and is it still under
warranty?"* The agent decides the order itself: `lookup_order` → `calculate`
(price × 2) → `check_warranty`, then composes the answer.

## Structured output
The run ends with a constrained JSON pass (`response_schema = OrderQuote`), so the
final result is parseable, not free text:

```json
{
  "order_id": "A1001", "item": "laptop", "unit_price": 1200,
  "quantity": 2, "total_cost": 2400,
  "under_warranty": true, "warranty_expires": "2027-05-20",
  "notes": "..."
}
```

## Reliability note
The loop is bounded by `MAX_STEPS = 6`. If the agent never converges it exits the
`for/else` and returns `{"error": "step limit reached…"}` instead of looping
forever. Tool failures are returned **as data** (`{"error": …}`), never raised —
so an unknown order id (`A9999`) degrades into an honest answer rather than a
crash.

## Safety note
**Mitigation: validate every tool call before it runs** (`validate_and_run`).
It rejects unknown tools, missing/extra args, and non-alphanumeric `order_id`s;
`calculate` additionally whitelists characters so no code execution rides in
through an "expression". Tool results are also treated as untrusted **data** (the
system instruction tells the agent never to obey instructions found inside tool
output). This defends against **argument-injection / tool abuse** — a model (or a
poisoned data source) trying to smuggle `order_id = "A1; DROP …"` or
`expression = "__import__('os')…"` is blocked at the gate.

## Captured run
Tools + safety gate verified live (`python solution.py --selftest`):

```
 lookup_order('A1001')   -> {'item':'laptop','price':1200,'purchased':'2026-05-20','warranty_months':12}
 check_warranty('A1001') -> {'under_warranty': True,  'warranty_expires': '2027-05-20'}
 check_warranty('A1004') -> {'under_warranty': False, 'warranty_expires': '2025-03-10'}
 calculate('1200 * 2')   -> {'result': 2400}
 validate unknown tool   -> {'error': "refused: unknown tool 'rm_rf'"}
 validate missing arg    -> {'error': "refused: missing argument 'order_id' for lookup_order"}
 validate bad order_id   -> {'error': 'refused: order_id must be alphanumeric'}
```

The full agent trace + structured JSON print when `GOOGLE_API_KEY` is set
(`python solution.py`). No API key is committed — the key is read from the
environment.
