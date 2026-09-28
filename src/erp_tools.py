"""
ERP tool functions — the "APIs" that agents call to read state
and execute transactions against the mock database.
"""
from typing import Dict, Any, List
import uuid
from src.erp_database import erp_db
from src.models import PurchaseOrder, ValidationResult


def get_inventory_and_forecast(product_id: str, node_id: str) -> Dict[str, Any]:
    """Return current stock, velocity, forecast, and pipeline for a product at a node."""
    product = erp_db.get_product(product_id)
    node = erp_db.get_node(node_id)
    if not product or not node:
        return {"error": f"Product {product_id} or Node {node_id} not found"}

    open_pos = erp_db.get_open_pos(node_id=node_id, product_id=product_id)
    incoming = sum(po.requested_qty for po in open_pos if po.status in ("SUBMITTED", "APPROVED"))

    doc = product.current_inventory / product.daily_demand if product.daily_demand > 0 else 999.0
    doc_with_pipeline = (product.current_inventory + incoming) / product.daily_demand if product.daily_demand > 0 else 999.0

    return {
        "product_id": product.id,
        "product_name": product.name,
        "category": product.category,
        "current_inventory": product.current_inventory,
        "daily_demand_units": product.daily_demand,
        "forecast_demand_7d": product.forecast_demand_7d,
        "safety_stock_threshold": product.safety_stock_threshold,
        "shelf_life_days": product.shelf_life_days,
        "unit_volume_m3": product.unit_volume_m3,
        "incoming_pipeline_qty": incoming,
        "open_pos_count": len(open_pos),
        "days_of_coverage_current": round(doc, 1),
        "days_of_coverage_with_pipeline": round(doc_with_pipeline, 1),
        "stockout_risk": doc < 2.5
    }


def get_node_constraints(node_id: str) -> Dict[str, Any]:
    """Return storage capacity and budget status for a fulfillment node."""
    node = erp_db.get_node(node_id)
    if not node:
        return {"error": f"Node {node_id} not found"}

    return {
        "node_id": node.id,
        "node_name": node.name,
        "location": node.location,
        "total_storage_capacity_m3": node.total_storage_capacity_m3,
        "used_storage_capacity_m3": node.used_storage_capacity_m3,
        "available_storage_m3": round(node.available_storage_m3, 3),
        "storage_utilization_pct": round(node.used_storage_capacity_m3 / node.total_storage_capacity_m3 * 100, 1),
        "monthly_budget": node.monthly_budget,
        "spent_budget": node.spent_budget,
        "available_budget": round(node.available_budget, 2),
        "budget_utilization_pct": round(node.spent_budget / node.monthly_budget * 100, 1)
    }


def get_available_suppliers(product_id: str) -> List[Dict[str, Any]]:
    """Return all qualified suppliers for a product."""
    return [
        {
            "supplier_id": s.id,
            "supplier_name": s.name,
            "unit_price": s.unit_price,
            "lead_time_days": s.lead_time_days,
            "moq": s.moq,
            "reliability_score": s.reliability_score,
            "max_capacity": s.max_capacity,
            "notes": s.notes
        }
        for s in erp_db.get_suppliers_for_product(product_id)
    ]


