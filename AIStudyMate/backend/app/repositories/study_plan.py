from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.advanced_learning import StudyPlan, StudyTask


OPTIONS = (selectinload(StudyPlan.tasks), selectinload(StudyPlan.documents), selectinload(StudyPlan.availability))


class StudyPlanRepository:
    def __init__(self, session: AsyncSession): self.session = session
    def add(self, plan: StudyPlan): self.session.add(plan)
    async def list_owned(self, user_id: UUID):
        return list((await self.session.scalars(select(StudyPlan).where(StudyPlan.user_id == user_id).options(*OPTIONS).order_by(StudyPlan.created_at.desc()))).unique().all())
    async def get_owned(self, plan_id: UUID, user_id: UUID, *, for_update=False):
        query = select(StudyPlan).where(StudyPlan.id == plan_id, StudyPlan.user_id == user_id).options(*OPTIONS).execution_options(populate_existing=True)
        if for_update: query = query.with_for_update(of=StudyPlan)
        return await self.session.scalar(query)
    async def get_task_owned(self, task_id: UUID, user_id: UUID, *, for_update=False):
        query = select(StudyTask).join(StudyTask.plan).where(StudyTask.id == task_id, StudyPlan.user_id == user_id).options(selectinload(StudyTask.plan)).execution_options(populate_existing=True)
        if for_update: query = query.with_for_update(of=StudyTask)
        return await self.session.scalar(query)
    async def delete_incomplete_tasks(self, plan_id: UUID):
        await self.session.execute(delete(StudyTask).where(StudyTask.plan_id == plan_id, StudyTask.status != "completed"))
    async def delete(self, plan: StudyPlan): await self.session.delete(plan)
