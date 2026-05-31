"""
JUNO SAP Connector
Suporta: SAP ECC, S/4HANA, Business One (B1)
"""

import base64
from datetime import datetime
from typing import Any

import requests

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.models import ERPConnection


class SAPConnector(ERPConnectorBase):
    """
    Conector para SAP.

    Modos de conexão:
    1. OData (S/4HANA) — via SAP Gateway
    2. SOAP (ECC) — via PI/PO
    3. DI API (Business One) — via COM/SOAP
    4. RFC (direto) — via pyrfc (opcional)
    """

    def __init__(self, connection: ERPConnection, db):
        super().__init__(connection, db)
        self.session = requests.Session()
        self.base_url: str | None = None
        self.csrf_token: str | None = None

    def connect(self) -> bool:
        """Estabelece conexão com SAP."""
        try:
            if self.connection.auth_method == "odata":
                return self._connect_odata()
            elif self.connection.auth_method == "soap":
                return self._connect_soap()
            elif self.connection.auth_method == "b1_di_api":
                return self._connect_b1()
            elif self.connection.auth_method == "basic":
                return self._connect_basic()
            else:
                return self._connect_odata()
        except Exception as e:
            self.errors.append(f"Erro de conexão SAP: {str(e)}")
            return False

    def _connect_odata(self) -> bool:
        """Conecta via OData (S/4HANA)."""
        self.base_url = (
            f"https://{self.connection.host}:{self.connection.port or 44300}/sap/opu/odata/sap"
        )

        # Autenticação Basic
        credentials = base64.b64encode(
            f"{self.connection.username}:{self.password}".encode()
        ).decode()

        self.session.headers.update(
            {"Authorization": f"Basic {credentials}", "x-csrf-token": "fetch"}
        )

        # Fetch CSRF token
        response = self.session.get(
            f"{self.base_url}/API_PRODUCT_SRV/$metadata", verify=False, timeout=30
        )

        if response.status_code == 200:
            self.csrf_token = response.headers.get("x-csrf-token")
            if self.csrf_token:
                self.session.headers["x-csrf-token"] = self.csrf_token
            return True

        return False

    def _connect_basic(self) -> bool:
        """Conecta via Basic Auth genérico."""
        self.base_url = f"http://{self.connection.host}:{self.connection.port or 8000}"

        credentials = base64.b64encode(
            f"{self.connection.username}:{self.password}".encode()
        ).decode()

        self.session.headers.update({"Authorization": f"Basic {credentials}"})

        return True

    def _connect_soap(self) -> bool:
        """Conecta via SOAP (ECC)."""
        try:
            from zeep import Client

            wsdl_url = f"http://{self.connection.host}:{self.connection.port or 8000}/sap/bc/srt/wsdl/flv_10002A111AD1/bndg_url/sap/bc/srt/rfc/sap/z_juno/100/z_juno/z_juno"
            self.soap_client = Client(wsdl_url)
            return True
        except Exception as e:
            self.errors.append(f"Erro SOAP SAP: {str(e)}")
            return False

    def _connect_b1(self) -> bool:
        """Conecta via DI API (Business One)."""
        # B1 usa COM ou SOAP
        self.base_url = f"http://{self.connection.host}:{self.connection.port or 8080}/B1iXcellerator/exec/soapapi.wsdl"
        try:
            from zeep import Client

            self.soap_client = Client(self.base_url)
            return True
        except Exception as e:
            self.errors.append(f"Erro B1 DI API: {str(e)}")
            return False

    def validate_connection(self) -> dict[str, Any]:
        """Valida configurações SAP."""
        required = ["host", "username", "password_encrypted"]
        missing = [f for f in required if not getattr(self.connection, f, None)]

        return {
            "valid": len(missing) == 0,
            "missing_fields": missing,
            "erp_type": "sap",
            "auth_method": self.connection.auth_method or "odata",
            "host": self.connection.host,
            "port": self.connection.port,
            "sap_version": self._detect_sap_version(),
        }

    def _detect_sap_version(self) -> str:
        """Tenta detectar versão do SAP."""
        # Simplificado — em produção, consultar system info
        if "s4" in (self.connection.database_name or "").lower():
            return "S/4HANA"
        elif "ecc" in (self.connection.database_name or "").lower():
            return "ECC"
        elif "b1" in (self.connection.erp_type or "").lower():
            return "Business One"
        return "Unknown"

    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        """Busca dados do SAP."""
        if self.connection.auth_method in ["odata", "basic"]:
            return self._fetch_odata(entity_type, since, limit)
        elif self.connection.auth_method == "soap":
            return self._fetch_soap(entity_type, since, limit)
        elif self.connection.auth_method == "b1_di_api":
            return self._fetch_b1(entity_type, since, limit)
        return []

    def _fetch_odata(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via OData."""
        # Mapear para entidades OData SAP
        odata_entities = {
            "products": "API_PRODUCT_SRV/A_Product",
            "customers": "API_BUSINESS_PARTNER/A_BusinessPartner",
            "sales_orders": "API_SALES_ORDER_SRV/A_SalesOrder",
            "production_orders": "API_PRODUCTION_ORDER/ProductionOrder",
        }

        entity = odata_entities.get(entity_type, entity_type)
        url = f"{self.base_url}/{entity}"

        params: dict[str, Any] = {"$top": limit, "$format": "json"}

        if since:
            params["$filter"] = f"LastChangeDateTime ge datetime'{since.isoformat()}'"

        response = self.session.get(url, params=params, verify=False, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if "d" in data and "results" in data["d"]:
                return data["d"]["results"]
            return data if isinstance(data, list) else []

        return []

    def _fetch_soap(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via SOAP."""
        # Implementação simplificada
        return []

    def _fetch_b1(self, entity_type: str, since: datetime | None, limit: int) -> list[dict]:
        """Busca via Business One DI API."""
        # Implementação simplificada
        return []

    def get_schema(self, entity_type: str) -> list[dict]:
        """Retorna schema SAP."""
        schemas = {
            "products": [
                {"name": "Product", "type": "string", "required": True},
                {"name": "ProductDescription", "type": "string", "required": True},
                {"name": "BaseUnit", "type": "string", "required": True},
                {"name": "NetWeight", "type": "float", "required": False},
            ],
            "customers": [
                {"name": "BusinessPartner", "type": "string", "required": True},
                {"name": "BusinessPartnerName", "type": "string", "required": True},
                {"name": "BusinessPartnerType", "type": "string", "required": True},
            ],
            "sales_orders": [
                {"name": "SalesOrder", "type": "string", "required": True},
                {"name": "SalesOrderType", "type": "string", "required": True},
                {"name": "SalesOrganization", "type": "string", "required": True},
            ],
        }

        return schemas.get(entity_type, [])


# Registrar no factory
ERPConnectorFactory.register("sap", SAPConnector)
ERPConnectorFactory.register("sap_ecc", SAPConnector)
ERPConnectorFactory.register("sap_s4hana", SAPConnector)
ERPConnectorFactory.register("sap_b1", SAPConnector)
ERPConnectorFactory.register("sap_business_one", SAPConnector)
