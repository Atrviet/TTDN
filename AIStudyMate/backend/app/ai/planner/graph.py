from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langgraph.graph import END, START, StateGraph

from app.ai.planner.state import PlannedTask, StudyPlannerState
from app.ai.rag.service import RAGService
from app.ai.topics import LearningTopicIdentifier, TopicEvidence


SavePlan = Callable[[StudyPlannerState], Awaitable[object]]


class StudyPlannerGraph:
    def __init__(self, *, rag_service: RAGService, topic_identifier: LearningTopicIdentifier,
                 save_plan: SavePlan, max_steps: int, max_retries: int, context_top_k: int) -> None:
        self.rag_service = rag_service
        self.topic_identifier = topic_identifier
        self.save_plan_callback = save_plan
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.context_top_k = context_top_k
        self.graph = self._build()

    def _build(self):
        builder = StateGraph(StudyPlannerState)
        for name, node in (
            ("validate_goal", self._validate_goal),
            ("retrieve_learning_material", self._retrieve),
            ("identify_topics", self._identify_topics),
            ("estimate_workload", self._estimate_workload),
            ("generate_schedule", self._generate_schedule),
            ("validate_schedule", self._validate_schedule),
            ("save_plan", self._save_plan),
        ):
            builder.add_node(name, node)
        builder.add_edge(START, "validate_goal")
        builder.add_conditional_edges("validate_goal", self._route, {"continue": "retrieve_learning_material", "end": END})
        builder.add_conditional_edges("retrieve_learning_material", self._route, {"continue": "identify_topics", "end": END})
        builder.add_conditional_edges("identify_topics", self._route, {"continue": "estimate_workload", "end": END})
        builder.add_conditional_edges("estimate_workload", self._route, {"continue": "generate_schedule", "end": END})
        builder.add_edge("generate_schedule", "validate_schedule")
        builder.add_conditional_edges(
            "validate_schedule", self._after_validation,
            {"save": "save_plan", "retry": "generate_schedule", "end": END},
        )
        builder.add_edge("save_plan", END)
        return builder.compile()

    async def run(self, state: StudyPlannerState) -> StudyPlannerState:
        return await self.graph.ainvoke(state, config={"recursion_limit": self.max_steps + 2})

    def _step(self, state: StudyPlannerState) -> dict | None:
        if state["execution_steps"] >= self.max_steps:
            return {"status": "step_limit", "error": "Maximum planner graph steps reached"}
        return None

    async def _validate_goal(self, state: StudyPlannerState) -> dict:
        if limited := self._step(state): return limited
        try:
            ZoneInfo(state["timezone"])
        except ZoneInfoNotFoundError:
            return {"status": "invalid", "error": "Unknown timezone", "execution_steps": state["execution_steps"] + 1}
        today = datetime.now(ZoneInfo(state["timezone"])).date()
        if state["exam_date"] <= today:
            return {"status": "invalid", "error": "Exam date must be in the future", "execution_steps": state["execution_steps"] + 1}
        if not state["available_days"]:
            return {"status": "invalid", "error": "At least one study day is required", "execution_steps": state["execution_steps"] + 1}
        return {"execution_steps": state["execution_steps"] + 1}

    async def _retrieve(self, state: StudyPlannerState) -> dict:
        if limited := self._step(state): return limited
        results = await self.rag_service.search(
            query=f"{state['subject']} {state['goal']}", document_ids=state["document_ids"],
            user_id=state["user_id"], top_k=self.context_top_k,
        )
        evidence = [{"document_id": item.metadata["document_id"], "chunk_id": item.chroma_id,
                     "page_number": item.metadata.get("page_number"), "text": item.text} for item in results]
        if not evidence:
            return {"status": "invalid", "error": "No learning material is available", "execution_steps": state["execution_steps"] + 1}
        return {"retrieved_evidence": evidence, "execution_steps": state["execution_steps"] + 1}

    async def _identify_topics(self, state: StudyPlannerState) -> dict:
        if limited := self._step(state): return limited
        result = await self.topic_identifier.identify([TopicEvidence.model_validate(item) for item in state["retrieved_evidence"]])
        if not result.topics:
            return {"status": "invalid", "error": "No study topics could be identified", "execution_steps": state["execution_steps"] + 1}
        topics = [item.model_dump() for item in result.topics]
        return {"topics": topics, "execution_steps": state["execution_steps"] + 1}

    async def _estimate_workload(self, state: StudyPlannerState) -> dict:
        if limited := self._step(state): return limited
        multiplier = {"easy": 1, "medium": 2, "hard": 3}[state["difficulty"]]
        workload = len(state["topics"]) * (multiplier + 1) * state["preferred_session_minutes"]
        days = self._eligible_dates(state)
        capacity = len(days) * state["daily_available_minutes"]
        if workload > capacity:
            return {"status": "invalid", "error": f"Impossible deadline: requires {workload} minutes but only {capacity} are available", "workload_minutes": workload, "execution_steps": state["execution_steps"] + 1}
        return {"workload_minutes": workload, "execution_steps": state["execution_steps"] + 1}

    async def _generate_schedule(self, state: StudyPlannerState) -> dict:
        if limited := self._step(state): return limited
        zone = ZoneInfo(state["timezone"]); dates = self._eligible_dates(state)
        multiplier = {"easy": 1, "medium": 2, "hard": 3}[state["difficulty"]]
        specs = []
        for topic in state["topics"]:
            for index in range(multiplier): specs.append((topic["name"], "study", 5 - index))
            specs.append((topic["name"], "review", 4))
        tasks: list[PlannedTask] = []; cursor = 0; used: dict[date, int] = {}
        for topic, task_type, priority in specs:
            while cursor < len(dates) and used.get(dates[cursor], 0) + state["preferred_session_minutes"] > state["daily_available_minutes"]:
                cursor += 1
            if cursor >= len(dates):
                return {"status": "invalid", "error": "Impossible deadline after schedule allocation", "execution_steps": state["execution_steps"] + 1}
            day = dates[cursor]; offset = used.get(day, 0)
            start = datetime.combine(day, time(18, 0), zone) + timedelta(minutes=offset)
            end = start + timedelta(minutes=state["preferred_session_minutes"])
            used[day] = offset + state["preferred_session_minutes"]
            tasks.append({"title": f"{'Ôn tập' if task_type == 'review' else 'Học'}: {topic}",
                          "description": state["goal"], "topic": topic, "task_type": task_type,
                          "priority": max(1, min(priority, 5)), "planned_start_at": start.astimezone(UTC),
                          "due_at": end.astimezone(UTC), "planned_duration_minutes": state["preferred_session_minutes"],
                          "document_id": state["document_ids"][0] if state["document_ids"] else None})
        return {"proposed_tasks": tasks, "execution_steps": state["execution_steps"] + 1}

    async def _validate_schedule(self, state: StudyPlannerState) -> dict:
        if limited := self._step(state): return limited
        error = self.validate_tasks(state)
        if error:
            return {"status": "invalid", "error": error, "retry_count": state["retry_count"] + 1,
                    "execution_steps": state["execution_steps"] + 1}
        return {"status": "valid", "error": None, "execution_steps": state["execution_steps"] + 1}

    async def _save_plan(self, state: StudyPlannerState) -> dict:
        if limited := self._step(state): return limited
        plan = await self.save_plan_callback(state)
        return {"status": "saved", "plan_id": plan.id, "execution_steps": state["execution_steps"] + 1}

    def validate_tasks(self, state: StudyPlannerState) -> str | None:
        zone = ZoneInfo(state["timezone"]); by_day: dict[date, list[PlannedTask]] = {}
        for task in state["proposed_tasks"]:
            local_start = task["planned_start_at"].astimezone(zone); local_end = task["due_at"].astimezone(zone)
            if local_start.date() > state["exam_date"] or local_end.date() > state["exam_date"]:
                return "A task is scheduled after the exam deadline"
            if local_start.weekday() not in state["available_days"]:
                return "A task is scheduled outside selected study days"
            if local_end <= local_start or task["planned_duration_minutes"] > state["daily_available_minutes"]:
                return "A task has invalid duration"
            by_day.setdefault(local_start.date(), []).append(task)
        for tasks in by_day.values():
            if sum(item["planned_duration_minutes"] for item in tasks) > state["daily_available_minutes"]:
                return "Daily availability is exceeded"
            ordered = sorted(tasks, key=lambda item: item["planned_start_at"])
            if any(left["due_at"] > right["planned_start_at"] for left, right in zip(ordered, ordered[1:])):
                return "Study tasks overlap"
        return None

    def _eligible_dates(self, state: StudyPlannerState) -> list[date]:
        zone = ZoneInfo(state["timezone"]); current = datetime.now(zone).date()
        result = []
        while current <= state["exam_date"]:
            if current.weekday() in state["available_days"]: result.append(current)
            current += timedelta(days=1)
        return result

    @staticmethod
    def _route(state: StudyPlannerState) -> Literal["continue", "end"]:
        return "end" if state["status"] in {"invalid", "step_limit"} else "continue"

    def _after_validation(self, state: StudyPlannerState) -> Literal["save", "retry", "end"]:
        if state["status"] == "valid": return "save"
        if state["status"] == "invalid" and state["retry_count"] <= self.max_retries: return "retry"
        return "end"
