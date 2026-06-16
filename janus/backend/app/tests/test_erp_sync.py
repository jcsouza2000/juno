"""Testes do skeleton de sincronizacao ERP ao vivo (run_connection_sync)."""

from types import SimpleNamespace

from app.services.erp_sync import live_sync_enabled, run_connection_sync


class _FakeConnector:
    def __init__(self, *, connected=True, results=None, errors=None):
        self._connected = connected
        self._results = results or {}
        self.errors = errors or []

    def connect(self):
        return self._connected

    def sync_entity(self, entity_type, sync_type="incremental"):
        return self._results.get(entity_type, {"success": True, "records_imported": 0})


class _FakeFactory:
    def __init__(self, connector, available=("totvs_protheus",)):
        self._connector = connector
        self._available = list(available)

    def list_available(self):
        return self._available

    def create(self, erp_type, connection, db):
        return self._connector


def _conn(erp_type="totvs_protheus"):
    return SimpleNamespace(id=10, company_id=4, erp_type=erp_type)


def test_run_connection_sync_aggregates_and_completes():
    connector = _FakeConnector(
        results={
            "products": {"success": True, "records_imported": 3},
            "customers": {"success": True, "records_imported": 2},
            "sales_orders": {"success": True, "records_imported": 5},
        }
    )
    factory = _FakeFactory(connector)

    outcome = run_connection_sync(db=None, connection=_conn(), factory=factory)  # type: ignore[arg-type]

    assert outcome.records_imported == 10
    assert outcome.status == "completed"
    assert outcome.errors == []
    assert outcome.company_id == 4


def test_run_connection_sync_marks_failed_on_entity_error():
    connector = _FakeConnector(
        results={
            "products": {"success": False, "error": "timeout", "records_imported": 0},
        }
    )
    factory = _FakeFactory(connector)

    outcome = run_connection_sync(db=None, connection=_conn(), factory=factory)  # type: ignore[arg-type]

    assert outcome.status == "failed"
    assert any("products" in e for e in outcome.errors)


def test_run_connection_sync_skips_unregistered_connector():
    factory = _FakeFactory(_FakeConnector(), available=("sap_ecc",))

    outcome = run_connection_sync(db=None, connection=_conn("infor_ln"), factory=factory)  # type: ignore[arg-type]

    assert outcome.status == "skipped"


def test_run_connection_sync_failed_when_cannot_connect():
    connector = _FakeConnector(connected=False, errors=["sem rede"])
    factory = _FakeFactory(connector)

    outcome = run_connection_sync(db=None, connection=_conn(), factory=factory)  # type: ignore[arg-type]

    assert outcome.status == "failed"
    assert "sem rede" in outcome.errors


def test_live_sync_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("ERP_LIVE_SYNC_ENABLED", raising=False)
    assert live_sync_enabled() is False
    monkeypatch.setenv("ERP_LIVE_SYNC_ENABLED", "true")
    assert live_sync_enabled() is True
