"""
JUNO LGPD/GDPR Engine
Conformidade com Lei Geral de Protecao de Dados e GDPR
"""

import json
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow_naive
from app.models import ConsentRecord, Customer, DataSubjectRequest
from app.security.audit_engine import AuditEngine

logger = logging.getLogger(__name__)


class GDPREngine:
    """
    Engine de conformidade LGPD/GDPR.
    """

    REQUEST_TYPES = {
        "access": "Acesso aos dados",
        "rectification": "Retificacao de dados",
        "erasure": "Exclusao de dados (direito ao esquecimento)",
        "portability": "Portabilidade dos dados",
        "restriction": "Restricao de processamento",
    }

    LEGAL_BASES = {
        "consent": "Consentimento",
        "contract": "Execucao de contrato",
        "legal_obligation": "Obrigacao legal",
        "vital_interests": "Interesses vitais",
        "public_task": "Interesse publico",
        "legitimate_interest": "Interesse legitimo",
    }

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditEngine(db)

    def create_data_subject_request(
        self,
        company_id: int,
        request_type: str,
        data_subject_email: str,
        data_subject_name: str | None = None,
        data_subject_type: str = "customer",
        request_details: str | None = None,
        legal_basis: str | None = None,
    ) -> DataSubjectRequest:
        """Cria nova requisicao do titular de dados."""
        if request_type not in self.REQUEST_TYPES:
            raise ValueError(f"Tipo de requisicao invalido: {request_type}")

        deadline = utcnow_naive() + timedelta(days=15)

        dsr = DataSubjectRequest(
            company_id=company_id,
            request_type=request_type,
            data_subject_email=data_subject_email,
            data_subject_name=data_subject_name,
            data_subject_type=data_subject_type,
            request_details=request_details,
            deadline_at=deadline,
            legal_basis=legal_basis,
        )
        self.db.add(dsr)
        self.db.commit()
        self.db.refresh(dsr)

        self.audit.log(
            company_id=company_id,
            user_id=None,
            action="DSR_CREATED",
            resource_type="data_subject_request",
            resource_id=dsr.id,
            new_values={"type": request_type, "email": data_subject_email},
            severity="info",
            compliance_tags=["lgpd", "gdpr"],
        )

        logger.info(f"[LGPD] DSR criada: {request_type} para {data_subject_email}")

        return dsr

    def process_data_subject_request(
        self,
        dsr_id: int,
        processed_by: int,
        approve: bool = True,
        response_data: dict | None = None,
        rejection_reason: str | None = None,
    ) -> DataSubjectRequest:
        """Processa uma requisicao do titular."""
        dsr = self.db.query(DataSubjectRequest).filter(DataSubjectRequest.id == dsr_id).first()

        if not dsr:
            raise ValueError("Requisicao nao encontrada")

        if dsr.status != "pending":
            raise ValueError("Requisicao ja processada")

        if approve:
            dsr.status = "completed"
            dsr.response_data = json.dumps(response_data, default=str) if response_data else None

            if dsr.request_type == "erasure":
                self._execute_erasure(dsr)
            elif dsr.request_type == "portability":
                dsr.response_data = json.dumps(self._execute_portability(dsr), default=str)
            elif dsr.request_type == "access":
                dsr.response_data = json.dumps(self._execute_access(dsr), default=str)
        else:
            dsr.status = "rejected"
            dsr.rejection_reason = rejection_reason

        dsr.completed_at = utcnow_naive()
        dsr.completed_by = processed_by

        self.db.commit()
        self.db.refresh(dsr)

        self.audit.log(
            company_id=dsr.company_id,
            user_id=processed_by,
            action="DSR_PROCESSED",
            resource_type="data_subject_request",
            resource_id=dsr.id,
            new_values={
                "status": dsr.status,
                "approved": approve,
                "completed_at": dsr.completed_at.isoformat(),
            },
            severity="info",
            compliance_tags=["lgpd", "gdpr"],
        )

        return dsr

    def _execute_erasure(self, dsr: DataSubjectRequest) -> None:
        """Executa exclusao/anomizacao de dados."""
        if dsr.data_subject_type == "customer":
            customer = (
                self.db.query(Customer)
                .filter(
                    Customer.email == dsr.data_subject_email, Customer.company_id == dsr.company_id
                )
                .first()
            )

            if customer:
                customer.name = "ANONIMIZADO"
                customer.email = f"anon_{customer.id}@deleted.local"
                customer.phone = None
                customer.address = None
                customer.document = None
                customer.is_active = False

                self.db.commit()
                logger.info(f"[LGPD] Cliente {customer.id} anonimizado")

    def _execute_portability(self, dsr: DataSubjectRequest) -> dict:
        """Exporta dados para portabilidade."""
        if dsr.data_subject_type == "customer":
            customer = (
                self.db.query(Customer)
                .filter(
                    Customer.email == dsr.data_subject_email, Customer.company_id == dsr.company_id
                )
                .first()
            )

            if customer:
                return {
                    "personal_data": {
                        "name": customer.name,
                        "email": customer.email,
                        "phone": customer.phone,
                        "address": customer.address,
                        "document": customer.document,
                    },
                    "orders": [],
                    "consents": self._get_consent_history(dsr.data_subject_email, dsr.company_id),
                }

        return {}

    def _execute_access(self, dsr: DataSubjectRequest) -> dict:
        """Retorna dados para requisicao de acesso."""
        return self._execute_portability(dsr)

    def record_consent(
        self,
        company_id: int,
        data_subject_email: str,
        consent_type: str,
        consent_given: bool,
        consent_text: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        consent_version: str = "1.0",
    ) -> ConsentRecord:
        """Registra consentimento do titular."""
        consent = ConsentRecord(
            company_id=company_id,
            data_subject_email=data_subject_email,
            consent_type=consent_type,
            consent_given=consent_given,
            consent_version=consent_version,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text=consent_text,
        )
        self.db.add(consent)
        self.db.commit()
        self.db.refresh(consent)

        self.audit.log(
            company_id=company_id,
            user_id=None,
            action="CONSENT_RECORDED",
            resource_type="consent",
            resource_id=consent.id,
            new_values={"type": consent_type, "given": consent_given, "email": data_subject_email},
            compliance_tags=["lgpd", "gdpr"],
        )

        return consent

    def withdraw_consent(self, consent_id: int, withdrawn_by: int) -> ConsentRecord:
        """Registra revogacao de consentimento."""
        consent = self.db.query(ConsentRecord).filter(ConsentRecord.id == consent_id).first()

        if not consent:
            raise ValueError("Consentimento nao encontrado")

        consent.consent_given = False
        consent.withdrawn_at = utcnow_naive()
        consent.withdrawn_by = withdrawn_by

        self.db.commit()
        self.db.refresh(consent)

        self.audit.log(
            company_id=consent.company_id,
            user_id=withdrawn_by,
            action="CONSENT_WITHDRAWN",
            resource_type="consent",
            resource_id=consent.id,
            old_values={"given": True},
            new_values={"given": False, "withdrawn_at": consent.withdrawn_at.isoformat()},
            compliance_tags=["lgpd", "gdpr"],
        )

        return consent

    def check_consent(self, company_id: int, data_subject_email: str, consent_type: str) -> bool:
        """Verifica se titular tem consentimento valido."""
        latest = (
            self.db.query(ConsentRecord)
            .filter(
                and_(
                    ConsentRecord.company_id == company_id,
                    ConsentRecord.data_subject_email == data_subject_email,
                    ConsentRecord.consent_type == consent_type,
                )
            )
            .order_by(ConsentRecord.created_at.desc())
            .first()
        )

        if not latest:
            return False

        return latest.consent_given and latest.withdrawn_at is None

    def _get_consent_history(self, email: str, company_id: int) -> list[dict]:
        """Retorna historico de consentimentos."""
        consents = (
            self.db.query(ConsentRecord)
            .filter(
                and_(
                    ConsentRecord.company_id == company_id,
                    ConsentRecord.data_subject_email == email,
                )
            )
            .order_by(ConsentRecord.created_at)
            .all()
        )

        return [
            {
                "type": c.consent_type,
                "given": c.consent_given,
                "version": c.consent_version,
                "date": c.created_at.isoformat() if c.created_at else None,
                "withdrawn": c.withdrawn_at is not None,
            }
            for c in consents
        ]

    def get_pending_requests(self, company_id: int) -> list[DataSubjectRequest]:
        """Retorna requisicoes pendentes."""
        return (
            self.db.query(DataSubjectRequest)
            .filter(
                and_(
                    DataSubjectRequest.company_id == company_id,
                    DataSubjectRequest.status == "pending",
                    DataSubjectRequest.deadline_at >= utcnow_naive(),
                )
            )
            .order_by(DataSubjectRequest.deadline_at)
            .all()
        )

    def get_compliance_report(self, company_id: int) -> dict[str, Any]:
        """Gera relatorio de conformidade LGPD/GDPR."""
        total_dsr = (
            self.db.query(DataSubjectRequest)
            .filter(DataSubjectRequest.company_id == company_id)
            .count()
        )

        pending_dsr = (
            self.db.query(DataSubjectRequest)
            .filter(
                and_(
                    DataSubjectRequest.company_id == company_id,
                    DataSubjectRequest.status == "pending",
                )
            )
            .count()
        )

        overdue_dsr = (
            self.db.query(DataSubjectRequest)
            .filter(
                and_(
                    DataSubjectRequest.company_id == company_id,
                    DataSubjectRequest.status == "pending",
                    DataSubjectRequest.deadline_at < utcnow_naive(),
                )
            )
            .count()
        )

        total_consents = (
            self.db.query(ConsentRecord).filter(ConsentRecord.company_id == company_id).count()
        )

        active_consents = (
            self.db.query(ConsentRecord)
            .filter(
                and_(
                    ConsentRecord.company_id == company_id,
                    ConsentRecord.consent_given == True,
                    ConsentRecord.withdrawn_at == None,
                )
            )
            .count()
        )

        withdrawn_consents = (
            self.db.query(ConsentRecord)
            .filter(
                and_(ConsentRecord.company_id == company_id, ConsentRecord.withdrawn_at != None)
            )
            .count()
        )

        return {
            "generated_at": utcnow_naive().isoformat(),
            "data_subject_requests": {
                "total": total_dsr,
                "pending": pending_dsr,
                "overdue": overdue_dsr,
                "compliance_rate": (
                    ((total_dsr - overdue_dsr) / total_dsr * 100) if total_dsr > 0 else 100
                ),
            },
            "consents": {
                "total": total_consents,
                "active": active_consents,
                "withdrawn": withdrawn_consents,
            },
            "recommendations": [
                (
                    "Revisar consentimentos expirados"
                    if active_consents < total_consents * 0.8
                    else None
                ),
                "Processar DSRs pendentes" if pending_dsr > 0 else None,
                "Investigar DSRs atrasadas" if overdue_dsr > 0 else None,
            ],
        }