def validate_purchase_order_constraints(
    product_id: str,
    node_id: str,
    supplier_id: str,
    quantity: int
) -> ValidationResult:
    """
    Check a proposed order against hard constraints:
    1. Supplier MOQ
    2. Node storage capacity (m3)
    3. Node remaining budget
    4. Shelf-life / spoilage (for perishables)

    Returns a ValidationResult with pass/fail per constraint and a
    remediation suggestion when the order can be adjusted to fit.
    """
    product = erp_db.get_product(product_id)
    node = erp_db.get_node(node_id)
    supplier = erp_db.get_supplier(supplier_id)
    violations = []

    if not product or not node or not supplier:
        return ValidationResult(
            is_valid=False, budget_ok=False, storage_ok=False,
            moq_ok=False, shelf_life_ok=False,
            violations=["Invalid product, node, or supplier ID."]
        )

    # MOQ
    moq_ok = quantity >= supplier.moq
    if not moq_ok:
        violations.append(f"Quantity {quantity} < supplier MOQ {supplier.moq}.")

    # Storage
    volume_needed = quantity * product.unit_volume_m3
    storage_ok = volume_needed <= node.available_storage_m3
    if not storage_ok:
        max_by_storage = int(node.available_storage_m3 / product.unit_volume_m3)
        violations.append(
            f"Needs {volume_needed:.2f} m3 but only {node.available_storage_m3:.2f} m3 available "
            f"(max {max_by_storage} units)."
        )

    # Budget
    cost = quantity * supplier.unit_price
    budget_ok = cost <= node.available_budget
    if not budget_ok:
        max_by_budget = int(node.available_budget / supplier.unit_price)
        violations.append(
            f"Cost ${cost:.2f} exceeds remaining budget ${node.available_budget:.2f} "
            f"(max {max_by_budget} units)."
        )

    # Shelf-life (only relevant for perishables)
    shelf_life_ok = True
    if product.shelf_life_days <= 15:
        total_units = product.current_inventory + quantity
        days_supply = total_units / product.daily_demand if product.daily_demand > 0 else 999.0
        if days_supply > product.shelf_life_days:
            shelf_life_ok = False
            violations.append(
                f"Would create {days_supply:.1f} days of supply, exceeding "
                f"{product.shelf_life_days}-day shelf life."
            )

    is_valid = moq_ok and storage_ok and budget_ok and shelf_life_ok
    remediation = None

    if not is_valid:
        max_s = int(node.available_storage_m3 / product.unit_volume_m3)
        max_b = int(node.available_budget / supplier.unit_price)
        feasible = min(max_s, max_b)
        if feasible >= supplier.moq:
            remediation = (
                f"Reduce to {feasible} units (storage limit {max_s}, "
                f"budget limit {max_b}, MOQ {supplier.moq})."
            )
        else:
            remediation = (
                f"Max feasible is {feasible} units but MOQ is {supplier.moq}. "
                f"Need a different supplier or human override."
            )

    return ValidationResult(
        is_valid=is_valid, budget_ok=budget_ok, storage_ok=storage_ok,
        moq_ok=moq_ok, shelf_life_ok=shelf_life_ok,
        violations=violations, remediation_suggestion=remediation
    )


def execute_create_purchase_order(
    product_id: str,
    node_id: str,
    supplier_id: str,
    quantity: int,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Create a new PO after validating constraints. Updates node storage and
    budget state to reflect the committed order.
    """
    val = validate_purchase_order_constraints(product_id, node_id, supplier_id, quantity)
    if not val.is_valid:
        return {
            "success": False,
            "status": "VALIDATION_FAILED",
            "violations": val.violations,
            "remediation_suggestion": val.remediation_suggestion
        }

    product = erp_db.get_product(product_id)
    node = erp_db.get_node(node_id)
    supplier = erp_db.get_supplier(supplier_id)

    order_cost = quantity * supplier.unit_price
    order_volume = quantity * product.unit_volume_m3
    po_id = f"po_{uuid.uuid4().hex[:8]}"
    po_number = f"PO-2026-{uuid.uuid4().hex[:4].upper()}"

    new_po = PurchaseOrder(
        id=po_id, po_number=po_number,
        product_id=product_id, node_id=node_id, supplier_id=supplier_id,
        requested_qty=quantity, confirmed_qty=quantity,
        unit_price=supplier.unit_price,
        total_cost=order_cost, total_volume_m3=order_volume,
        status="APPROVED", notes=notes
    )

    erp_db.purchase_orders[po_id] = new_po
    node.used_storage_capacity_m3 += order_volume
    node.spent_budget += order_cost

    return {
        "success": True, "status": "APPROVED",
        "po_id": po_id, "po_number": po_number,
        "quantity": quantity, "unit_price": supplier.unit_price,
        "total_cost": order_cost, "total_volume_m3": order_volume,
        "supplier_name": supplier.name,
        "remaining_storage_m3": round(node.available_storage_m3, 3),
        "remaining_budget": round(node.available_budget, 2)
    }


def execute_modify_purchase_order(
    po_id: str,
    new_quantity: int,
    status: str = "MODIFIED",
    notes: str = ""
) -> Dict[str, Any]:
    """Update an existing PO's quantity and status. Adjusts node state accordingly."""
    if po_id not in erp_db.purchase_orders:
        return {"success": False, "error": f"PO {po_id} not found"}

    po = erp_db.purchase_orders[po_id]
    product = erp_db.get_product(po.product_id)
    node = erp_db.get_node(po.node_id)

    # Undo old allocation
    node.used_storage_capacity_m3 -= po.total_volume_m3
    node.spent_budget -= po.total_cost

    # Apply new values
    po.requested_qty = new_quantity
    po.confirmed_qty = new_quantity
    po.total_cost = new_quantity * po.unit_price
    po.total_volume_m3 = new_quantity * product.unit_volume_m3
    po.status = status
    po.notes = notes

    node.used_storage_capacity_m3 += po.total_volume_m3
    node.spent_budget += po.total_cost

    return {
        "success": True, "po_id": po.id, "po_number": po.po_number,
        "new_quantity": new_quantity, "new_status": status,
        "total_cost": po.total_cost
    }
