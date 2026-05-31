"""
JUNO Oracle Connector
Suporta: Oracle E-Business Suite (EBS), JD Edwards, NetSuite
"""

from datetime import datetime
from typing import Any

import requests

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.models import ERPConnection


class OracleConnector(ERPConnectorBase):
    """Conector Oracle EBS / JD Edwards / NetSuite."""

    def __init__(self, connection: ERPConnection, db=None):
        super().__init__(connection, db)
        self.session = requests.Session()
        self.base_url: str | None = None

    def connect(self) -> bool:
        try:
            if self.connection.auth_method == "netsuite":
                return self._connect_netsuite()
            return self._connect_rest()
        except Exception as e:
            self.errors.append(f"Erro conexao Oracle: {str(e)}")
            return False

    def _connect_rest(self) -> bool:
        self.base_url = (
            f"https://{self.connection.host}:{self.connection.port or 443}/oracle/apps/rest"
        )
        self.session.auth = (self.connection.username, self.password)
        response = self.session.get(f"{self.base_url}/latest/products", verify=False, timeout=30)
        return response.status_code == 200

    def _connect_netsuite(self) -> bool:
        self.base_url = f"https://{self.connection.host or '1234567.suitetalk.api.netsuite.com'}"
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )
        response = self.session.get(f"{self.base_url}/services/rest/record/v1/products", timeout=30)
        return response.status_code == 200

    def validate_connection(self) -> dict[str, Any]:
        required = ["host", "username", "password_encrypted"]
        missing = [f for f in required if not getattr(self.connection, f, None)]
        return {
            "valid": len(missing) == 0,
            "missing_fields": missing,
            "erp_type": "oracle",
            "host": self.connection.host,
        }

    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        if self.connection.auth_method == "netsuite":
            return self._fetch_netsuite(entity_type, since, limit)
        return self._fetch_rest(entity_type, since, limit)

    def _fetch_rest(self, entity_type: str, since, limit: int) -> list[dict]:
        endpoints = {
            "products": "latest/products",
            "customers": "latest/customers",
            "sales_orders": "latest/salesOrders",
        }
        url = f"{self.base_url}/{endpoints.get(entity_type, f'latest/{entity_type}')}"
        params: dict[str, Any] = {"limit": limit, "offset": 0}
        if since:
            params["q"] = f"LastUpdateDate > '{since.strftime('%Y-%m-%d')}'"
        response = self.session.get(url, params=params, verify=False, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return data.get("items", data) if isinstance(data, dict) else data
        return []

    def _fetch_netsuite(self, entity_type: str, since, limit: int) -> list[dict]:
        endpoints = {
            "products": "inventoryItem",
            "customers": "customer",
            "sales_orders": "salesOrder",
        }
        entity = endpoints.get(entity_type, entity_type)
        url = f"{self.base_url}/services/rest/record/v1/{entity}"
        response = self.session.get(url, params={"limit": limit, "offset": 0}, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return data.get("items", []) if isinstance(data, dict) else data
        return []

    def get_schema(self, entity_type: str) -> list[dict]:
        return []


ERPConnectorFactory.register("oracle_ebs", OracleConnector)
ERPConnectorFactory.register("oracle_jde", OracleConnector)
ERPConnectorFactory.register("oracle_netsuite", OracleConnector)
