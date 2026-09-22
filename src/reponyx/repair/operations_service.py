"""Bounded operational services for jobs, review, history, and metrics."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from reponyx.repair.operations import JobStatus, RepairJob, ReviewStatus
from reponyx.repair.operations_db import OperationsStore
from reponyx.repair.service import RepairService


class RepairOperationsService:
    def __init__(self, repairs: RepairService, store: OperationsStore | None = None) -> None:
        self.repairs = repairs
        self.store = store or OperationsStore(repairs.repositories.store)
        self.reviews: dict[str, ReviewStatus] = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reponyx-repair")

    def enqueue(
        self, repository_id: str, issue: str, investigation_id: str | None = None
    ) -> dict[str, str]:
        job = RepairJob(uuid4().hex, "", JobStatus.QUEUED, datetime.now(UTC))
        self.store.save_job(job)
        self.executor.submit(self._run, job.job_id, repository_id, issue, investigation_id)
        return {"job_id": job.job_id, "status": job.status.value}

    def _run(
        self, job_id: str, repository_id: str, issue: str, investigation_id: str | None
    ) -> None:
        jobs = self.store.list_jobs()
        job = next(item for item in jobs if item.job_id == job_id)
        running = RepairJob(
            job.job_id, job.repair_id, JobStatus.RUNNING, job.created_at, datetime.now(UTC)
        )
        self.store.update_job(running)
        try:
            result = self.repairs.create(repository_id, issue, investigation_id)
            completed = RepairJob(
                job_id,
                result["repair_id"],
                JobStatus.COMPLETED,
                job.created_at,
                running.started_at,
                datetime.now(UTC),
            )
            self.store.update_job(completed)
            self.reviews[result["repair_id"]] = ReviewStatus.PENDING_REVIEW
        except Exception as exc:
            self.store.update_job(
                RepairJob(
                    job_id,
                    job.repair_id,
                    JobStatus.FAILED,
                    job.created_at,
                    running.started_at,
                    datetime.now(UTC),
                    str(exc),
                )
            )

    def history(self, repository_id: str | None = None) -> list[dict[str, object]]:
        seen: set[str] = set()
        items: list[dict[str, object]] = []
        for state in self.repairs.active.values():
            rid = str(state["repair_id"])
            if repository_id is not None and state["repository_id"] != repository_id:
                continue
            seen.add(rid)
            items.append(
                {
                    "repair_id": rid,
                    "repository_id": state["repository_id"],
                    "status": state["repair_status"],
                    "iteration_count": state.get("iteration_count", 0),
                    "issue": state.get("issue", ""),
                }
            )
        for state in self.repairs.store.list():
            rid = str(state["repair_id"])
            if rid in seen:
                continue
            if repository_id is not None and state.get("repository_id") != repository_id:
                continue
            seen.add(rid)
            items.append(
                {
                    "repair_id": rid,
                    "repository_id": state.get("repository_id", ""),
                    "status": state.get("repair_status", "unknown"),
                    "iteration_count": state.get("iteration_count", 0),
                    "issue": state.get("issue", ""),
                }
            )
        return items

    def review(self, repair_id: str) -> dict[str, object]:
        report = self.repairs.report(repair_id)
        if report is None:
            raise KeyError(repair_id)
        return {
            "repair_id": repair_id,
            "status": self.reviews.get(repair_id, ReviewStatus.PENDING_REVIEW).value,
            "report": report,
            "diff": self.repairs.diff(repair_id),
        }

    def approve(self, repair_id: str) -> dict[str, str]:
        if self.repairs.report(repair_id) is None:
            raise KeyError(repair_id)
        self.reviews[repair_id] = ReviewStatus.APPROVED
        return {"repair_id": repair_id, "status": ReviewStatus.APPROVED.value}

    def reject(self, repair_id: str) -> dict[str, str]:
        if self.repairs.report(repair_id) is None:
            raise KeyError(repair_id)
        self.reviews[repair_id] = ReviewStatus.REJECTED
        return {"repair_id": repair_id, "status": ReviewStatus.REJECTED.value}
