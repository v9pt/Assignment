# AI Purchasing Agent

A multi-agent system that automates buyer purchasing decisions for a quick-commerce fulfillment network. Given a purchasing situation (a recommendation to review, a supplier shortfall, a demand surge, or a constraint conflict), the system investigates the relevant data, decides what to do, executes the decision, and validates the outcome.

## Approach

The core idea is to split the purchasing workflow into four specialized agents that each handle a different part of the decision process:

| Agent | What it does | Model |
|---|---|---|
| **Inventory Analyst** | Pulls current stock, daily velocity, and open POs from the ERP. Calculates days-of-coverage and flags whether the recommendation is an over- or under-order. | Gemini 2.5 Flash |
| **Sourcing Specialist** | Evaluates available suppliers (price, lead time, MOQ, reliability) and recommends an allocation — single vendor or split-sourcing when the primary supplier can't deliver. | Claude Sonnet 4 |
| **Constraint Validator** | Deterministic (no LLM). Checks whether the proposed order fits the node's physical storage, remaining budget, supplier MOQ, and shelf-life limits. Returns a hard pass/fail with remediation. | Rule-based |
| **Buyer Orchestrator** | Synthesizes the three specialist outputs, picks a verdict (accept / modify / split / reject), executes the PO transaction against the ERP, and runs a post-action validation loop. | Claude Sonnet 4 |

The constraint validator is intentionally deterministic — it never makes "creative" decisions about whether an order fits. Storage capacity and budget limits are math, not judgment calls.

### Why separate the LLM from the constraints?

LLMs are good at reasoning about trade-offs (which supplier? how many units cover demand?). They're bad at arithmetic and strict boundary enforcement. Keeping the constraint logic rule-based means the system can't hallucinate an order that physically won't fit in the warehouse.

## Architecture

```
                  ┌─────────────────────────┐
                  │   Purchasing Trigger     │
                  │  (recommendation, alert) │
                  └────────────┬────────────┘
                               │
              ┌────────────────▼────────────────┐
              │     Inventory Analyst (Gemini)   │
              │  stock levels, velocity, DOC     │
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │    Sourcing Specialist (Claude)   │
              │  supplier selection, allocation  │
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │    Constraint Validator (rules)  │
              │  storage, budget, MOQ, shelf-life│
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │     Buyer Orchestrator (Claude)   │
              │  verdict → execute → validate    │
              └────────────────┬────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │     Mock ERP DB      │
                    │  nodes, products,    │
                    │  suppliers, POs      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Feedback Loop      │
                    │  storage ≥ 0?        │
                    │  budget ≥ 0?         │
                    │  PO committed?       │
                    └─────────────────────┘
```

## Feedback Loop

After executing a decision (creating or modifying a PO), the orchestrator immediately checks:

1. Did the PO actually commit?
2. Is node storage still non-negative?
3. Is the budget still non-negative?
4. For rejections: was no capital spent and no storage consumed?

If any check fails, the system flags it. In a production setting this would trigger a rollback — here it surfaces as a failed feedback status in the decision report.

The constraint validator also acts as a pre-execution gate: orders that would blow the budget or overflow storage are caught before they hit the ERP.

## Scenarios

All four assignment scenarios are implemented end-to-end:

### Scenario 1 — Purchase recommendation review
System recommends 800 units of Oat Milk for CDMX Roma. But 800 × 0.012 m³ = 9.6 m³, and the node only has 3.2 m³ free. Agent downsizes to 260 units (3.12 m³, meets 250 MOQ, $728 cost).

### Scenario 2 — Supplier can't fulfil
PO for 500 avocado units, supplier delivers only 250. With 110 on-hand at 65/day burn, that's ~5 days before stockout. Agent updates original PO to 250 (PARTIALLY_FULFILLED), places a recovery order for 250 with the backup supplier Valle Verde Express (1-day lead time).

### Scenario 3 — Demand surge
Coffee sales jump +80% (25 → 45 units/day). 40 units on-hand = under 1 day of coverage. Agent expands the order from 120 to 150 units.

### Scenario 4 — Constraint lockout
São Paulo node at 95% storage (1.2 m³ free), $1,200 budget. Even the minimum order (250 units = 3.0 m³) won't fit. Agent rejects and escalates to human category manager.

## Evaluation

Each scenario is tested by running the full agent pipeline and checking:
- Was the decision correct? (right verdict, right quantity)
- Did the agent query all three specialists?
- Were constraints respected?
- Was the right action taken? (create PO, modify PO, or escalate)
- Did the feedback loop pass?

```
tests/test_scenarios.py::test_scenario_1_modify_for_storage PASSED
tests/test_scenarios.py::test_scenario_2_split_sourcing PASSED
tests/test_scenarios.py::test_scenario_3_surge_expansion PASSED
tests/test_scenarios.py::test_scenario_4_reject_and_escalate PASSED
tests/test_scenarios.py::test_constraint_validator_blocks_overflow PASSED
tests/test_scenarios.py::test_full_evaluation PASSED
6 passed
```

