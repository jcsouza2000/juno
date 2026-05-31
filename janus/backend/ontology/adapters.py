from app.models import Company, Product, ProductionOrder

from .entities import Empresa, Ordem, Produto


def produto_from_db(db_product: Product) -> Produto:
    return Produto(
        id=db_product.id,
        nome=db_product.name,
        custo_padrao=float(db_product.standard_cost or 0),
        preco_venda=float(db_product.sale_price or 0),
    )


def ordem_from_db(db_order: ProductionOrder) -> Ordem:
    return Ordem(
        id=db_order.id,
        produto_id=db_order.product_id,
        data_planejada=db_order.planned_date,
        data_real=db_order.actual_date,
    )


def empresa_from_db(db_company: Company) -> Empresa:
    return Empresa(
        id=db_company.id,
        nome=db_company.name,
    )
