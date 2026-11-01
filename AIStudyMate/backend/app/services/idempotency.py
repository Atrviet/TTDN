import hashlib,json
from dataclasses import dataclass
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.advanced_learning import AIGenerationRequest

class IdempotencyConflictError(Exception):pass
class IdempotencyInProgressError(Exception):pass
class IdempotencyPersistenceError(Exception):pass
@dataclass(frozen=True)
class IdempotencyClaim:
    record_id:UUID|None;completed_resource_id:UUID|None
class IdempotencyService:
    def __init__(self,session:AsyncSession)->None:self.session=session
    async def claim(self,user_id:UUID,operation:str,key:str|None,payload:BaseModel)->IdempotencyClaim:
        if not key:return IdempotencyClaim(None,None)
        digest=hashlib.sha256(json.dumps(payload.model_dump(mode="json"),sort_keys=True,separators=(",",":")).encode()).hexdigest()
        existing=await self.session.scalar(select(AIGenerationRequest).where(AIGenerationRequest.user_id==user_id,AIGenerationRequest.operation==operation,AIGenerationRequest.idempotency_key==key))
        if existing:
            if existing.request_hash!=digest:raise IdempotencyConflictError
            if existing.status=="completed":return IdempotencyClaim(existing.id,existing.resource_id)
            if existing.status=="in_progress":raise IdempotencyInProgressError
            existing.status="in_progress";existing.error_code=None;await self.session.commit();return IdempotencyClaim(existing.id,None)
        record=AIGenerationRequest(user_id=user_id,operation=operation,idempotency_key=key,request_hash=digest,status="in_progress");self.session.add(record)
        try:await self.session.commit()
        except IntegrityError as exc:await self.session.rollback();raise IdempotencyInProgressError from exc
        except SQLAlchemyError as exc:await self.session.rollback();raise IdempotencyPersistenceError from exc
        return IdempotencyClaim(record.id,None)
    async def complete(self,claim:IdempotencyClaim,resource_id:UUID)->None:
        if claim.record_id is None:return
        record=await self.session.get(AIGenerationRequest,claim.record_id);record.status="completed";record.resource_id=resource_id;await self.session.commit()
    async def fail(self,claim:IdempotencyClaim,code:str)->None:
        if claim.record_id is None:return
        await self.session.rollback();record=await self.session.get(AIGenerationRequest,claim.record_id);record.status="failed";record.error_code=code[:64];await self.session.commit()
