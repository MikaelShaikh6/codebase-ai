from __future__ import annotations

import os
import logging
import threading
import time
from pathlib import Path

from sqlmodel import Session, select

from app.core.database import engine
from app.models.job import JobStatus, ProjectJob
from app.models.project import Project, ProjectStatus
from app.services.project_processor import process_project

POLL_INTERVAL_SECONDS = 2
logger = logging.getLogger(__name__)
_worker_started = False
_worker_lock = threading.Lock()


def process_next_job() -> bool:
    with Session(engine) as session:
        job = session.exec(
            select(ProjectJob)
            .where(ProjectJob.status == JobStatus.QUEUED)
            .order_by(ProjectJob.created_at)
        ).first()
        if job is None:
            return False
        job.status = JobStatus.RUNNING
        job.attempts += 1
        session.add(job)
        session.commit()
        job_id, project_id = job.id, job.project_id

    project_directory = Path("data/projects").resolve() / project_id
    process_project(project_id, project_directory=project_directory)

    with Session(engine) as session:
        job = session.get(ProjectJob, job_id)
        project = session.get(Project, project_id)
        if job is not None:
            job.status = (
                JobStatus.COMPLETED
                if project is not None and project.status != ProjectStatus.FAILED
                else JobStatus.FAILED
            )
            job.error = project.error if project is not None else "Project was not found."
            session.add(job)
            session.commit()
    return True


def recover_interrupted_jobs() -> None:
    with Session(engine) as session:
        jobs = session.exec(
            select(ProjectJob).where(ProjectJob.status == JobStatus.RUNNING)
        ).all()
        for job in jobs:
            job.status = JobStatus.QUEUED
            session.add(job)
        session.commit()


def start_project_worker() -> None:
    global _worker_started
    if os.getenv("RUN_PROJECT_WORKER", "false").lower() != "true":
        return
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True
    recover_interrupted_jobs()
    thread = threading.Thread(target=_worker_loop, name="project-worker", daemon=True)
    thread.start()


def _worker_loop() -> None:
    while True:
        try:
            if not process_next_job():
                time.sleep(POLL_INTERVAL_SECONDS)
        except Exception:
            logger.exception("Project worker iteration failed.")
            time.sleep(POLL_INTERVAL_SECONDS)
