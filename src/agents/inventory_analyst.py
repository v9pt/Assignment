"""
Agent 1 — Inventory & demand analysis.

Pulls current stock levels and sales velocity from the ERP, then asks
Gemini to assess whether a given replenishment recommendation is
reasonable or needs adjustment.
"""
import json
from src.llm_client import llm_client
from src.erp_tools import get_inventory_and_forecast
from src.models import AgentTraceStep


class InventoryAnalystAgent:
    def __init__(self):
        self.name = "Inventory & Demand Analyst"
        self.role = "Demand forecasting & burn-rate analysis"
        self.model = "Gemini 2.5 Flash"

    async def analyze(
        self,
        product_id: str,
        node_id: str,
        recommended_qty: int,
        context_notes: str = ""
    ) -> AgentTraceStep:
        telemetry = get_inventory_and_forecast(product_id, node_id)

        system_prompt = (
            "You are an inventory analyst for a quick-commerce fulfillment network. "
            "Audit the incoming replenishment recommendation: calculate burn rates, "
            "days of coverage, and flag any spoilage or stockout risk. "
            "Return a JSON object."
        )

        user_prompt = f"""
Inventory telemetry:
{json.dumps(telemetry, indent=2)}

Recommended purchase: {recommended_qty} units
Context: {context_notes}

Questions:
1. Is {recommended_qty} units justified, too high, or too low?
2. Current days of coverage vs target?
3. Stockout or spoilage risk?
4. Your adjusted quantity recommendation?

Return JSON with keys: analysis, healthy_coverage_target_days,
adjusted_demand_need, stockout_risk_score (0-1), justification.
"""
        raw = await llm_client.call_gemini(system_prompt, user_prompt)

        try:
            findings = json.loads(raw)
        except Exception:
            findings = {
                "raw_response": raw,
                "adjusted_demand_need": recommended_qty,
                "stockout_risk_score": 0.5
            }

        adjusted = findings.get("adjusted_demand_need", recommended_qty)
        thought = (
            f"Checked {recommended_qty}-unit recommendation against "
            f"{telemetry.get('current_inventory')} on-hand / "
            f"{telemetry.get('daily_demand_units')} units/day velocity. "
            f"Adjusted target: {adjusted} units."
        )

        return AgentTraceStep(
            agent_name=self.name,
            role=self.role,
            model=self.model,
            thought=thought,
            findings={
                "erp_telemetry": telemetry,
                "demand_analysis": findings
            },
            recommendation=str(findings.get("justification", findings.get("analysis", "")))
        )
