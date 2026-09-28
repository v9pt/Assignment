"""
Data models and schemas for the AI Buyer Agent System.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class Product(BaseModel):
    id: str
    name: str
    category: str
    unit_cost: float
    unit_volume_m3: float = 0.02  # e.g., 0.02 m3 per unit
    shelf_life_days: int = 30
    current_inventory: int
    daily_demand: float
    forecast_demand_7d: float
    safety_stock_threshold: int


class Supplier(BaseModel):
    id: str
    name: str
    product_id: str
    unit_price: float
    lead_time_days: int
    moq: int  # Minimum Order Quantity
    reliability_score: float  # 0.0 to 1.0 (historical fulfillment rate)
    max_capacity: int
    notes: Optional[str] = None


class FulfillmentNode(BaseModel):
    id: str
    name: str
    location: str
    total_storage_capacity_m3: float
    used_storage_capacity_m3: float
    monthly_budget: float
    spent_budget: float

    @property
    def available_storage_m3(self) -> float:
        return max(0.0, self.total_storage_capacity_m3 - self.used_storage_capacity_m3)

    @property
    def available_budget(self) -> float:
        return max(0.0, self.monthly_budget - self.spent_budget)


class PurchaseOrder(BaseModel):
    id: str
    po_number: str
    product_id: str
    node_id: str
    supplier_id: str
    requested_qty: int
    confirmed_qty: int = 0
    unit_price: float
    total_cost: float
    total_volume_m3: float
    status: Literal[
        "PENDING_REVIEW",
        "APPROVED",
        "SUBMITTED",
        "PARTIALLY_FULFILLED",
        "MODIFIED",
        "REJECTED",
        "CANCELLED"
    ] = "PENDING_REVIEW"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: Optional[str] = None


class AgentTraceStep(BaseModel):
    agent_name: str
    role: str
    model: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    thought: str
    findings: Dict[str, Any] = Field(default_factory=dict)
    recommendation: Optional[str] = None


class ValidationResult(BaseModel):
    is_valid: bool
    budget_ok: bool
    storage_ok: bool
    moq_ok: bool
    shelf_life_ok: bool
    violations: List[str] = Field(default_factory=list)
    remediation_suggestion: Optional[str] = None


class DecisionReport(BaseModel):
    scenario_id: str
    scenario_name: str
    original_recommendation_qty: int
    verdict: Literal["ACCEPT", "MODIFY", "REJECT", "ESCALATE", "SPLIT_SOURCING"]
    recommended_qty: int
    supplier_id: str
    supplier_name: str
    estimated_cost: float
    volume_m3: float
    confidence_score: float  # 0.0 - 1.0
    rationale: str
    feedback_loop_passed: bool
    feedback_loop_details: str
    agent_traces: List[AgentTraceStep] = Field(default_factory=list)
    actions_executed: List[Dict[str, Any]] = Field(default_factory=list)
    human_approval_required: bool = False
    human_approval_reason: Optional[str] = None


class Scenario(BaseModel):
    id: str
    scenario_number: int
    title: str
    subtitle: str
    description: str
    node_id: str
    product_id: str
    recommended_qty: int
    existing_po_id: Optional[str] = None
    supplier_shortfall_qty: Optional[int] = None
    demand_surge_percentage: Optional[float] = None
