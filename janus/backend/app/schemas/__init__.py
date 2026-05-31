"""
Schemas Pydantic — separados dos models SQLAlchemy (app.models).

Estrutura:
- `auth.py`: schemas relacionados a autenticação (LoginResponse, UserOut, etc.)
- `common.py`: schemas reutilizáveis (envelope de paginação, erro genérico).

Regra: nunca retorne um model SQLAlchemy diretamente em um endpoint.
Sempre converta para um schema Pydantic com `from_attributes=True`.
Isso evita vazar campos sensíveis (hashed_password, tokens internos, etc.)
e permite versionar a API independente do schema do banco.
"""
