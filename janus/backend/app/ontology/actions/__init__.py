"""
app.ontology.actions — handlers das Action Types declaradas em definitions/.

Cada handler tem assinatura:
    def handler(target, inputs: dict, *, db, user, cursor) -> None
      - target: instancia SQLAlchemy ja carregada (row)
      - inputs: dict de inputs validados
      - db: Session (transacao aberta — handler nao deve commit/rollback)
      - user: UserContext
      - cursor: AuditCursor (handler pode chamar cursor.add_warning, etc.)

Handler so MUTA o target. Nao decide nada de auth/validation/audit — quem cuida
disso e' o runtime.execute_action. Aqui e' so a regra de negocio crua.
"""
