"""
sdk_gen — geradores de SDK Python e TypeScript a partir do Registry.

Uso (CLI, planejado):
    juno ontology generate-sdk --lang python --out sdk/python/
    juno ontology generate-sdk --lang typescript --out janus/frontend/src/ontology/

TODO(sem4): implementar
"""

from .python import generate_python_sdk  # noqa: F401
from .typescript import generate_typescript_sdk  # noqa: F401
