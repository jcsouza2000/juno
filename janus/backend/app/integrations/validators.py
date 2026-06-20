REQUIRED_FIELDS: dict[str, list[str]] = {
    "products": ["name"],
    "customers": ["name"],
    "sales_orders": ["customer_name", "product_name", "revenue"],
    "production_orders": ["product_name", "planned_qty", "actual_qty"],
    "inventory": ["product_name"],
    "suppliers": ["name"],
    "financials": ["account_name"],
}

ALLOWED_TYPES = list(REQUIRED_FIELDS.keys())


def validate_payload(data_type: str, columns: list[str]) -> dict:
    """Check that all required canonical fields are present after mapping."""
    required = REQUIRED_FIELDS.get(data_type, [])
    missing = [f for f in required if f not in columns]
    return {"valid": len(missing) == 0, "missing": missing}
