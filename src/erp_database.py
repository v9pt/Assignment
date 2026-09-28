"""
In-memory mock ERP database.

Holds fulfillment nodes, products, suppliers, purchase orders, and
scenario definitions. Resets to a known state between test runs.
"""
from typing import Dict, List, Optional
from copy import deepcopy
from src.models import Product, Supplier, FulfillmentNode, PurchaseOrder, Scenario


class ERPDatabase:
    def __init__(self):
        self._init_data()

    def _init_data(self):
        # Fulfillment Nodes (Dark Stores)
        self.nodes: Dict[str, FulfillmentNode] = {
            "node_bogota_norte": FulfillmentNode(
                id="node_bogota_norte",
                name="Bogotá Chapinero Dark Store",
                location="Bogotá, Colombia",
                total_storage_capacity_m3=18.0,
                used_storage_capacity_m3=10.5,  # 7.5 m3 available
                monthly_budget=20000.0,
                spent_budget=13200.0           # $6,800 available
            ),
            "node_cdmx_roma": FulfillmentNode(
                id="node_cdmx_roma",
                name="CDMX Roma Norte Micro-Hub",
                location="Mexico City, Mexico",
                total_storage_capacity_m3=15.0,
                used_storage_capacity_m3=11.8,  # 3.2 m3 available
                monthly_budget=25000.0,
                spent_budget=21500.0           # $3,500 available
            ),
            "node_sao_paulo_pinheiros": FulfillmentNode(
                id="node_sao_paulo_pinheiros",
                name="São Paulo Pinheiros Dark Store",
                location="São Paulo, Brazil",
                total_storage_capacity_m3=25.0,
                used_storage_capacity_m3=23.8,  # 1.2 m3 available
                monthly_budget=30000.0,
                spent_budget=28800.0           # $1,200 available
            )
        }

        # Products Catalog
        self.products: Dict[str, Product] = {
            "prod_oat_milk_barista": Product(
                id="prod_oat_milk_barista",
                name="Oat Milk Barista Edition 1L",
                category="Dairy & Plant-Based Alternatives",
                unit_cost=2.80,
                unit_volume_m3=0.012,
                shelf_life_days=90,
                current_inventory=80,
                daily_demand=45.0,
                forecast_demand_7d=315.0,
                safety_stock_threshold=90
            ),
            "prod_avocado_hass": Product(
                id="prod_avocado_hass",
                name="Hass Avocado 1kg Mesh Pack",
                category="Fresh Produce / Perishable",
                unit_cost=3.50,
                unit_volume_m3=0.015,
                shelf_life_days=12,
                current_inventory=110,
                daily_demand=65.0,
                forecast_demand_7d=455.0,
                safety_stock_threshold=120
            ),
            "prod_premium_coffee_beans": Product(
                id="prod_premium_coffee_beans",
                name="Specialty Roasted Coffee Beans 500g",
                category="Beverages & Pantry",
                unit_cost=7.50,
                unit_volume_m3=0.008,
                shelf_life_days=180,
                current_inventory=40,
                daily_demand=25.0,
                forecast_demand_7d=175.0,
                safety_stock_threshold=50
            )
        }

        # Qualified Suppliers
        self.suppliers: Dict[str, Supplier] = {
            "supp_oat_master": Supplier(
                id="supp_oat_master",
                name="OatMaster Global Ltd",
                product_id="prod_oat_milk_barista",
                unit_price=2.80,
                lead_time_days=3,
                moq=250,                    # Minimum Order 250 units
                reliability_score=0.96,
                max_capacity=2500,
                notes="Primary partner. Tier-1 wholesale discount. Strict MOQ."
            ),
            "supp_quick_beverages": Supplier(
                id="supp_quick_beverages",
                name="QuickBev Regional Logistics",
                product_id="prod_oat_milk_barista",
                unit_price=3.15,
                lead_time_days=1,           # Express next-day delivery
                moq=100,
                reliability_score=0.91,
                max_capacity=800,
                notes="Secondary emergency supplier. Higher price but fast 24h lead time."
            ),
            "supp_agricola_central": Supplier(
                id="supp_agricola_central",
                name="Agrícola Central Valley",
                product_id="prod_avocado_hass",
                unit_price=3.50,
                lead_time_days=2,
                moq=200,
                reliability_score=0.94,
                max_capacity=1500,
                notes="Primary grower cooperative. High quality produce."
            ),
            "supp_valle_verde_express": Supplier(
                id="supp_valle_verde_express",
                name="Valle Verde Express Farms",
                product_id="prod_avocado_hass",
                unit_price=3.85,
                lead_time_days=1,           # 1-day express
                moq=100,
                reliability_score=0.92,
                max_capacity=900,
                notes="Backup agricultural distributor. Flexible order sizes, rapid dispatch."
            ),
            "supp_andes_roasters": Supplier(
                id="supp_andes_roasters",
                name="Andes Specialty Roasters",
                product_id="prod_premium_coffee_beans",
                unit_price=7.50,
                lead_time_days=4,
                moq=100,
                reliability_score=0.98,
                max_capacity=1000,
                notes="Exclusive roastery partner. High value items."
            )
        }

        # Open Purchase Orders
        self.purchase_orders: Dict[str, PurchaseOrder] = {
            "po_scenario_2": PurchaseOrder(
                id="po_scenario_2",
                po_number="PO-2026-0891",
                product_id="prod_avocado_hass",
                node_id="node_bogota_norte",
                supplier_id="supp_agricola_central",
                requested_qty=500,
                confirmed_qty=0,
                unit_price=3.50,
                total_cost=1750.0,
                total_volume_m3=7.5,
                status="SUBMITTED",
                notes="Original replenishing order for Chapinero node."
            )
        }

        # Test scenarios
        self.scenarios: Dict[str, Scenario] = {
            "scenario_1": Scenario(
                id="scenario_1",
                scenario_number=1,
                title="Scenario 1: Purchase Recommendation Review",
                subtitle="Evaluate 800-unit recommendation against storage & budget limits",
                description=(
                    "The purchasing system recommends buying 800 units of Oat Milk Barista for CDMX Roma node. "
                    "Current stock is 80 units, 7-day forecast is 315 units. "
                    "Available storage at CDMX node is only 3.2 m3 (800 units need 9.6 m3!). "
                    "Available budget is $3,500. The agent must investigate, determine whether to accept, "
                    "modify, or reject, optimize order quantity to fit physical storage, and validate."
                ),
                node_id="node_cdmx_roma",
                product_id="prod_oat_milk_barista",
                recommended_qty=800
            ),
            "scenario_2": Scenario(
                id="scenario_2",
                scenario_number=2,
                title="Scenario 2: Supplier Cannot Fulfil Purchase",
                subtitle="Handle 50% supplier stockout (250 / 500 units delivered)",
                description=(
                    "A purchase order (PO-2026-0891) for 500 units of Hass Avocado was submitted to Agrícola Central, "
                    "but the supplier informs the system that only 250 units can currently be supplied. "
                    "Avocados burn at 65 units/day with only 110 units on hand. The shortfall will cause a stockout "
                    "within 5.5 days. The agent must evaluate alternative suppliers (Valle Verde Express), "
                    "decide whether to split or source the remaining 250 units, execute the recovery PO, and validate."
                ),
                node_id="node_bogota_norte",
                product_id="prod_avocado_hass",
                recommended_qty=500,
                existing_po_id="po_scenario_2",
                supplier_shortfall_qty=250
            ),
            "scenario_3": Scenario(
                id="scenario_3",
                scenario_number=3,
                title="Scenario 3: Demand & Forecast Surge",
                subtitle="Quick-commerce flash surge (+80% sales velocity)",
                description=(
                    "Coffee bean sales velocity surged by +80% due to a local promotion. "
                    "Existing inventory (40 units) and old forecast are insufficient to sustain demand. "
                    "The agent investigates sales telemetry, computes updated Days of Coverage (DOC), "
                    "and issues an expedited PO to avoid lost revenue while staying within node parameters."
                ),
                node_id="node_bogota_norte",
                product_id="prod_premium_coffee_beans",
                recommended_qty=120,
                demand_surge_percentage=80.0
            ),
            "scenario_4": Scenario(
                id="scenario_4",
                scenario_number=4,
                title="Scenario 4: Severe Purchasing Constraint Breach",
                subtitle="Dual Warehouse Capacity & Capital Lockout -> Human Escalation",
                description=(
                    "System generates a 600-unit restocking request for São Paulo Pinheiros node. "
                    "However, the node is at 95% storage capacity (only 1.2 m3 remaining, needs 7.2 m3) "
                    "and has only $1,200 remaining monthly budget ($1,680 needed). "
                    "The agent detects that even the supplier MOQ (250 units = $700, 3.0 m3) exceeds storage. "
                    "Instead of failing or making an illegal order, the agent rejects the recommendation "
                    "and triggers an urgent Human Escalation ticket for Category Management."
                ),
                node_id="node_sao_paulo_pinheiros",
                product_id="prod_oat_milk_barista",
                recommended_qty=600
            )
        }

    def reset(self):
        """Restore all data to the initial state."""
        self._init_data()

    def get_node(self, node_id: str) -> Optional[FulfillmentNode]:
        return self.nodes.get(node_id)

    def get_product(self, product_id: str) -> Optional[Product]:
        return self.products.get(product_id)

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        return self.suppliers.get(supplier_id)

    def get_suppliers_for_product(self, product_id: str) -> List[Supplier]:
        return [s for s in self.suppliers.values() if s.product_id == product_id]

    def get_open_pos(self, node_id: Optional[str] = None, product_id: Optional[str] = None) -> List[PurchaseOrder]:
        pos = list(self.purchase_orders.values())
        if node_id:
            pos = [p for p in pos if p.node_id == node_id]
        if product_id:
            pos = [p for p in pos if p.product_id == product_id]
        return pos


erp_db = ERPDatabase()
