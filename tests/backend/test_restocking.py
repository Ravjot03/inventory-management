"""
Tests for restocking order endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """The order store is in-memory; reset it around every test."""
    main.restock_orders.clear()
    yield
    main.restock_orders.clear()


def _sku_and_cost():
    forecast = main.demand_forecasts[0]
    return forecast["item_sku"], forecast["unit_cost"], forecast["lead_time_days"]


class TestRestockingOrders:
    """Test suite for /api/restocking-orders."""

    def test_demand_forecasts_include_cost_and_lead_time(self, client):
        response = client.get("/api/demand")
        assert response.status_code == 200
        for forecast in response.json():
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] > 0

    def test_list_empty_initially(self, client):
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_order_success(self, client):
        sku, unit_cost, lead_time = _sku_and_cost()
        response = client.post(
            "/api/restocking-orders",
            json={"items": [{"sku": sku, "quantity": 10}], "budget": 10 * unit_cost + 100},
        )
        assert response.status_code == 201
        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["total_cost"] == round(10 * unit_cost, 2)
        assert order["lead_time_days"] == lead_time
        assert order["items"][0]["sku"] == sku

    def test_lead_time_is_max_across_lines(self, client):
        forecasts = main.demand_forecasts[:2]
        items = [{"sku": f["item_sku"], "quantity": 1} for f in forecasts]
        budget = sum(f["unit_cost"] for f in forecasts) + 1
        response = client.post("/api/restocking-orders", json={"items": items, "budget": budget})
        assert response.status_code == 201
        assert response.json()["lead_time_days"] == max(f["lead_time_days"] for f in forecasts)

    def test_client_cannot_override_cost(self, client):
        sku, unit_cost, _ = _sku_and_cost()
        response = client.post(
            "/api/restocking-orders",
            json={"items": [{"sku": sku, "quantity": 2, "unit_cost": 0.01}], "budget": 1000000},
        )
        assert response.status_code == 201
        assert response.json()["total_cost"] == round(2 * unit_cost, 2)

    def test_over_budget_rejected(self, client):
        sku, unit_cost, _ = _sku_and_cost()
        response = client.post(
            "/api/restocking-orders",
            json={"items": [{"sku": sku, "quantity": 10}], "budget": 10 * unit_cost - 1},
        )
        assert response.status_code == 400

    def test_empty_items_rejected(self, client):
        response = client.post("/api/restocking-orders", json={"items": [], "budget": 1000})
        assert response.status_code == 400

    def test_non_positive_quantity_rejected(self, client):
        sku, _, _ = _sku_and_cost()
        response = client.post(
            "/api/restocking-orders", json={"items": [{"sku": sku, "quantity": 0}], "budget": 1000}
        )
        assert response.status_code == 400

    def test_unknown_sku_rejected(self, client):
        response = client.post(
            "/api/restocking-orders", json={"items": [{"sku": "NOPE-999", "quantity": 1}], "budget": 1000}
        )
        assert response.status_code == 404

    def test_submitted_order_appears_in_list_newest_first(self, client):
        sku, unit_cost, _ = _sku_and_cost()
        payload = {"items": [{"sku": sku, "quantity": 1}], "budget": unit_cost + 1}
        first = client.post("/api/restocking-orders", json=payload).json()
        second = client.post("/api/restocking-orders", json=payload).json()
        listed = client.get("/api/restocking-orders").json()
        assert [o["id"] for o in listed] == [second["id"], first["id"]]
