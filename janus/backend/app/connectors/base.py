"""
JUNO ERP Base Connector — Arquitetura Adapter Pattern
Todos os conectores específicos herdam desta classe base.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.audit_logger import AuditLogger
from app.core.crypto import decrypt
from app.core.datetime_utils import utcnow_naive
from app.models import ERPConnection, ERPFieldMapping, ERPSyncLog


class ERPConnectorBase(ABC):
    """
    Classe base abstrata para todos os conectores ERP.

    Como criar um novo conector:
    1. Herdar de ERPConnectorBase
    2. Implementar connect(), fetch_data(), validate_connection()
    3. Registrar em ERPConnectorFactory
    """

    def __init__(self, connection: ERPConnection, db: Session):
        self.connection = connection
        self.db = db
        self.audit = AuditLogger(db)
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def password(self) -> str | None:
        """Plain ERP password for runtime auth; never persist this value."""
        try:
            return decrypt(self.connection.password_encrypted)
        except ValueError as exc:
            self.errors.append(str(exc))
            return None

    @property
    def api_key(self) -> str | None:
        """Plain ERP API key for runtime auth."""
        try:
            return decrypt(self.connection.api_key)
        except ValueError:
            return self.connection.api_key

    @property
    def api_secret(self) -> str | None:
        """Plain ERP API secret for runtime auth."""
        try:
            return decrypt(self.connection.api_secret)
        except ValueError:
            return self.connection.api_secret

    # ============================================================
    # MÉTODOS ABSTRATOS (devem ser implementados)
    # ============================================================

    @abstractmethod
    def connect(self) -> bool:
        """
        Estabelece conexão com o ERP.
        Retorna True se conectado, False caso contrário.
        """
        pass

    @abstractmethod
    def validate_connection(self) -> dict[str, Any]:
        """
        Valida configurações de conexão.
        Retorna dict com status e detalhes.
        """
        pass

    @abstractmethod
    def fetch_data(
        self, entity_type: str, since: datetime | None = None, limit: int = 1000
    ) -> list[dict]:
        """
        Busca dados do ERP para uma entidade.

        Args:
            entity_type: Tipo de entidade (products, customers, orders, etc.)
            since: Data de corte para sync incremental
            limit: Máximo de registros

        Returns:
            Lista de dicionários com dados brutos do ERP
        """
        pass

    @abstractmethod
    def get_schema(self, entity_type: str) -> list[dict]:
        """
        Retorna schema do ERP para uma entidade.
        Útil para mapeamento automático de campos.
        """
        pass

    # ============================================================
    # MÉTODOS CONCRETOS (comportamento padrão)
    # ============================================================

    def sync_entity(self, entity_type: str, sync_type: str = "incremental") -> dict:
        """
        Executa sincronização completa para uma entidade.

        Args:
            entity_type: Tipo de entidade
            sync_type: 'full' ou 'incremental'

        Returns:
            Resultado da sincronização
        """
        # Criar log
        sync_log = ERPSyncLog(
            connection_id=self.connection.id,
            sync_type=sync_type,
            entity_type=entity_type,
            started_at=utcnow_naive(),
            status="running",
        )
        self.db.add(sync_log)
        self.db.commit()

        try:
            # Determinar data de corte
            since = None
            if sync_type == "incremental" and self.connection.last_sync:
                since = self.connection.last_sync

            # Buscar dados
            raw_data = self.fetch_data(entity_type, since=since)
            sync_log.records_found = len(raw_data)

            # Transformar dados
            transformed_data = self._transform_data(entity_type, raw_data)

            # Importar para JUNO
            imported, failed = self._import_to_juno(entity_type, transformed_data)

            sync_log.records_imported = imported
            sync_log.records_failed = failed
            sync_log.status = "completed" if failed == 0 else "partial"
            sync_log.completed_at = utcnow_naive()

            # Calcular duração
            duration = (sync_log.completed_at - sync_log.started_at).total_seconds()
            sync_log.duration_seconds = duration

            # Atualizar connection
            self.connection.last_sync = utcnow_naive()
            self.connection.status = "active"
            self.db.commit()

            # Auditoria
            self.audit.log(
                action=f"erp_sync_{entity_type}",
                details={
                    "connection_id": self.connection.id,
                    "erp_type": self.connection.erp_type,
                    "records_found": len(raw_data),
                    "records_imported": imported,
                    "duration_seconds": duration,
                },
            )

            return {
                "success": True,
                "records_found": len(raw_data),
                "records_imported": imported,
                "records_failed": failed,
                "duration_seconds": duration,
                "sync_log_id": sync_log.id,
            }

        except Exception as e:
            sync_log.status = "failed"
            sync_log.error_message = str(e)
            sync_log.completed_at = utcnow_naive()

            self.connection.status = "error"
            self.connection.last_error = str(e)
            self.db.commit()

            return {"success": False, "error": str(e), "sync_log_id": sync_log.id}

    def _transform_data(self, entity_type: str, raw_data: list[dict]) -> list[dict]:
        """
        Transforma dados do ERP para formato JUNO usando mapeamentos.
        """
        # Buscar mapeamentos ativos
        mappings = (
            self.db.query(ERPFieldMapping)
            .filter(
                ERPFieldMapping.connection_id == self.connection.id,
                ERPFieldMapping.entity_type == entity_type,
                ERPFieldMapping.is_active == True,
            )
            .all()
        )

        if not mappings:
            # Tentar mapeamento automático
            mappings = self._auto_generate_mappings(entity_type)

        # Criar dict de mapeamento
        field_map = {m.erp_field_name: m for m in mappings}

        transformed = []
        for record in raw_data:
            new_record = {}
            for erp_field, value in record.items():
                if erp_field in field_map:
                    mapping = field_map[erp_field]
                    juno_field = mapping.juno_field_name

                    # Aplicar transformação se houver
                    if mapping.transform_rule:
                        value = self._apply_transform(value, mapping.transform_rule)

                    # Converter tipo
                    value = self._convert_type(value, mapping.data_type)

                    new_record[juno_field] = value

            transformed.append(new_record)

        return transformed

    def _auto_generate_mappings(self, entity_type: str) -> list[ERPFieldMapping]:
        """
        Gera mapeamentos automáticos baseado em schema do ERP.
        """
        schema = self.get_schema(entity_type)

        # Mapeamentos padrão conhecidos
        default_maps = {
            "products": {
                "CODIGO": "name",
                "DESCRICAO": "name",
                "NOME": "name",
                "CUSTO": "standard_cost",
                "PRECO": "sale_price",
                "PRECO_VENDA": "sale_price",
                "CATEGORIA": "category",
            },
            "customers": {
                "CODIGO": "name",
                "NOME": "name",
                "RAZAO_SOCIAL": "name",
                "FANTASIA": "name",
                "CNPJ": "segment",
                "SETOR": "segment",
            },
            "sales_orders": {
                "NUMERO": "revenue",
                "CLIENTE": "customer_id",
                "PRODUTO": "product_id",
                "VALOR": "revenue",
                "TOTAL": "revenue",
                "DATA": "order_date",
            },
        }

        maps = default_maps.get(entity_type, {})
        generated = []

        for field_info in schema:
            erp_name = field_info.get("name", "")
            if erp_name in maps:
                mapping = ERPFieldMapping(
                    connection_id=self.connection.id,
                    entity_type=entity_type,
                    erp_field_name=erp_name,
                    juno_field_name=maps[erp_name],
                    data_type=field_info.get("type", "string"),
                    is_active=True,
                )
                self.db.add(mapping)
                generated.append(mapping)

        self.db.commit()
        return generated

    def _apply_transform(self, value: Any, rule: str) -> Any:
        """
        Aplica regra de transformação ao valor.
        """
        try:
            # Regras suportadas: uppercase, lowercase, trim, multiply:X, divide:X, add_days:X
            if rule == "uppercase":
                return str(value).upper() if value else value
            elif rule == "lowercase":
                return str(value).lower() if value else value
            elif rule == "trim":
                return str(value).strip() if value else value
            elif rule.startswith("multiply:"):
                factor = float(rule.split(":")[1])
                return float(value) * factor if value else 0
            elif rule.startswith("divide:"):
                factor = float(rule.split(":")[1])
                return float(value) / factor if value and factor != 0 else 0
            elif rule.startswith("add_days:"):
                int(rule.split(":")[1])
                # Assumir que value é datetime
                return value  # TODO: Implementar
            return value
        except (TypeError, ValueError):
            return value

    def _convert_type(self, value: Any, data_type: str) -> Any:
        """
        Converte valor para o tipo especificado.
        """
        if value is None:
            return None

        try:
            if data_type == "int":
                return int(float(str(value).replace(",", ".")))
            elif data_type == "float":
                return float(str(value).replace(",", "."))
            elif data_type == "bool":
                return str(value).lower() in ("true", "1", "yes", "sim", "s")
            elif data_type == "date":
                # Tentar múltiplos formatos
                if isinstance(value, datetime):
                    return value
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                    try:
                        return datetime.strptime(str(value), fmt)
                    except ValueError:
                        continue
                return None
            else:
                return str(value)
        except (TypeError, ValueError):
            return value

    def _import_to_juno(self, entity_type: str, data: list[dict]) -> tuple:
        """
        Importa dados transformados para as tabelas JUNO.
        Retorna (imported_count, failed_count).
        """
        from app.integrations.connector_importer import ERPImporterV2

        importer = ERPImporterV2(self.db)
        imported = 0
        failed = 0

        # Mapear entity_type para método do importer
        import_methods = {
            "products": importer._import_products,
            "customers": importer._import_customers,
            "sales_orders": importer._import_sales_orders,
            "production_orders": importer._import_production_orders,
            "inventory": importer._import_inventory,
            "suppliers": importer._import_suppliers,
            "financials": importer._import_financials,
        }

        method = import_methods.get(entity_type)
        if method:
            try:
                method(self.connection.company_id, data)
                imported = len(data)
            except Exception as e:
                failed = len(data)
                self.errors.append(str(e))
        else:
            failed = len(data)
            self.errors.append(f"Importador não implementado para: {entity_type}")

        return imported, failed

    def test_connection(self) -> dict:
        """
        Testa conexão e retorna diagnóstico completo.
        """
        result: dict[str, Any] = {
            "connected": False,
            "erp_type": self.connection.erp_type,
            "host": self.connection.host,
            "database": self.connection.database_name,
            "errors": [],
            "details": {},
        }

        try:
            is_connected = self.connect()
            result["connected"] = is_connected

            if is_connected:
                # Testar leitura
                schema = self.get_schema("products")
                result["details"]["schema_sample"] = schema[:3] if schema else []
                result["details"]["can_read"] = True
            else:
                result["errors"].append("Não foi possível conectar")

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def get_sync_status(self) -> dict:
        """
        Retorna status atual da sincronização.
        """
        last_logs = (
            self.db.query(ERPSyncLog)
            .filter(ERPSyncLog.connection_id == self.connection.id)
            .order_by(ERPSyncLog.started_at.desc())
            .limit(5)
            .all()
        )

        return {
            "connection_id": self.connection.id,
            "erp_type": self.connection.erp_type,
            "status": self.connection.status,
            "last_sync": (
                self.connection.last_sync.isoformat() if self.connection.last_sync else None
            ),
            "last_error": self.connection.last_error,
            "sync_frequency_minutes": self.connection.sync_frequency_minutes,
            "recent_syncs": [
                {
                    "id": log.id,
                    "entity_type": log.entity_type,
                    "status": log.status,
                    "records_found": log.records_found,
                    "records_imported": log.records_imported,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                }
                for log in last_logs
            ],
        }


class ERPConnectorFactory:
    """
    Factory para criar conectores ERP.
    """

    _connectors: dict[str, type[ERPConnectorBase]] = {}

    @classmethod
    def register(cls, erp_type: str, connector_class):
        """Registra um novo conector."""
        cls._connectors[erp_type] = connector_class

    @classmethod
    def get(cls, erp_type: str) -> type[ERPConnectorBase] | None:
        """Retorna a classe do conector, se registrada."""
        return cls._connectors.get(erp_type)

    @classmethod
    def create(cls, erp_type: str, connection: ERPConnection, db: Session) -> ERPConnectorBase:
        """Cria instância do conector apropriado."""
        if erp_type not in cls._connectors:
            raise ValueError(
                f"Conector não suportado: {erp_type}. Disponíveis: {list(cls._connectors.keys())}"
            )

        return cls._connectors[erp_type](connection, db)

    @classmethod
    def list_available(cls) -> list[str]:
        return list(cls._connectors.keys())
