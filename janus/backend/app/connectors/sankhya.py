"""
JUNO Sankhya Connector — Omni, W, SankhyaNet
"""

from datetime import datetime
from typing import Any

import requests

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.models import ERPConnection


class SankhyaConnector(ERPConnectorBase):
    def __init__(self, connection: ERPConnection, db=None):
        super().__init__(connection, db)
        self.session = requests.Session()
        self.base_url: str | None = None
        self.jsessionid: str | None = None

    def connect(self) -> bool:
        try:
            self.base_url = (
                f"http://{self.connection.host}:{self.connection.port or 8180}/mge/service.sbr"
            )
            payload: Any = {
                "serviceName": "MobileLoginSP.login",
                "requestBody": {
                    "NOMUSU": {"$": self.connection.username},
                    "INTERNO": {"$": self.password},
                    "KEEPCONNECTED": {"$": "S"},
                },
            }
            response = self.session.post(
                self.base_url,
                params={"serviceName": "MobileLoginSP.login", "outputType": "json"},
                json=payload,
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    self.jsessionid = response.cookies.get("JSESSIONID")
                    return True
            self.errors.append("Falha no login Sankhya")
            return False
        except Exception as e:
            self.errors.append(f"Erro conexao Sankhya: {str(e)}")
            return False

    def validate_connection(self) -> dict[str, Any]:
        required = ["host", "username", "password_encrypted"]
        missing = [f for f in required if not getattr(self.connection, f, None)]
        return {
            "valid": len(missing) == 0,
            "missing_fields": missing,
            "erp_type": "sankhya",
            "host": self.connection.host,
        }

    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        if self.base_url is None:
            return []

        entity_map = {"products": "TGFPRO", "customers": "TGFPAR", "sales_orders": "TGFCAB"}
        table = entity_map.get(entity_type, entity_type.upper())
        try:
            payload: dict[str, Any] = {
                "serviceName": "CRUDServiceProvider.loadRecords",
                "requestBody": {
                    "dataSet": {
                        "rootEntity": table,
                        "includePresentationFields": "N",
                        "offsetPage": "0",
                        "criteria": {"expression": {"$": "1=1"}},
                    }
                },
            }
            response = self.session.post(
                self.base_url,
                params={"serviceName": "CRUDServiceProvider.loadRecords", "outputType": "json"},
                json=payload,
                timeout=60,
            )
            if response.status_code == 200:
                data = response.json()
                rows = data.get("responseBody", {}).get("entities", {}).get("entity", [])
                if isinstance(rows, dict):
                    rows = [rows]
                return rows[:limit]
        except Exception as e:
            self.errors.append(f"Erro fetch Sankhya {entity_type}: {str(e)}")
        return []

    def get_schema(self, entity_type: str) -> list[dict]:
        return []


ERPConnectorFactory.register("sankhya", SankhyaConnector)
ERPConnectorFactory.register("sankhya_omni", SankhyaConnector)
ERPConnectorFactory.register("sankhya_w", SankhyaConnector)
