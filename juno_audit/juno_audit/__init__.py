"""juno_audit - Camada de Confianca do JUNO_AI (Ledger + Agent ID + Export)."""
from .chain import build_event, verify_chain, GENESIS
from .merkle import merkle_root, merkle_proof, verify_proof
from .signer import generate_keypair, sign_event, verify_event_signature
from .middleware import AuditLedger, AuditEventRow, Base
from .models_anchor import AuditAnchorRow
from .batch import close_open_batches, retry_pending, upgrade_submitted
from .scheduler import build_scheduler, run_cycle
from .anchors import (OpenTimestampsBackend, ClientExportBackend,
                      IcpBrasilTsaBackend)
from .registry import (AgentRow, register_agent, list_agents, get_agent,
                       revoke_agent, pubkeys_snapshot,
                       AgentAlreadyExists, AgentNotFound)
from .export import build_export_bundle, EXPORT_SCHEMA_VERSION

__version__ = "0.3.0"
