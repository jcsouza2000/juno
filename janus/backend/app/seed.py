"""
JUNO Seed - Idempotente e Seguro
Nunca duplica dados. Usa UPSERT do PostgreSQL.

NOTA: Este e um SCRIPT CLI standalone (rodado via `python -m app.seed`).
Os `print()` aqui sao INTENCIONAIS -- feedback para o operador rodando
o seed. Nao substituir por logger.
"""

import json
import os

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .database import SessionLocal

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "demo")


def load_json(filename: str) -> list:
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Arquivo nao encontrado: {filepath}")
        return []
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def seed_companies(db):
    companies = load_json("companies.json")
    if not companies:
        return

    for company in companies:
        db.execute(
            text(
                """
                INSERT INTO companies (id, name, sector, revenue_year)
                VALUES (:id, :name, :sector, :revenue_year)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    sector = EXCLUDED.sector,
                    revenue_year = EXCLUDED.revenue_year
                """
            ),
            company,
        )
    db.commit()
    print(f"Companies: {len(companies)} registros (upsert)")


def seed_products_a(db):
    products = load_json("products_a.json")
    if not products:
        return

    for product in products:
        try:
            db.execute(
                text(
                    """
                    INSERT INTO products (company_id, name, category, standard_cost, sale_price)
                    VALUES (1, :name, :category, :standard_cost, :sale_price)
                    ON CONFLICT (company_id, name) DO UPDATE SET
                        category = EXCLUDED.category,
                        standard_cost = EXCLUDED.standard_cost,
                        sale_price = EXCLUDED.sale_price
                    """
                ),
                product,
            )
        except OperationalError as exc:
            if "ON CONFLICT clause does not match" not in str(exc):
                raise

            existing = db.execute(
                text(
                    """
                    SELECT id FROM products
                    WHERE company_id = 1 AND name = :name
                    LIMIT 1
                    """
                ),
                {"name": product["name"]},
            ).fetchone()

            if existing:
                db.execute(
                    text(
                        """
                        UPDATE products
                        SET category = :category,
                            standard_cost = :standard_cost,
                            sale_price = :sale_price
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": existing[0],
                        "category": product["category"],
                        "standard_cost": product["standard_cost"],
                        "sale_price": product["sale_price"],
                    },
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO products (company_id, name, category, standard_cost, sale_price)
                        VALUES (1, :name, :category, :standard_cost, :sale_price)
                        """
                    ),
                    product,
                )
    db.commit()
    print(f"Products A: {len(products)} registros (upsert)")


def run_seed():
    print("JUNO Seed - Iniciando...")
    db = SessionLocal()
    try:
        seed_companies(db)
        seed_products_a(db)
        print("Seed concluido com sucesso")
    except Exception as e:
        db.rollback()
        print(f"Erro no seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
