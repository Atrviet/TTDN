from typing import Annotated
from fastapi import Depends
from app.api.dependencies.auth import SessionDependency
from app.services.idempotency import IdempotencyService
def get_idempotency_service(session:SessionDependency):return IdempotencyService(session)
IdempotencyServiceDependency=Annotated[IdempotencyService,Depends(get_idempotency_service)]
