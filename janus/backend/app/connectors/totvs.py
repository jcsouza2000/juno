"""
JUNO TOTVS Connector
Suporta: Protheus (TOTVS ERP), RM (TOTVS RM), Datasul
"""

import json
from datetime import datetime
from typing import Any

import requests
import urllib3

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.models import ERPConnection

# Desabilitar warnings SSL (dev apenas)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TOTVSConnector(ERPConnectorBase):
    """
    Conector para ERPs TOTVS.

    Modos de conexão:
    1. REST API (Protheus) — via TOTVS Application Server
    2. SOAP (RM) — via webservices RM
    3. ODBC (Datasul) — via Progress OpenEdge
    """

    def __init__(self, connection: ERPConnection, db):
        super().__init__(connection, db)
        self.session = requests.Session()
        self.base_url: str | None = None
        self.auth_token: str | None = None

    def connect(self) -> bool:
        """
        Estabelece conexão com TOTVS.
        """
        try:
            if self.connection.auth_method == "rest":
                return self._connect_rest()
            elif self.connection.auth_method == "soap":
                return self._connect_soap()
            elif self.connection.auth_method == "odbc":
                return self._connect_odbc()
            else:
                # Tentar REST por padrão
                return self._connect_rest()
        except Exception as e:
            self.errors.append(f"Erro de conexão TOTVS: {str(e)}")
            return False

    def _connect_rest(self) -> bool:
        """Conecta via REST API (Protheus)."""
        self.base_url = f"http://{self.connection.host}:{self.connection.port or 8080}/rest"

        # Autenticação
        auth_url = f"{self.base_url}/api/oauth2/v1/token"
        auth_data = {
            "grant_type": "password",
            "username": self.connection.username,
            "password": self.password,
            "client_id": self.api_key or "JUNO",
            "client_secret": self.api_secret or "",
        }

        response = self.session.post(auth_url, json=auth_data, verify=False, timeout=30)

        if response.status_code == 200:
            token_data = response.json()
            self.auth_token = token_data.get("access_token")
            self.session.headers.update(
                {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/json"}
            )
            return True

        return False

    def _connect_soap(self) -> bool:
        """Conecta via SOAP (RM)."""
        try:
            from zeep import Client

            wsdl_url = f"http://{self.connection.host}:{self.connection.port or 8051}/wsconsultasql/MEX?wsdl"
            self.soap_client = Client(wsdl_url)
            return True
        except Exception as e:
            self.errors.append(f"Erro SOAP: {str(e)}")
            return False

    def _connect_odbc(self) -> bool:
        """Conecta via ODBC (Datasul)."""
        try:
            import pyodbc

            conn_str = (
                f"DRIVER={{Progress OpenEdge 11.3 Driver}};"
                f"HOST={self.connection.host};"
                f"PORT={self.connection.port or 25010};"
                f"DB={self.connection.database_name};"
                f"UID={self.connection.username};"
                f"PWD={self.password};"
            )
            self.odbc_conn = pyodbc.connect(conn_str, timeout=30)
            return True
        except Exception as e:
            self.errors.append(f"Erro ODBC: {str(e)}")
            return False

    def validate_connection(self) -> dict[str, Any]:
        """Valida configurações de conexão TOTVS."""
        required = ["host", "username", "password_encrypted"]
        missing = [f for f in required if not getattr(self.connection, f, None)]

        return {
            "valid": len(missing) == 0,
            "missing_fields": missing,
            "erp_type": "totvs",
            "auth_method": self.connection.auth_method or "rest",
            "host": self.connection.host,
            "port": self.connection.port,
        }

    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        """Busca dados do TOTVS."""
        if self.connection.auth_method == "rest":
            return self._fetch_rest(entity_type, since, limit)
        elif self.connection.auth_method == "soap":
            return self._fetch_soap(entity_type, since, limit)
        elif self.connection.auth_method == "odbc":
            return self._fetch_odbc(entity_type, since, limit)
        return []

    def _fetch_rest(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via REST API."""
        # Mapear entity_type para endpoint TOTVS
        endpoints = {
            "products": "Products",
            "customers": "Customers",
            "sales_orders": "SalesOrders",
            "production_orders": "ProductionOrders",
            "inventory": "Inventory",
        }

        endpoint = endpoints.get(entity_type, entity_type)
        url = f"{self.base_url}/api/framework/v1/{endpoint}"

        params: dict[str, Any] = {"limit": limit, "offset": 0}

        if since:
            params["modified_since"] = since.isoformat()

        response = self.session.get(url, params=params, verify=False, timeout=60)

        if response.status_code == 200:
            data = response.json()
            # TOTVS retorna estrutura aninhada
            if isinstance(data, dict) and "items" in data:
                return data["items"]
            return data if isinstance(data, list) else []

        return []

    def _fetch_soap(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via SOAP."""
        # Usar zeep para chamar métodos SOAP
        queries = {
            "products": "SELECT CODIGO, DESCRICAO, CUSTO, PRECO_VENDA FROM SB1010 WHERE D_E_L_E_T_ = ''",
            "customers": "SELECT CODIGO, NOME, FANTASIA, CNPJ FROM SA1010 WHERE D_E_L_E_T_ = ''",
            "sales_orders": "SELECT NUM, CLIENTE, PRODUTO, QUANT, VALOR FROM SC5010 WHERE D_E_L_E_T_ = ''",
        }

        query = queries.get(entity_type, f"SELECT * FROM {entity_type}")

        try:
            result = self.soap_client.service.Consultar(query)
            # Parse resultado SOAP
            return self._parse_soap_result(result)
        except Exception as e:
            self.errors.append(f"Erro SOAP fetch: {str(e)}")
            return []

    def _fetch_odbc(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via ODBC."""
        queries = {
            "products": "SELECT item-code, item-name, cost, price FROM item",
            "customers": "SELECT cust-num, name, address FROM customer",
            "sales_orders": "SELECT order-num, cust-num, item-num, qty, price FROM order-line",
        }

        query = queries.get(entity_type, f"SELECT * FROM {entity_type}")

        if since:
            query += f" WHERE modified-date >= '{since.strftime('%Y-%m-%d')}'"

        query += f" LIMIT {limit}"

        try:
            cursor = self.odbc_conn.cursor()
            cursor.execute(query)

            columns = [desc[0] for desc in cursor.description]
            rows = []

            for row in cursor.fetchall():
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                rows.append(row_dict)

            return rows

        except Exception as e:
            self.errors.append(f"Erro ODBC fetch: {str(e)}")
            return []

    def _parse_soap_result(self, result) -> list[dict]:
        """Parse resultado SOAP para lista de dicts."""
        # Implementação simplificada
        if hasattr(result, "Resultado"):
            return json.loads(result.Resultado)
        return []

    def get_schema(self, entity_type: str) -> list[dict]:
        """Retorna schema do TOTVS."""
        schemas = {
            "products": [
                {"name": "CODIGO", "type": "string", "required": True},
                {"name": "DESCRICAO", "type": "string", "required": True},
                {"name": "CUSTO", "type": "float", "required": True},
                {"name": "PRECO_VENDA", "type": "float", "required": True},
                {"name": "CATEGORIA", "type": "string", "required": False},
            ],
            "customers": [
                {"name": "CODIGO", "type": "string", "required": True},
                {"name": "NOME", "type": "string", "required": True},
                {"name": "FANTASIA", "type": "string", "required": False},
                {"name": "CNPJ", "type": "string", "required": False},
            ],
            "sales_orders": [
                {"name": "NUM", "type": "string", "required": True},
                {"name": "CLIENTE", "type": "string", "required": True},
                {"name": "PRODUTO", "type": "string", "required": True},
                {"name": "VALOR", "type": "float", "required": True},
                {"name": "DATA", "type": "date", "required": True},
            ],
        }

        return schemas.get(entity_type, [])


# Registrar no factory
ERPConnectorFactory.register("totvs", TOTVSConnector)
ERPConnectorFactory.register("totvs_protheus", TOTVSConnector)
ERPConnectorFactory.register("totvs_rm", TOTVSConnector)
ERPConnectorFactory.register("totvs_datasul", TOTVSConnector)
