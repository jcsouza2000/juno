"""Testes dos models ERP novos (Connection, SyncLog, FieldMapping)."""

from app.core.datetime_utils import utcnow_naive
from app.models import (
    Company,
    ERPConnection,
    ERPFieldMapping,
    ERPSyncLog,
)


def test_erp_connection_crud(db_session):
    company = Company(name="ACME", sector="industria")
    db_session.add(company)
    db_session.commit()

    conn = ERPConnection(
        company_id=company.id,
        erp_type="totvs_protheus",
        name="Producao Matriz",
        host="erp.acme.local",
        port=8080,
        username="api_user",
        password_encrypted="ct-encrypted-here",
        auth_method="basic",
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)

    assert conn.id is not None
    assert conn.company_id == company.id
    assert conn.is_active is True
    assert conn.status == "inactive"


def test_sync_log_relationship(db_session):
    company = Company(name="X", sector="y")
    db_session.add(company)
    db_session.commit()
    conn = ERPConnection(company_id=company.id, erp_type="sap_ecc", name="X", host="h")
    db_session.add(conn)
    db_session.commit()

    log = ERPSyncLog(
        connection_id=conn.id,
        sync_type="full",
        entity_type="products",
        started_at=utcnow_naive(),
        status="completed",
        records_found=100,
        records_imported=98,
        records_failed=2,
    )
    db_session.add(log)
    db_session.commit()

    db_session.refresh(conn)
    assert len(conn.sync_logs) == 1
    assert conn.sync_logs[0].entity_type == "products"


def test_field_mapping_relationship(db_session):
    company = Company(name="X", sector="y")
    db_session.add(company)
    db_session.commit()
    conn = ERPConnection(company_id=company.id, erp_type="generic", name="X", host="h")
    db_session.add(conn)
    db_session.commit()

    mapping = ERPFieldMapping(
        connection_id=conn.id,
        entity_type="products",
        erp_field_name="CODIGO",
        juno_field_name="name",
        data_type="string",
    )
    db_session.add(mapping)
    db_session.commit()

    db_session.refresh(conn)
    assert len(conn.field_mappings) == 1
    assert conn.field_mappings[0].erp_field_name == "CODIGO"


def test_cascade_delete_connection(db_session):
    company = Company(name="X", sector="y")
    db_session.add(company)
    db_session.commit()
    conn = ERPConnection(company_id=company.id, erp_type="generic", name="X", host="h")
    db_session.add(conn)
    db_session.commit()
    db_session.add(
        ERPSyncLog(
            connection_id=conn.id,
            sync_type="full",
            entity_type="products",
            started_at=utcnow_naive(),
            status="completed",
        )
    )
    db_session.commit()

    db_session.delete(conn)
    db_session.commit()
    assert db_session.query(ERPSyncLog).count() == 0
