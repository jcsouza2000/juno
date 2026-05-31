"""
JUNO Generic ERP Connector — REST/JSON para ERPs nao catalogados
"""

import json
from datetime import datetime
from typing import Any

import requests

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.models import ERPConnection


class GenericConnector(ERPConnectorBase):
    def __init__(self, connection: ERPConnection, db=None):
        super().__init__(connection, db)
        self.session = requests.Session()
        self.base_url: str | None = None

    def connect(self) -> bool:
        try:
            self.base_url = f"http://{self.connection.host}:{self.connection.port or 80}"
            if self.api_key:
                self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
            elif self.connection.username:
                self.session.auth = (self.connection.username, self.password)
            return True
        except Exception as e:
            self.errors.append(f"Erro conexao generica: {str(e)}")
            return False

    def validate_connection(self) -> dict[str, Any]:
        missing = [] if getattr(self.connection, "host", None) else ["host"]
        return {
            "valid": len(missing) == 0,
            "missing_fields": missing,
            "erp_type": "generic",
            "host": self.connection.host,
        }

    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        extra: dict[str, Any] = (
            json.loads(self.connection.extra_config) if self.connection.extra_config else {}
        )
        endpoints = extra.get("endpoints", {})
        endpoint = endpoints.get(entity_type, f"/{entity_type}")
        url = f"{self.base_url}{endpoint}"
        try:
            params: dict[str, Any] = {"limit": limit}
            if since:
                params["updated_since"] = since.isoformat()
            response = self.session.get(url, params=params, timeout=60)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data[:limit]
                for key in ("items", "data", "results", "records"):
                    if key in data:
                        return data[key][:limit]
        except Exception as e:
            self.errors.append(f"Erro fetch generico {entity_type}: {str(e)}")
        return []

    def get_schema(self, entity_type: str) -> list[dict]:
        return []


ERPConnectorFactory.register("generic", GenericConnector)
ERPConnectorFactory.register("other", GenericConnector)
