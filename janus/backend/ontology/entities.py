from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Produto:
    id: int
    nome: str
    custo_padrao: float
    preco_venda: float

    @property
    def margem(self) -> float:
        return float(self.preco_venda) - float(self.custo_padrao)


@dataclass
class Ordem:
    id: int
    produto_id: int
    data_planejada: Optional[date]
    data_real: Optional[date]

    @property
    def atraso_dias(self) -> int:
        if not self.data_real or not self.data_planejada:
            return 0
        return max(0, (self.data_real - self.data_planejada).days)


@dataclass
class Empresa:
    id: int
    nome: str
