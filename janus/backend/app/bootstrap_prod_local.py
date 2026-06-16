"""Bootstrap minimo para stack Docker prod local: empresa + admin."""

from __future__ import annotations

from sqlalchemy import text

from app.auth import get_password_hash
from app.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO companies (id, name, sector, revenue_year)
                VALUES (1, 'Minha Empresa', 'Piloto', 45000000)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    sector = EXCLUDED.sector,
                    revenue_year = EXCLUDED.revenue_year
                """
            )
        )

        email = "admin@juno.local"
        password_hash = get_password_hash("Admin123!")
        db.execute(
            text(
                """
                INSERT INTO users (email, full_name, hashed_password, role, is_active)
                VALUES (:email, 'Admin Piloto', :pwd, 'admin', true)
                ON CONFLICT (email) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    hashed_password = EXCLUDED.hashed_password,
                    role = EXCLUDED.role,
                    is_active = true
                """
            ),
            {"email": email, "pwd": password_hash},
        )
        user_id = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        ).scalar_one()

        db.execute(
            text(
                """
                INSERT INTO user_company_memberships (user_id, company_id, role_in_tenant, is_primary)
                SELECT :uid, 1, 'owner', true
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_company_memberships
                    WHERE user_id = :uid AND company_id = 1
                )
                """
            ),
            {"uid": user_id},
        )
        db.commit()
        print(f"Bootstrap OK: admin={email} company_id=1")
    finally:
        db.close()


if __name__ == "__main__":
    main()
