"""
JUNO ERP Connectors Package
"""

from app.connectors.base import ERPConnectorBase, ERPConnectorFactory
from app.connectors.generic import GenericConnector
from app.connectors.infor import InforConnector
from app.connectors.oracle import OracleConnector
from app.connectors.sankhya import SankhyaConnector
from app.connectors.sap import SAPConnector
from app.connectors.senior import SeniorConnector
from app.connectors.totvs import TOTVSConnector

__all__ = [
    "ERPConnectorBase",
    "ERPConnectorFactory",
    "TOTVSConnector",
    "SAPConnector",
    "OracleConnector",
    "InforConnector",
    "SeniorConnector",
    "SankhyaConnector",
    "GenericConnector",
]
