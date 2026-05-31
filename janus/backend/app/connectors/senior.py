"""
JUNO Senior Connector
Suporta: Senior Sistemas (ERP, Gestão de Pessoas, etc.)
"""

from datetime import datetime
from typing import Any

import requests

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.models import ERPConnection


class SeniorConnector(ERPConnectorBase):
    """
    Conector para Senior Sistemas.

    Modos de conexão:
    1. REST API — via Senior API Platform
    2. SOAP — via webservices legados
    """

    def __init__(self, connection: ERPConnection, db):
        super().__init__(connection, db)
        self.session = requests.Session()
        self.base_url: str | None = None

    def connect(self) -> bool:
        """Estabelece conexão com Senior."""
        try:
            if self.connection.auth_method == "rest":
                return self._connect_rest()
            elif self.connection.auth_method == "soap":
                return self._connect_soap()
            else:
                return self._connect_rest()
        except Exception as e:
            self.errors.append(f"Erro de conexão Senior: {str(e)}")
            return False

    def _connect_rest(self) -> bool:
        """Conecta via REST API Senior."""
        self.base_url = f"https://{self.connection.host}/g5-senior-services"

        # Senior usa token de acesso
        auth_url = f"{self.base_url}/sam/auth/token"
        auth_data = {
            "username": self.connection.username,
            "password": self.password,
            "client_id": self.api_key,
        }

        response = self.session.post(auth_url, json=auth_data, verify=False, timeout=30)

        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get("access_token")
            self.session.headers.update(
                {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            return True

        return False

    def _connect_soap(self) -> bool:
        """Conecta via SOAP."""
        try:
            from zeep import Client

            wsdl_url = f"http://{self.connection.host}/services/rhu?wsdl"
            self.soap_client = Client(wsdl_url)
            return True
        except Exception as e:
            self.errors.append(f"Erro SOAP Senior: {str(e)}")
            return False

    def validate_connection(self) -> dict[str, Any]:
        """Valida configurações Senior."""
        required = ["host", "username", "password_encrypted"]
        missing = [f for f in required if not getattr(self.connection, f, None)]

        return {
            "valid": len(missing) == 0,
            "missing_fields": missing,
            "erp_type": "senior",
            "auth_method": self.connection.auth_method or "rest",
            "host": self.connection.host,
        }

    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        """Busca dados do Senior."""
        if self.connection.auth_method == "rest":
            return self._fetch_rest(entity_type, since, limit)
        elif self.connection.auth_method == "soap":
            return self._fetch_soap(entity_type, since, limit)
        return []

    def _fetch_rest(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via REST."""
        endpoints = {
            "products": "sapi/produto",
            "customers": "sapi/cliente",
            "sales_orders": "sapi/pedido",
        }

        endpoint = endpoints.get(entity_type, f"sapi/{entity_type}")
        url = f"{self.base_url}/{endpoint}"

        params: dict[str, Any] = {"limit": limit, "offset": 0}

        if since:
            params["dataAlteracao"] = since.strftime("%Y-%m-%d")

        response = self.session.get(url, params=params, verify=False, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                return data["data"]
            return data if isinstance(data, list) else []

        return []

    def _fetch_soap(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via SOAP."""
        return []

    def get_schema(self, entity_type: str) -> list[dict]:
        """Retorna schema Senior."""
        schemas = {
            "products": [
                {"name": "codigo", "type": "string", "required": True},
                {"name": "descricao", "type": "string", "required": True},
                {"name": "custo", "type": "float", "required": True},
                {"name": "preco", "type": "float", "required": True},
            ],
            "customers": [
                {"name": "codigo", "type": "string", "required": True},
                {"name": "razaoSocial", "type": "string", "required": True},
            ],
            "sales_orders": [
                {"name": "numero", "type": "string", "required": True},
                {"name": "cliente", "type": "string", "required": True},
            ],
        }

        return schemas.get(entity_type, [])


# Registrar no factory
ERPConnectorFactory.register("senior", SeniorConnector)
ERPConnectorFactory.register("senior_sistemas", SeniorConnector)
