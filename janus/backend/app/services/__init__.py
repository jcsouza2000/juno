"""
Camada de Services — lógica de negócio entre Routers e Models.

Convenções:
- Routers (app.routers.*) lidam só com parse/validação de input e response.
  Toda lógica de negócio deve estar em um Service.
- Services recebem o `db: Session` por injeção, retornam models ou DTOs.
- Services nunca importam `fastapi` (devem ser testáveis sem app).

Exemplo:

    # app/services/auth_service.py
    class AuthService:
        def __init__(self, db: Session):
            self.db = db

        def authenticate(self, email: str, password: str) -> User | None:
            ...

    # app/routers/auth.py
    @router.post("/login")
    def login(form, db = Depends(get_db)):
        service = AuthService(db)
        user = service.authenticate(form.username, form.password)
        ...
"""
