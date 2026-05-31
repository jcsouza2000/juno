"""
schema.py — Pydantic models que validam o YAML da ontologia.

Toda definição em `definitions/*.yaml` é parseada e validada contra estes modelos.
Erros de schema explodem no startup do app (fail-fast).

TODO(sem1): implementar validadores cruzados (ex: links apontam para ObjectType existente)
TODO(sem1): suporte a referências externas ($ref) entre YAMLs
TODO(sem2): validar que `backing.model` resolve via importlib
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Metadados comuns (estilo k8s CRD)
# =============================================================================


class Metadata(BaseModel):
    """Metadados de qualquer recurso da ontologia."""

    name: str = Field(..., description="Nome único do recurso (PascalCase para tipos)")
    description: str | None = None
    owner: str | None = Field(None, description="Time/squad responsável")
    tags: list[str] = Field(default_factory=list)


class ResourceBase(BaseModel):
    """Base para Object/Action/Function/Marking."""

    apiVersion: Literal["ontology.juno.gravithy.com.br/v1"]
    kind: str
    metadata: Metadata


# =============================================================================
# Property Types
# =============================================================================


class PropertyType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    MONEY = "money"
    PERCENT = "percent"
    ENUM = "enum"
    REF = "ref"
    ARRAY = "array"
    # Custom (extensível via plugins)
    CNPJ = "cnpj"
    CPF = "cpf"


class PropertySpec(BaseModel):
    """Definição de uma property de Object Type."""

    model_config = ConfigDict(extra="forbid")

    type: PropertyType
    required: bool = False
    readonly: bool = False
    description: str | None = None
    marking: str | None = Field(None, description="Marking aplicada a esta property")

    # Constraints
    min: float | None = None
    max: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None

    # Type-specific
    currency: str | None = Field(None, description="Para type=money")
    enum_hint: list[str] | None = Field(None, description="Valores sugeridos (não força)")
    enum_values: list[str] | None = Field(None, description="Valores exigidos (type=enum)")
    item_type: PropertyType | None = Field(None, description="Para type=array")
    ref_type: str | None = Field(None, description="Para type=ref")


class ComputedPropertySpec(BaseModel):
    """Property calculada (read-only)."""

    model_config = ConfigDict(extra="forbid")

    type: PropertyType
    formula: str = Field(..., description="Expressão asteval; recebe props do objeto como vars")
    description: str | None = None


# =============================================================================
# Backing (de onde vêm os dados)
# =============================================================================


class BackingType(str, Enum):
    SQLALCHEMY = "sqlalchemy"
    EXTERNAL_API = "external_api"
    FUNCTION = "function"


class ObjectBacking(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: BackingType
    model: str | None = Field(None, description="Para SQLALCHEMY: dotted path para a classe")
    primary_key: str | list[str] = "id"
    table: str | None = None  # override


# =============================================================================
# Links
# =============================================================================


class LinkCardinality(str, Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class LinkBackingType(str, Enum):
    FOREIGN_KEY = "foreign_key"
    JUNCTION_TABLE = "junction_table"
    FUNCTION = "function"


class LinkBacking(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: LinkBackingType
    column: str | None = None  # FK on this side
    target_column: str | None = None  # FK on the other side
    table: str | None = None  # for junction
    handler: str | None = None  # for function


class LinkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(..., description="Nome do ObjectType alvo")
    cardinality: LinkCardinality
    backing: LinkBacking
    reverse_name: str | None = Field(
        None, description="Nome do link reverso (gerado auto se ausente)"
    )
    description: str | None = None


# =============================================================================
# Markings (referenciadas)
# =============================================================================


class MarkingsRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inherit: list[str] = Field(default_factory=list)


# =============================================================================
# ObjectType
# =============================================================================


class ObjectTypeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backing: ObjectBacking
    title_property: str = Field(..., description="Property usada como rótulo humano")
    identifier_properties: list[str] = Field(default_factory=lambda: ["id"])

    properties: dict[str, PropertySpec]
    computed_properties: dict[str, ComputedPropertySpec] = Field(default_factory=dict)
    links: dict[str, LinkSpec] = Field(default_factory=dict)
    markings: MarkingsRef = Field(default_factory=MarkingsRef)

    actions: list[str] = Field(default_factory=list, description="Nomes de ActionTypes aplicáveis")


class ObjectTypeResource(ResourceBase):
    kind: Literal["ObjectType"]
    spec: ObjectTypeSpec


# =============================================================================
# ActionType
# =============================================================================


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ValidationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str = Field(..., description="Expressão asteval; vars: inputs + props do target")
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR


class AuthorizationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str] = Field(default_factory=list)
    require_markings: list[str] = Field(default_factory=list)
    require_confirmation: bool = Field(
        False, description="Para Actions chamadas pela IA, exige confirmação humana"
    )


class EffectSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handler: str = Field(
        ..., description="Dotted path; ex: app.ontology.actions.product.update_price"
    )
    is_async: bool = Field(False, alias="async")
    transactional: bool = True


class AuditSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields_before: list[str] = Field(default_factory=list)
    fields_after: list[str] = Field(default_factory=list)
    extra_context: list[str] = Field(default_factory=list)


class ActionTypeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(..., description="Nome do ObjectType alvo")
    inputs: dict[str, PropertySpec]
    validation: list[ValidationRule] = Field(default_factory=list)
    authorization: AuthorizationSpec
    effect: EffectSpec
    audit: AuditSpec = Field(default_factory=AuditSpec)
    dry_run: Literal["supported", "required", "unsupported"] = "supported"


class ActionTypeResource(ResourceBase):
    kind: Literal["ActionType"]
    spec: ActionTypeSpec


# =============================================================================
# MarkingSet
# =============================================================================


class MarkingEnforcement(str, Enum):
    ROW_LEVEL = "row_level"
    COLUMN_LEVEL = "column_level"
    OBJECT_LEVEL = "object_level"


class MarkingDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    enforcement: MarkingEnforcement
    predicate: str | None = Field(None, description="Expressão asteval; vars: row, user")
    requires_role: list[str] = Field(default_factory=list)
    requires_marking_grant: bool = False


class MarkingSetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markings: dict[str, MarkingDef]


class MarkingSetResource(ResourceBase):
    kind: Literal["MarkingSet"]
    spec: MarkingSetSpec


# =============================================================================
# Union para o loader
# =============================================================================

OntologyResource = ObjectTypeResource | ActionTypeResource | MarkingSetResource


def parse_resource(raw: dict[str, Any]) -> OntologyResource:
    """
    Parser disjunto: olha o `kind` e instancia o modelo apropriado.

    TODO(sem1): suporte a kind=FunctionType
    TODO(sem1): mensagens de erro contextualizadas (path do YAML, linha)
    """
    kind = raw.get("kind")
    if kind == "ObjectType":
        return ObjectTypeResource.model_validate(raw)
    if kind == "ActionType":
        return ActionTypeResource.model_validate(raw)
    if kind == "MarkingSet":
        return MarkingSetResource.model_validate(raw)
    raise ValueError(f"Unknown ontology kind: {kind!r}")
