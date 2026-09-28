"""
Executable ERP Tools & Deterministic Constraint Validator.
These tools are invoked by the AI Purchasing Agents to inspect telemetry,
evaluate physical/financial constraints, and execute transactional actions.
"""
from typing import Dict, Any, List, Optional
import uuid
from src.erp_database import erp_db
from src.models import PurchaseOrder, ValidationResult


def get_inventory_and_forecast(product_id: str, node_id: str) -> Dict[str, Any]:
    """Retrieve current stock level, sales velocity, forecast, and incoming pipeline."""
    product = erp_db.get_product(product_id)
    node = erp_db.get_node(node_id)
    if not product or not node:
        return {"error": f"Product {product_id} or Node {node_id} not found"}

    open_pos = erp_db.get_open_pos(node_id=node_id, product_id=product_id)
    incoming_qty = sum(po.requested_qty for po in open_pos if po.status in ("SUBMITTED", "APPROVED"))

    days_of_coverage = product.current_inventory / product.daily_demand if product.daily_demand > 0 else 999.0
    days_of_coverage_with_incoming = (product.current_inventory + incoming_qty) / product.daily_demand if product.daily_demand > 0 else 999.0

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
        "incoming_pipeline_qty": incoming_qty,
        "open_pos_count": len(open_pos),
        "days_of_coverage_current": round(days_of_coverage, 1),
        "days_of_coverage_with_pipeline": round(days_of_coverage_with_incoming, 1),
        "stockout_risk": days_of_coverage < 2.5
    }


def get_node_constraints(node_id: str) -> Dict[str, Any]:
    """Inspect warehouse physical storage capacity and monthly purchasing budget limits."""
    node = erp_db.get_node(node_id)
    if not node:
        return {"error": f"Node {node_id} not found"}

    storage_utilization_pct = (node.used_storage_capacity_m3 / node.total_storage_capacity_m3) * 100
    budget_utilization_pct = (node.spent_budget / node.monthly_budget) * 100

    return {
        "node_id": node.id,
        "node_name": node.name,
        "location": node.location,
        "total_storage_capacity_m3": node.total_storage_capacity_m3,
        "used_storage_capacity_m3": node.used_storage_capacity_m3,
        "available_storage_m3": round(node.available_storage_m3, 3),
        "storage_utilization_pct": round(storage_utilization_pct, 1),
        "monthly_budget": node.monthly_budget,
        "spent_budget": node.spent_budget,
        "available_budget": round(node.available_budget, 2),
        "budget_utilization_pct": round(budget_utilization_pct, 1)
    }


def get_available_suppliers(product_id: str) -> List[Dict[str, Any]]:
    """Retrieve all qualified suppliers for a product with pricing, lead times, and reliability."""
    suppliers = erp_db.get_suppliers_for_product(product_id)
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
        for s in suppliers
    ]


