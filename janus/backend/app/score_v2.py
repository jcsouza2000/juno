"""
JUNO Score v2.0 â€” Ãndice Composto de SaÃºde Empresarial

FÃ³rmula:
    Score = w1*Margem + w2*Liquidez + w3*Endividamento +
            w4*EficiÃªncia_ProduÃ§Ã£o + w5*Qualidade_Dados +
            w6*Sazonalidade + w7*ConcentraÃ§Ã£o_Clientes

Onde:
    w1-w7 = pesos calibrados por setor (soma = 1.0)
    Cada componente normalizado 0-100

Setores suportados:
    - manufatura_encomenda (bens de capital)
    - manufatura_seriada (implementos, componentes)
    - metalurgia
    - quimica
    - textil
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy import case, desc, extract, func
from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.core.i18n import tr, tr_component
from app.database import get_db
from app.models import (
    Company,
    Customer,
    FinancialStatement,
    Product,
    ProductionOrder,
    SalesOrder,
    ScoreHistory,
)

OPEN_PRODUCTION_STATUSES = {
    "aberto",
    "aberta",
    "planned",
    "planejada",
    "em_andamento",
    "em andamento",
}

# ============================================================
# CONFIGURAÃ‡Ã•ES DE PESOS POR SETOR
# ============================================================

SECTOR_WEIGHTS = {
    "manufatura_encomenda": {
        "margin": 0.25,
        "liquidity": 0.15,
        "debt": 0.15,
        "production": 0.20,
        "data_quality": 0.10,
        "seasonality": 0.10,
        "customer_concentration": 0.05,
    },
    "manufatura_seriada": {
        "margin": 0.20,
        "liquidity": 0.15,
        "debt": 0.15,
        "production": 0.25,
        "data_quality": 0.10,
        "seasonality": 0.10,
        "customer_concentration": 0.05,
    },
    "default": {
        "margin": 0.20,
        "liquidity": 0.20,
        "debt": 0.20,
        "production": 0.15,
        "data_quality": 0.15,
        "seasonality": 0.05,
        "customer_concentration": 0.05,
    },
}


def _line_text(value: str) -> str:
    return (value or "").lower().replace("_", " ")


# ============================================================
# DATACLASS DE RESULTADO
# ============================================================


@dataclass
class ScoreComponent:
    name: str
    weight: float
    raw_value: float
    normalized_score: float
    weighted_score: float
    details: dict


@dataclass
class JunoScoreResult:
    company_id: int
    company_name: str
    overall_score: float
    components: list[ScoreComponent]
    trend: str  # improving, stable, declining
    trend_delta: float
    calculation_date: datetime
    recommendations: list[str]


# ============================================================
# CALCULADORA DE SCORE
# ============================================================


class JunoScoreCalculator:
    """
    Calculadora do Score JUNO v2.0.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_weights(self, sector: str) -> dict[str, float]:
        """Retorna pesos calibrados para o setor."""
        return SECTOR_WEIGHTS.get(sector, SECTOR_WEIGHTS["default"])

    # ============================================================
    # COMPONENTES INDIVIDUAIS
    # ============================================================

    def calculate_margin_score(self, company_id: int) -> tuple[float, dict]:
        """
        Score de Margem (0-100).
        Baseado em: margem bruta, margem lÃ­quida, produtos com margem negativa.
        """
        products = self.db.query(Product).filter(Product.company_id == company_id).all()

        if not products:
            return 50, {"error": "Sem produtos cadastrados"}

        total_products = len(products)
        negative_margin = 0
        total_margin_pct = 0.0
        margin_details: list[dict] = []

        for p in products:
            if p.sale_price > 0:
                margin = (p.sale_price - p.standard_cost) / p.sale_price * 100
                total_margin_pct += margin

                if margin < 0:
                    negative_margin += 1

                margin_details.append(
                    {
                        "product": p.name,
                        "margin_pct": round(margin, 2),
                        "status": "negativa" if margin < 0 else "positiva",
                    }
                )

        avg_margin = total_margin_pct / total_products if total_products > 0 else 0

        # Normalizar: margem mÃ©dia 30% = 100 pontos
        # Cada produto negativo penaliza 15 pontos
        base_score = min(100, max(0, avg_margin * 3.33))  # 30% * 3.33 â‰ˆ 100
        penalty = negative_margin * 15

        score = max(0, base_score - penalty)

        details = {
            "avg_margin_pct": round(avg_margin, 2),
            "total_products": total_products,
            "negative_margin_products": negative_margin,
            "base_score": round(base_score, 2),
            "penalty": penalty,
            "product_details": margin_details[:5],  # Top 5
        }

        return score, details

    def calculate_liquidity_score(self, company_id: int) -> tuple[float, dict]:
        """
        Score de Liquidez (0-100).
        Baseado em: liquidez corrente, liquidez seca, capital de giro.
        """
        # Buscar dados do balanÃ§o
        balance = (
            self.db.query(FinancialStatement)
            .filter(
                FinancialStatement.company_id == company_id,
                FinancialStatement.statement_type.in_(("BALANCO", "Balanco", "balanco")),
            )
            .all()
        )

        if not balance:
            return 50, {"error": "Sem dados de balanÃ§o. FaÃ§a upload em /financials"}

        # Calcular liquidez corrente (Ativo Circulante / Passivo Circulante)
        # SimplificaÃ§Ã£o: buscar contas relevantes
        ativo_circulante = sum(
            [b.value for b in balance if "ativo circulante" in _line_text(b.line_item)]
        )
        passivo_circulante = sum(
            [
                b.value
                for b in balance
                if "passivo circulante" in _line_text(b.line_item)
                and "nao circulante" not in _line_text(b.line_item)
                and "não circulante" not in _line_text(b.line_item)
            ]
        )

        if passivo_circulante > 0:
            liquidez_corrente = ativo_circulante / passivo_circulante
        else:
            liquidez_corrente = 0

        # Normalizar: LC 2.0 = 100 pontos, LC 1.0 = 50 pontos, LC < 0.5 = 0
        if liquidez_corrente >= 2.0:
            score = 100.0
        elif liquidez_corrente >= 1.0:
            score = 50 + (liquidez_corrente - 1.0) * 50
        else:
            score = max(0, liquidez_corrente * 100)

        details = {
            "liquidez_corrente": round(liquidez_corrente, 2),
            "ativo_circulante": ativo_circulante,
            "passivo_circulante": passivo_circulante,
            "interpretation": (
                "Excelente"
                if score > 80
                else "Bom" if score > 60 else "AtenÃ§Ã£o" if score > 40 else "CrÃ­tico"
            ),
        }

        return score, details

    def calculate_debt_score(self, company_id: int) -> tuple[float, dict]:
        """
        Score de Endividamento (0-100).
        Menor endividamento = maior score.
        """
        balance = (
            self.db.query(FinancialStatement)
            .filter(
                FinancialStatement.company_id == company_id,
                FinancialStatement.statement_type.in_(("BALANCO", "Balanco", "balanco")),
            )
            .all()
        )

        if not balance:
            return 50, {"error": "Sem dados de balanÃ§o"}

        # Endividamento = (PC + PNC) / (PC + PNC + PL)
        pc = sum(
            [
                b.value
                for b in balance
                if "passivo circulante" in _line_text(b.line_item)
                and "nao circulante" not in _line_text(b.line_item)
                and "não circulante" not in _line_text(b.line_item)
            ]
        )
        pnc = sum(
            [
                b.value
                for b in balance
                if "passivo nao circulante" in _line_text(b.line_item)
                or "passivo não circulante" in _line_text(b.line_item)
            ]
        )
        pl = sum(
            [
                b.value
                for b in balance
                if "patrimonio liquido" in _line_text(b.line_item)
                or "patrimônio líquido" in _line_text(b.line_item)
            ]
        )

        total_passivo = pc + pnc

        if total_passivo + pl > 0:
            endividamento = total_passivo / (total_passivo + pl) * 100
        else:
            endividamento = 0

        # Inverter: 0% endividamento = 100 pontos, 100% = 0 pontos
        score = max(0, 100 - endividamento)

        details = {
            "endividamento_pct": round(endividamento, 2),
            "passivo_circulante": pc,
            "passivo_nao_circulante": pnc,
            "patrimonio_liquido": pl,
            "interpretation": (
                "Excelente"
                if score > 80
                else "Bom" if score > 60 else "AtenÃ§Ã£o" if score > 40 else "CrÃ­tico"
            ),
        }

        return score, details

    def calculate_production_score(self, company_id: int) -> tuple[float, dict]:
        """
        Score de EficiÃªncia de ProduÃ§Ã£o (0-100).
        Baseado em: atrasos, estouro de custo, qualidade.
        """
        # Agregacao em SQL (antes carregava todas as ordens no ORM e iterava em
        # Python — ~78k linhas levavam ~3s). today vira limite de datetime: a
        # logica original comparava planned_date.date() < today.
        today_start = datetime.combine(utcnow_naive().date(), datetime.min.time())
        open_status = func.lower(func.trim(func.coalesce(ProductionOrder.status, ""))).in_(
            OPEN_PRODUCTION_STATUSES
        )
        delayed_case = case(
            (
                (
                    (ProductionOrder.actual_date.isnot(None))
                    & (ProductionOrder.planned_date.isnot(None))
                    & (ProductionOrder.actual_date > ProductionOrder.planned_date)
                )
                | (
                    (ProductionOrder.actual_date.is_(None))
                    & (ProductionOrder.planned_date.isnot(None))
                    & (ProductionOrder.planned_date < today_start)
                    & open_status
                ),
                1,
            ),
            else_=0,
        )
        overrun_case = case(
            (
                (ProductionOrder.planned_cost.isnot(None))
                & (ProductionOrder.planned_cost != 0)
                & (ProductionOrder.actual_cost.isnot(None))
                & (ProductionOrder.actual_cost != 0)
                & (ProductionOrder.actual_cost > ProductionOrder.planned_cost * 1.1),
                1,
            ),
            else_=0,
        )
        agg = (
            self.db.query(
                func.count(ProductionOrder.id),
                func.coalesce(func.sum(delayed_case), 0),
                func.coalesce(func.sum(overrun_case), 0),
            )
            .filter(ProductionOrder.company_id == company_id)
            .one()
        )
        total_orders = int(agg[0] or 0)

        if total_orders == 0:
            return 50, {"error": "Sem ordens de produÃ§Ã£o"}

        delayed_orders = int(agg[1] or 0)
        cost_overruns = int(agg[2] or 0)

        # Atrasos: 0% = 100 pontos, >30% = 0 pontos
        delay_rate = delayed_orders / total_orders if total_orders > 0 else 0
        delay_score = max(0, 100 - delay_rate * 333)  # 30% atraso = 0 pontos

        # Estouro de custo: 0% = 100 pontos, >50% = 0 pontos
        overrun_rate = cost_overruns / total_orders if total_orders > 0 else 0
        cost_score = max(0, 100 - overrun_rate * 200)  # 50% estouro = 0 pontos

        # MÃ©dia ponderada
        score = (delay_score * 0.6) + (cost_score * 0.4)

        details = {
            "total_orders": total_orders,
            "delayed_orders": delayed_orders,
            "delay_rate_pct": round(delay_rate * 100, 2),
            "cost_overruns": cost_overruns,
            "overrun_rate_pct": round(overrun_rate * 100, 2),
            "delay_score": round(delay_score, 2),
            "cost_score": round(cost_score, 2),
        }

        return score, details

    def calculate_data_quality_score(self, company_id: int) -> tuple[float, dict]:
        """
        Score de Qualidade dos Dados (0-100).
        Baseado em: completude, consistÃªncia, atualidade.
        """
        # Verificar completude das tabelas principais
        checks: list[dict[str, float | int | str]] = []

        # Counts agregados em SQL (antes materializava products + production_orders
        # no ORM e contava em Python).
        # Produtos
        prod_complete_case = case(
            ((Product.standard_cost > 0) & (Product.sale_price > 0), 1), else_=0
        )
        prod_agg = (
            self.db.query(
                func.count(Product.id),
                func.coalesce(func.sum(prod_complete_case), 0),
            )
            .filter(Product.company_id == company_id)
            .one()
        )
        products_total = int(prod_agg[0] or 0)
        products_complete = int(prod_agg[1] or 0)
        checks.append(
            {
                "table": "products",
                "complete": products_complete,
                "total": products_total,
                "rate": products_complete / products_total if products_total > 0 else 0,
            }
        )

        # Clientes
        customers_total = (
            self.db.query(func.count(Customer.id))
            .filter(Customer.company_id == company_id)
            .scalar()
            or 0
        )
        checks.append(
            {
                "table": "customers",
                "complete": customers_total,
                "total": max(customers_total, 10),
                "rate": min(1.0, customers_total / 10),
            }
        )

        # Ordens de produÃ§Ã£o
        with_dates_case = case(
            (
                (ProductionOrder.planned_date.isnot(None))
                & (ProductionOrder.actual_date.isnot(None)),
                1,
            ),
            else_=0,
        )
        po_agg = (
            self.db.query(
                func.count(ProductionOrder.id),
                func.coalesce(func.sum(with_dates_case), 0),
            )
            .filter(ProductionOrder.company_id == company_id)
            .one()
        )
        po_total = int(po_agg[0] or 0)
        orders_with_dates = int(po_agg[1] or 0)
        checks.append(
            {
                "table": "production_orders",
                "complete": orders_with_dates,
                "total": po_total,
                "rate": orders_with_dates / po_total if po_total > 0 else 0,
            }
        )

        # Calcular score mÃ©dio
        avg_rate = sum(float(c["rate"]) for c in checks) / len(checks) if checks else 0
        score = avg_rate * 100

        details = {
            "checks": checks,
            "avg_completeness": round(avg_rate * 100, 2),
            "interpretation": (
                "Excelente"
                if score > 90
                else "Bom" if score > 70 else "Regular" if score > 50 else "CrÃ­tico"
            ),
        }

        return score, details

    def calculate_seasonality_score(self, company_id: int) -> tuple[float, dict]:
        """
        Score de Sazonalidade (0-100).
        Analisa variaÃ§Ã£o de vendas ao longo do ano.
        """
        # GROUP BY mes em SQL (antes carregava todos os pedidos no ORM —
        # ~117k linhas levavam ~5s). Agrega por numero do mes (1-12) somando
        # receita liquida (revenue - discount), ignorando pedidos sem data.
        any_sales = self.db.query(SalesOrder.id).filter(SalesOrder.company_id == company_id).first()
        if any_sales is None:
            return 50, {"error": "Sem pedidos de venda"}

        month_col = extract("month", SalesOrder.order_date)
        rows = (
            self.db.query(
                month_col.label("month"),
                func.sum(
                    func.coalesce(SalesOrder.revenue, 0) - func.coalesce(SalesOrder.discount, 0)
                ).label("revenue"),
            )
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.order_date.isnot(None),
            )
            .group_by(month_col)
            .all()
        )
        monthly_revenue: dict[int, float] = {int(r.month): float(r.revenue or 0) for r in rows}

        if not monthly_revenue:
            return 50, {"error": "Sem datas nos pedidos"}

        values = list(monthly_revenue.values())
        avg_revenue = sum(values) / len(values)

        # Coeficiente de variaÃ§Ã£o (CV)
        if avg_revenue > 0 and len(values) > 1:
            variance = sum([(v - avg_revenue) ** 2 for v in values]) / len(values)
            std_dev = variance**0.5
            cv = std_dev / avg_revenue
        else:
            cv = 0

        # CV baixo = sazonalidade bem gerenciada = score alto
        # CV < 0.2 = excelente (100 pontos), CV > 1.0 = crÃ­tico (0 pontos)
        score = max(0, 100 - cv * 100)

        details = {
            "monthly_revenue": {k: round(v, 2) for k, v in monthly_revenue.items()},
            "avg_monthly_revenue": round(avg_revenue, 2),
            "coefficient_variation": round(cv, 2),
            "interpretation": (
                "Bem gerenciada" if score > 70 else "Moderada" if score > 40 else "Alta variaÃ§Ã£o"
            ),
        }

        return score, details

    def calculate_customer_concentration_score(self, company_id: int) -> tuple[float, dict]:
        """
        Score de ConcentraÃ§Ã£o de Clientes (0-100).
        Menor concentraÃ§Ã£o = maior score (diversificaÃ§Ã£o Ã© saudÃ¡vel).
        """
        # GROUP BY cliente em SQL (antes carregava todos os pedidos no ORM —
        # ~117k linhas levavam ~5s). Mantem o agrupamento por customer_id
        # (inclusive NULL como um grupo, como no comportamento original).
        rows = (
            self.db.query(
                SalesOrder.customer_id.label("customer_id"),
                func.sum(
                    func.coalesce(SalesOrder.revenue, 0) - func.coalesce(SalesOrder.discount, 0)
                ).label("revenue"),
            )
            .filter(SalesOrder.company_id == company_id)
            .group_by(SalesOrder.customer_id)
            .all()
        )

        if not rows:
            return 50, {"error": "Sem pedidos"}

        # Receita por cliente
        customer_revenue: dict[int, float] = {r.customer_id: float(r.revenue or 0) for r in rows}

        total_revenue = sum(customer_revenue.values())

        if total_revenue == 0:
            return 50, {"error": "Sem receita"}

        # Ãndice HHI (Herfindahl-Hirschman)
        hhi = sum([(rev / total_revenue) ** 2 for rev in customer_revenue.values()])

        # HHI = 1 (monopÃ³lio) = 0 pontos, HHI = 0.1 (10 clientes iguais) = 100 pontos
        score = max(0, 100 - hhi * 100)

        # Top 3 clientes
        sorted_customers = sorted(customer_revenue.items(), key=lambda x: x[1], reverse=True)[:3]
        top3_share = sum([v for _, v in sorted_customers]) / total_revenue * 100

        details = {
            "total_customers": len(customer_revenue),
            "hhi_index": round(hhi, 4),
            "top3_share_pct": round(top3_share, 2),
            "interpretation": (
                "Bem diversificado"
                if score > 70
                else "Moderado" if score > 40 else "Alta concentraÃ§Ã£o"
            ),
        }

        return score, details

    # ============================================================
    # CÃLCULO COMPLETO
    # ============================================================

    def calculate_full_score(
        self, company_id: int, persist: bool = True, lang: str = "pt"
    ) -> JunoScoreResult:
        """
        Calcula o Score JUNO completo com todos os componentes.
        """
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError(f"Empresa {company_id} nÃ£o encontrada")

        # Detectar setor
        sector = self._detect_sector(company.sector)
        weights = self.get_weights(sector)

        # Calcular componentes
        components = []

        # 1. Margem
        margin_score, margin_details = self.calculate_margin_score(company_id)
        components.append(
            ScoreComponent(
                name="Margem",
                weight=weights["margin"],
                raw_value=margin_details.get("avg_margin_pct", 0),
                normalized_score=margin_score,
                weighted_score=margin_score * weights["margin"],
                details=margin_details,
            )
        )

        # 2. Liquidez
        liquidity_score, liquidity_details = self.calculate_liquidity_score(company_id)
        components.append(
            ScoreComponent(
                name="Liquidez",
                weight=weights["liquidity"],
                raw_value=liquidity_details.get("liquidez_corrente", 0),
                normalized_score=liquidity_score,
                weighted_score=liquidity_score * weights["liquidity"],
                details=liquidity_details,
            )
        )

        # 3. Endividamento
        debt_score, debt_details = self.calculate_debt_score(company_id)
        components.append(
            ScoreComponent(
                name="Endividamento",
                weight=weights["debt"],
                raw_value=debt_details.get("endividamento_pct", 0),
                normalized_score=debt_score,
                weighted_score=debt_score * weights["debt"],
                details=debt_details,
            )
        )

        # 4. ProduÃ§Ã£o
        production_score, production_details = self.calculate_production_score(company_id)
        components.append(
            ScoreComponent(
                name="ProduÃ§Ã£o",
                weight=weights["production"],
                raw_value=production_details.get("delay_rate_pct", 0),
                normalized_score=production_score,
                weighted_score=production_score * weights["production"],
                details=production_details,
            )
        )

        # 5. Qualidade de Dados
        data_score, data_details = self.calculate_data_quality_score(company_id)
        components.append(
            ScoreComponent(
                name="Qualidade de Dados",
                weight=weights["data_quality"],
                raw_value=data_details.get("avg_completeness", 0),
                normalized_score=data_score,
                weighted_score=data_score * weights["data_quality"],
                details=data_details,
            )
        )

        # 6. Sazonalidade
        season_score, season_details = self.calculate_seasonality_score(company_id)
        components.append(
            ScoreComponent(
                name="Sazonalidade",
                weight=weights["seasonality"],
                raw_value=season_details.get("coefficient_variation", 0),
                normalized_score=season_score,
                weighted_score=season_score * weights["seasonality"],
                details=season_details,
            )
        )

        # 7. ConcentraÃ§Ã£o de Clientes
        concentration_score, concentration_details = self.calculate_customer_concentration_score(
            company_id
        )
        components.append(
            ScoreComponent(
                name="ConcentraÃ§Ã£o de Clientes",
                weight=weights["customer_concentration"],
                raw_value=concentration_details.get("hhi_index", 0),
                normalized_score=concentration_score,
                weighted_score=concentration_score * weights["customer_concentration"],
                details=concentration_details,
            )
        )

        # Calcular score final
        overall_score = sum([c.weighted_score for c in components])

        # Determinar tendÃªncia (comparar com Ãºltimo score)
        trend, trend_delta = self._calculate_trend(company_id, overall_score)

        # Gerar recomendaÃ§Ãµes
        recommendations = self._generate_recommendations(components, lang)

        # Salvar no histÃ³rico
        if persist:
            self._save_score_history(company_id, overall_score, components)

        return JunoScoreResult(
            company_id=company_id,
            company_name=company.name,
            overall_score=round(overall_score, 2),
            components=components,
            trend=trend,
            trend_delta=round(trend_delta, 2),
            calculation_date=utcnow_naive(),
            recommendations=recommendations,
        )

    def _detect_sector(self, sector_description: str) -> str:
        """Detecta setor a partir da descriÃ§Ã£o."""
        sector_lower = (sector_description or "").lower()
        if "encomenda" in sector_lower or "capital" in sector_lower:
            return "manufatura_encomenda"
        elif "seriada" in sector_lower or "implemento" in sector_lower:
            return "manufatura_seriada"
        return "default"

    def _calculate_trend(self, company_id: int, current_score: float) -> tuple[str, float]:
        """Compara com Ãºltimo score calculado."""
        last_score = (
            self.db.query(ScoreHistory)
            .filter(ScoreHistory.company_id == company_id)
            .order_by(desc(ScoreHistory.score_date))
            .first()
        )

        if not last_score:
            return "stable", 0

        delta = current_score - last_score.overall_score

        if delta > 5:
            return "improving", delta
        elif delta < -5:
            return "declining", delta
        return "stable", delta

    def _save_score_history(
        self, company_id: int, overall: float, components: list[ScoreComponent]
    ):
        """Salva cÃ¡lculo no histÃ³rico."""
        history = ScoreHistory(
            company_id=company_id,
            score_date=utcnow_naive(),
            overall_score=overall,
            margin_score=next((c.normalized_score for c in components if c.name == "Margem"), 0),
            liquidity_score=next(
                (c.normalized_score for c in components if c.name == "Liquidez"), 0
            ),
            debt_score=next(
                (c.normalized_score for c in components if c.name == "Endividamento"), 0
            ),
            production_score=next(
                (c.normalized_score for c in components if c.name == "ProduÃ§Ã£o"), 0
            ),
            data_quality_score=next(
                (c.normalized_score for c in components if c.name == "Qualidade de Dados"), 0
            ),
        )
        self.db.add(history)
        self.db.commit()

    def _generate_recommendations(
        self, components: list[ScoreComponent], lang: str = "pt"
    ) -> list[str]:
        """Gera recomendacoes (i18n) baseadas nos componentes mais fracos.

        O emoji prefixo (mantido) e usado pelo pdf_service para escolher o
        estilo do paragrafo; so o texto e traduzido.
        """
        recommendations = []

        # Ordenar por score (menores primeiro)
        sorted_components = sorted(components, key=lambda c: c.normalized_score)

        for comp in sorted_components[:3]:  # Top 3 problemas
            name = tr_component(comp.name, lang)
            score = f"{comp.normalized_score:.0f}"
            if comp.normalized_score < 40:
                recommendations.append("🔴 " + tr("score.critical", lang, name=name, score=score))
            elif comp.normalized_score < 60:
                recommendations.append("🟡 " + tr("score.attention", lang, name=name, score=score))
            elif comp.normalized_score < 75:
                recommendations.append("🟢 " + tr("score.regular", lang, name=name, score=score))

        if not recommendations:
            recommendations.append("✅ " + tr("score.healthy", lang))

        return recommendations

    def get_score_history(self, company_id: int, days: int = 90) -> list[dict]:
        """Retorna histÃ³rico de scores para grÃ¡ficos."""
        since = utcnow_naive() - timedelta(days=days)

        history = (
            self.db.query(ScoreHistory)
            .filter(ScoreHistory.company_id == company_id, ScoreHistory.score_date >= since)
            .order_by(ScoreHistory.score_date)
            .all()
        )

        return [
            {
                "date": h.score_date.isoformat(),
                "overall": h.overall_score,
                "margin": h.margin_score,
                "liquidity": h.liquidity_score,
                "debt": h.debt_score,
                "production": h.production_score,
                "data_quality": h.data_quality_score,
            }
            for h in history
        ]


def get_score_calculator(db: Session = Depends(get_db)) -> JunoScoreCalculator:
    """Factory para injeÃ§Ã£o de dependÃªncia."""
    return JunoScoreCalculator(db)
