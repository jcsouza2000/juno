"""Testes de Snapshots e Time-travel."""

from __future__ import annotations

import pytest

from app.ontology.snapshots import (
    SnapshotError,
    create_snapshot,
    diff_snapshots,
    fetch_at,
    list_at,
    list_snapshots,
)


class TestCreate:
    def test_creates_with_payload(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        snap = create_snapshot(
            "antes-do-reajuste",
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            company_id=1,
        )
        assert snap["row_count"] == 3
        assert snap["object_type"] == "Produto"
        assert snap["name"] == "antes-do-reajuste"

    def test_invalid_name_raises(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        with pytest.raises(SnapshotError):
            create_snapshot(
                "", "Produto", user=admin_user_ctx, db=db_session, registry=loaded_registry
            )


class TestTimeTravel:
    def test_fetch_at_returns_old_state(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        tenant_user_ctx_factory,
        seed_data,
    ):
        # 1. Cria snapshot do estado original
        snap = create_snapshot(
            "antes",
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            company_id=1,
        )
        # 2. Muda o produto via Action
        from app.ontology import runtime

        user_c = tenant_user_ctx_factory(
            role="gerente_comercial",
            company_ids=[1],
            markings=["ConfidencialComercial"],
        )
        runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 300.0, "motivo": "reajuste"},
            user=user_c,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()

        # 3. Estado atual: 300
        current = runtime.fetch_by_id(
            "Produto", 10, user=admin_user_ctx, db=db_session, registry=loaded_registry
        )
        assert current["sale_price"] == 300.0

        # 4. Time-travel: snapshot ainda mostra 180
        past = fetch_at(snap["id"], 10, db=db_session)
        assert past is not None
        assert past["sale_price"] == 180.0

    def test_list_at(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        snap = create_snapshot(
            "baseline",
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            company_id=1,
        )
        result = list_at(snap["id"], db=db_session)
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_list_snapshots(self, db_session, loaded_registry, admin_user_ctx, seed_data):
        create_snapshot(
            "s1",
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            company_id=1,
        )
        create_snapshot(
            "s2",
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            company_id=1,
        )
        rows = list_snapshots(db_session, object_type="Produto")
        names = [r["name"] for r in rows]
        assert "s1" in names and "s2" in names

    def test_fetch_unknown_snapshot_raises(self, db_session):
        with pytest.raises(SnapshotError):
            fetch_at(99999, 10, db=db_session)

    def test_diff_detects_changes(
        self,
        db_session,
        loaded_registry,
        admin_user_ctx,
        tenant_user_ctx_factory,
        seed_data,
    ):
        from app.ontology import runtime

        # Snapshot inicial
        a = create_snapshot(
            "A",
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            company_id=1,
        )

        # Muda
        user_c = tenant_user_ctx_factory(
            role="gerente_comercial", company_ids=[1], markings=["ConfidencialComercial"]
        )
        runtime.execute_action(
            "atualizarPreco",
            10,
            {"novo_preco": 250.0, "motivo": "x"},
            user=user_c,
            db=db_session,
            registry=loaded_registry,
        )
        db_session.commit()

        # Segundo snapshot
        b = create_snapshot(
            "B",
            "Produto",
            user=admin_user_ctx,
            db=db_session,
            registry=loaded_registry,
            company_id=1,
        )

        d = diff_snapshots(a["id"], b["id"], db=db_session)
        assert d["summary"]["changed"] >= 1
        assert 10 in d["changed"]
        assert d["changed"][10]["sale_price"]["before"] == 180.0
        assert d["changed"][10]["sale_price"]["after"] == 250.0