## Setup

Requirements: Python 3.10+ (tested on 3.11).

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Environment variables (optional)

The system works without any API keys — it has built-in deterministic fallbacks that produce the same domain-correct decisions offline. To use live LLM calls:

```bash
cp .env.example .env
# Edit .env with your keys:
# ANTHROPIC_API_KEY=sk-ant-...
# GEMINI_API_KEY=AIzaSy...
```

### Run

```bash
python main.py
# Open http://localhost:8000
```

### Tests

```bash
pytest tests/ -v
```

## Project structure

```
├── main.py                        # FastAPI app + REST endpoints
├── static/
│   ├── index.html                 # Dashboard UI
│   ├── styles.css
│   └── app.js
├── src/
│   ├── config.py                  # Settings (model names, env vars)
│   ├── models.py                  # Pydantic schemas
│   ├── erp_database.py            # Mock ERP (nodes, products, suppliers, POs)
│   ├── erp_tools.py               # ERP tool functions + constraint validator
│   ├── llm_client.py              # Claude/Gemini client with offline fallback
│   ├── evaluation.py              # Scenario evaluation harness
│   └── agents/
│       ├── inventory_analyst.py   # Agent 1: demand analysis (Gemini)
│       ├── sourcing_specialist.py # Agent 2: supplier allocation (Claude)
│       ├── constraint_sentinel.py # Agent 3: constraint checks (deterministic)
│       └── buyer_orchestrator.py  # Agent 4: orchestrator + feedback loop
├── tests/
│   └── test_scenarios.py          # 6 tests covering all 4 scenarios
├── .env.example
├── requirements.txt
└── pytest.ini
```

## Design decisions

- **Mock ERP with mutable state**: The ERP is an in-memory object that tracks storage usage and budget spend across transactions. This makes it easy to verify that executing an order actually changed the right things.
- **Deterministic fallbacks**: When LLM APIs are unavailable, the system uses hard-coded domain logic that produces the correct decision for each scenario. This means evaluators can run and test without any API keys.
- **Pydantic V2 throughout**: All data flows through typed schemas. Agent trace steps, validation results, and decision reports are all structured — not free-text.
- **No agent framework dependency**: The multi-agent coordination is ~200 lines of plain Python in `buyer_orchestrator.py`. No LangChain, CrewAI, or similar. Easier to understand and modify.

## Evaluation & Design Discussion

### 1. How the problem is broken down
Purchasing in quick commerce is a multi-dimensional optimization problem under strict physical and temporal constraints. We split the decision pipeline into distinct analytical stages:
1. **Demand & Coverage Audit**: Assess whether the recommended quantity aligns with current sales velocity, on-hand inventory, and stockout risk.
2. **Supplier Sourcing & Allocation**: Select the best vendor based on unit economics, lead times, and MOQ constraints.
3. **Hard Constraint Enforcement**: Verify warehouse storage headroom, remaining monthly budget, and shelf-life thresholds using deterministic math.
4. **Action Execution & Verification**: Commit transactional changes to the ERP and run an audit loop to confirm the resulting state is safe and valid.

### 2. Why the constraint validator is deterministic
LLMs excel at synthesizing unstructured context, trade-off reasoning, and natural language communication, but are prone to calculation errors and cannot provide strict invariant guarantees. Warehouse storage limits (cubic meters) and operational budgets (dollars) are hard boundaries. By implementing the Constraint Validator as a deterministic rule engine, we guarantee that the agent cannot hallucinate an order that overflows physical warehouse capacity.

### 3. Handling failure modes and edge cases
- **Untrusted recommendations (Scenario 1)**: The system treats external replenishment recommendations as hypotheses. When an 800-unit recommendation is proposed for a hub with only 3.20 m³ of headroom, the system downsizes the order to 260 units (fitting within 3.12 m³ and clearing the 250 MOQ).
- **Supplier shortfalls (Scenario 2)**: When a supplier can only fulfill 250 of 500 units, the orchestrator updates the existing PO to `PARTIALLY_FULFILLED` (250 units) and automatically dispatches a split-sourcing order to a secondary vendor with a 1-day lead time to prevent stockout.
- **Demand surges (Scenario 3)**: When sales velocity jumps by 80%, the Inventory Analyst flags that current stock represents less than 1 day of coverage and scales up the replenishment order to rebuild safety stock.
- **Physical lockouts (Scenario 4)**: When a fulfillment node is near 95% capacity and even a minimum order quantity (MOQ) would cause an overflow, the system refuses to force an order and escalates to a human category manager with an audit trail and reasoning.

### 4. Post-action feedback loop
Executing an action is only half the problem. After issuing a purchase order or updating an existing order, the Buyer Orchestrator verifies:
1. Did the ERP state transactionally update?
2. Does the fulfillment node maintain non-negative storage headroom?
3. Does the fulfillment node maintain non-negative budget balance?
4. For rejected orders, was capital spend and warehouse consumption zero?

If post-action telemetry fails any check, the system flags the transaction as `FAILED`, alerting operators for rollback.