def validate_purchase_order_constraints(
    product_id: str,
    node_id: str,
    supplier_id: str,
    quantity: int
) -> ValidationResult:
    """
    DETERMINISTIC CONSTRAINT SENTINEL:
    Strict mathematical validation of physical storage, financial budget,
    supplier MOQ, and perishability/shelf-life coverage.
    """
    product = erp_db.get_product(product_id)
    node = erp_db.get_node(node_id)
    supplier = erp_db.get_supplier(supplier_id)

    violations = []
    remediation_suggestion = None

    if not product or not node or not supplier:
        return ValidationResult(
            is_valid=False,
            budget_ok=False,
            storage_ok=False,
            moq_ok=False,
            shelf_life_ok=False,
            violations=["Invalid product, node, or supplier identifier."]
        )

    # 1. MOQ Check
    moq_ok = quantity >= supplier.moq
    if not moq_ok:
        violations.append(
            f"Quantity ({quantity}) is below Supplier MOQ of {supplier.moq} units."
        )

    # 2. Storage Capacity Check
    order_volume = quantity * product.unit_volume_m3
    storage_ok = order_volume <= node.available_storage_m3
    if not storage_ok:
        max_possible_by_storage = int(node.available_storage_m3 / product.unit_volume_m3)
        violations.append(
            f"Volume ({order_volume:.2f} m3) exceeds available storage ({node.available_storage_m3:.2f} m3). "
            f"Maximum allowable units: {max_possible_by_storage}."
        )

    # 3. Budget Check
    order_cost = quantity * supplier.unit_price
    budget_ok = order_cost <= node.available_budget
    if not budget_ok:
        max_possible_by_budget = int(node.available_budget / supplier.unit_price)
        violations.append(
            f"Order cost (${order_cost:.2f}) exceeds available budget (${node.available_budget:.2f}). "
            f"Maximum allowable units by budget: {max_possible_by_budget}."
        )

    # 4. Perishability & Spoilage Check
    shelf_life_ok = True
    if product.shelf_life_days <= 15:
        # Perishable items: total coverage (current + order) should not exceed shelf life
        total_units = product.current_inventory + quantity
        days_of_supply = total_units / product.daily_demand if product.daily_demand > 0 else 999.0
        if days_of_supply > product.shelf_life_days:
            shelf_life_ok = False
            violations.append(
                f"Perishability breach: Order creates {days_of_supply:.1f} days of supply, "
                f"exceeding product shelf life of {product.shelf_life_days} days. High spoilage risk!"
            )

    is_valid = moq_ok and storage_ok and budget_ok and shelf_life_ok

    if not is_valid:
        # Calculate feasible upper bound
        max_by_storage = int(node.available_storage_m3 / product.unit_volume_m3)
        max_by_budget = int(node.available_budget / supplier.unit_price)
        feasible_upper = min(max_by_storage, max_by_budget)
        if feasible_upper >= supplier.moq:
            remediation_suggestion = (
                f"Adjust order quantity to {feasible_upper} units to satisfy both "
                f"storage ({max_by_storage}) and budget ({max_by_budget}) while meeting MOQ ({supplier.moq})."
            )
        else:
            remediation_suggestion = (
                f"Physical storage allows max {max_by_storage} units, but supplier MOQ is {supplier.moq}. "
                f"Order cannot be satisfied without secondary supplier or human capacity override."
            )

    return ValidationResult(
        is_valid=is_valid,
        budget_ok=budget_ok,
        storage_ok=storage_ok,
        moq_ok=moq_ok,
        shelf_life_ok=shelf_life_ok,
        violations=violations,
        remediation_suggestion=remediation_suggestion
    )


def execute_create_purchase_order(
    product_id: str,
    node_id: str,
    supplier_id: str,
    quantity: int,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Execute transactional Purchase Order creation in ERP after validation.
    Applies real state updates to available warehouse volume and spent budget.
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
        id=po_id,
        po_number=po_number,
        product_id=product_id,
        node_id=node_id,
        supplier_id=supplier_id,
        requested_qty=quantity,
        confirmed_qty=quantity,
        unit_price=supplier.unit_price,
        total_cost=order_cost,
        total_volume_m3=order_volume,
        status="APPROVED",
        notes=notes
    )

    # Commit state changes to ERP
    erp_db.purchase_orders[po_id] = new_po
    node.used_storage_capacity_m3 += order_volume
    node.spent_budget += order_cost

    return {
        "success": True,
        "status": "APPROVED",
        "po_id": po_id,
        "po_number": po_number,
        "quantity": quantity,
        "unit_price": supplier.unit_price,
        "total_cost": order_cost,
        "total_volume_m3": order_volume,
        "node_id": node_id,
        "supplier_id": supplier_id,
        "supplier_name": supplier.name,
        "updated_storage_available_m3": round(node.available_storage_m3, 3),
        "updated_budget_available": round(node.available_budget, 2)
    }


def execute_modify_purchase_order(
    po_id: str,
    new_quantity: int,
    status: str = "MODIFIED",
    notes: str = ""
) -> Dict[str, Any]:
    """Modify an existing purchase order (e.g., when supplier cuts quantity)."""
    if po_id not in erp_db.purchase_orders:
        return {"success": False, "error": f"PO {po_id} not found"}

    po = erp_db.purchase_orders[po_id]
    product = erp_db.get_product(po.product_id)
    node = erp_db.get_node(po.node_id)

    # Revert previous allocation from node
    node.used_storage_capacity_m3 -= po.total_volume_m3
    node.spent_budget -= po.total_cost

    # Update PO
    po.requested_qty = new_quantity
    po.confirmed_qty = new_quantity
    po.total_cost = new_quantity * po.unit_price
    po.total_volume_m3 = new_quantity * product.unit_volume_m3
    po.status = status
    po.notes = notes

    # Re-apply new footprint
    node.used_storage_capacity_m3 += po.total_volume_m3
    node.spent_budget += po.total_cost

    return {
        "success": True,
        "po_id": po.id,
        "po_number": po.po_number,
        "new_quantity": new_quantity,
        "new_status": status,
        "total_cost": po.total_cost,
        "notes": notes
    }
