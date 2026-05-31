"""
Conftest para testes da ontologia.

Fixa env vars de teste ANTES de importar app, depois expoe fixtures:
  - db_session: SQLite isolado, tabelas criadas e limpas entre testes
  - admin_user_ctx: UserContext com role=admin
  - tenant_user_ctx_factory: cria UserContext para tenant especifico
  - seed_data: popula Company/Product/SalesOrder de exemplo
  - loaded_registry: Registry com os YAMLs reais ja carregados
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

_tmp_dir = tempfile.mkdtemp(prefix="juno-ontology-test-")
_test_db_path = Path(_tmp_dir) / "test.db"
os.environ.setdefault("JUNO_ENV", "development")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_db_path}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-min-32-chars")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ALLOWED_ORIGINS", "http://testserver")

import pytest
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, engine
from app.ontology.loader import load_all
from app.ontology.permissions import UserContext
from app.ontology.registry import Registry

# DB ─────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def db_session():
    """Session limpa por teste. Tambem limpa cache de grants entre testes."""
    # Limpa cache de markings entre testes (TTL pode persistir grants antigos)
    try:
        from app.ontology.permissions import invalidate_grant_cache

        invalidate_grant_cache(None)
    except Exception:
        pass

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Registry ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def loaded_registry() -> Registry:
    reg = Registry()
    load_all(reg)
    return reg


# UserContexts ───────────────────────────────────────────────────────────────


@pytest.fixture()
def admin_user_ctx() -> UserContext:
    return UserContext(
        user_id=1,
        role="admin",
        company_ids=[1, 2],
        markings_granted=["*"],
    )


@pytest.fixture()
def tenant_user_ctx_factory():
    """Factory que cria UserContext para tenants especificos."""

    def _make(
        user_id=100,
        role="user",
        company_ids=None,
        markings=None,
    ) -> UserContext:
        # IMPORTANTE: distinguir None (= default [1]) de [] (= sem nenhuma empresa)
        if company_ids is None:
            company_ids = [1]
        return UserContext(
            user_id=user_id,
            role=role,
            company_ids=company_ids,
            markings_granted=markings or [],
        )

    return _make


# Seed data ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def seed_data(db_session):
    """Popula: 2 Companies, 5 Products (3 c1 + 2 c2), 2 SalesOrders em c1."""
    c1 = models.Company(id=1, name="Empresa Alpha", sector="industrial", revenue_year=10_000_000)
    c2 = models.Company(id=2, name="Empresa Beta", sector="servicos", revenue_year=2_500_000)
    db_session.add_all([c1, c2])
    db_session.flush()

    products_c1 = [
        models.Product(
            id=10,
            company_id=1,
            name="Widget Pro",
            category="produto-acabado",
            standard_cost=100.0,
            sale_price=180.0,
            stock_quantity=50,
            min_stock=20,
        ),
        models.Product(
            id=11,
            company_id=1,
            name="Gadget Mk2",
            category="produto-acabado",
            standard_cost=200.0,
            sale_price=350.0,
            stock_quantity=10,
            min_stock=15,
        ),
        models.Product(
            id=12,
            company_id=1,
            name="Material X",
            category="materia-prima",
            standard_cost=50.0,
            sale_price=0.0,
            stock_quantity=500,
            min_stock=100,
        ),
    ]
    products_c2 = [
        models.Product(
            id=20,
            company_id=2,
            name="Servico Plus",
            category="servico",
            standard_cost=300.0,
            sale_price=800.0,
            stock_quantity=0,
            min_stock=0,
        ),
        models.Product(
            id=21,
            company_id=2,
            name="Servico Lite",
            category="servico",
            standard_cost=100.0,
            sale_price=250.0,
            stock_quantity=0,
            min_stock=0,
        ),
    ]
    db_session.add_all(products_c1 + products_c2)
    db_session.flush()

    orders = [
        models.SalesOrder(
            id=100,
            company_id=1,
            customer_id=None,
            product_id=10,
            revenue=1800.0,
            discount=100.0,
            total=1700.0,
        ),
        models.SalesOrder(
            id=101,
            company_id=1,
            customer_id=None,
            product_id=11,
            revenue=3500.0,
            discount=0.0,
            total=3500.0,
        ),
    ]
    db_session.add_all(orders)
    db_session.commit()

    return {
        "company_ids": [1, 2],
        "product_ids_c1": [10, 11, 12],
        "product_ids_c2": [20, 21],
        "order_ids_c1": [100, 101],
    }
