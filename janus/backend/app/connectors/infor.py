"""
JUNO Infor Connector
Suporta: Infor LN (Baam), Infor M3, Infor CloudSuite
"""

from datetime import datetime
from typing import Any

import requests

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.models import ERPConnection


class InforConnector(ERPConnectorBase):
    """
    Conector para Infor.

    Modos de conexão:
    1. ION API (CloudSuite) — via Infor ION Grid
    2. REST (M3) — via M3 REST API
    3. SOAP (LN) — via LN Web Services
    """

    def __init__(self, connection: ERPConnection, db):
        super().__init__(connection, db)
        self.session = requests.Session()
        self.base_url: str | None = None
        self.ion_token = None

    def connect(self) -> bool:
        """Estabelece conexão com Infor."""
        try:
            if self.connection.auth_method == "ion_api":
                return self._connect_ion()
            elif self.connection.auth_method == "rest":
                return self._connect_rest()
            elif self.connection.auth_method == "soap":
                return self._connect_soap()
            else:
                return self._connect_ion()
        except Exception as e:
            self.errors.append(f"Erro de conexão Infor: {str(e)}")
            return False

    def _connect_ion(self) -> bool:
        """Conecta via ION API."""
        self.base_url = f"https://{self.connection.host}/InforIntSuite"

        # ION usa OAuth 2.0
        token_url = f"{self.base_url}/oauth2/token"
        auth_data = {
            "grant_type": "password",
            "username": self.connection.username,
            "password": self.password,
            "client_id": self.api_key,
            "client_secret": self.api_secret,
        }

        response = self.session.post(token_url, data=auth_data, verify=False, timeout=30)

        if response.status_code == 200:
            token_data = response.json()
            self.ion_token = token_data.get("access_token")
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.ion_token}",
                    "Content-Type": "application/json",
                    "X-Infor-Organization": self.connection.database_name or "",
                }
            )
            return True

        return False

    def _connect_rest(self) -> bool:
        """Conecta via REST (M3)."""
        self.base_url = f"http://{self.connection.host}:{self.connection.port or 8080}/m3api-rest"

        self.session.auth = (self.connection.username, self.password)  # type: ignore[assignment]

        return True

    def _connect_soap(self) -> bool:
        """Conecta via SOAP."""
        try:
            from zeep import Client

            wsdl_url = f"http://{self.connection.host}:{self.connection.port or 80}/ws/LN/soap"
            self.soap_client = Client(wsdl_url)
            return True
        except Exception as e:
            self.errors.append(f"Erro SOAP Infor: {str(e)}")
            return False

    def validate_connection(self) -> dict[str, Any]:
        """Valida configurações Infor."""
        required = ["host", "username", "password_encrypted"]
        missing = [f for f in required if not getattr(self.connection, f, None)]

        return {
            "valid": len(missing) == 0,
            "missing_fields": missing,
            "erp_type": "infor",
            "auth_method": self.connection.auth_method or "ion_api",
            "host": self.connection.host,
        }

    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        """Busca dados do Infor."""
        if self.connection.auth_method == "ion_api":
            return self._fetch_ion(entity_type, since, limit)
        elif self.connection.auth_method == "rest":
            return self._fetch_rest(entity_type, since, limit)
        elif self.connection.auth_method == "soap":
            return self._fetch_soap(entity_type, since, limit)
        return []

    def _fetch_ion(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via ION API."""
        endpoints = {
            "products": "record/ItemMaster",
            "customers": "record/BusinessPartner",
            "sales_orders": "record/SalesOrder",
        }

        entity = endpoints.get(entity_type, f"record/{entity_type}")
        url = f"{self.base_url}/{entity}"

        params: dict[str, Any] = {"pageSize": limit}

        if since:
            params["filter"] = f"LastModifiedDate ge {since.isoformat()}"

        response = self.session.get(url, params=params, verify=False, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                return data["items"]
            return data if isinstance(data, list) else []

        return []

    def _fetch_rest(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via REST (M3)."""
        # M3 usa programa específico
        programs = {"products": "MMS200MI", "customers": "CRS610MI", "sales_orders": "OIS100MI"}

        program = programs.get(entity_type, entity_type)
        url = f"{self.base_url}/execute/{program}/Lst"

        response = self.session.get(url, timeout=60)

        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []

        return []

    def _fetch_soap(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via SOAP."""
        return []

    def get_schema(self, entity_type: str) -> list[dict]:
        """Retorna schema Infor."""
        schemas = {
            "products": [
                {"name": "ItemNumber", "type": "string", "required": True},
                {"name": "Description", "type": "string", "required": True},
                {"name": "UnitCost", "type": "float", "required": True},
            ],
            "customers": [
                {"name": "CustomerNumber", "type": "string", "required": True},
                {"name": "Name", "type": "string", "required": True},
            ],
            "sales_orders": [
                {"name": "OrderNumber", "type": "string", "required": True},
                {"name": "Customer", "type": "string", "required": True},
            ],
        }

        return schemas.get(entity_type, [])


# Registrar no factory
ERPConnectorFactory.register("infor", InforConnector)
ERPConnectorFactory.register("infor_ln", InforConnector)
ERPConnectorFactory.register("infor_m3", InforConnector)
ERPConnectorFactory.register("infor_cloudsuite", InforConnector)
