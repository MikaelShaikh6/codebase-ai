from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.project import Project, ProjectStatus


def test_project_metadata_persists_with_processing_status() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    created_at = datetime.now(timezone.utc)

    with Session(engine) as session:
        session.add(
            Project(
                id="project-1",
                filename="project.zip",
                status=ProjectStatus.PROCESSING,
                created_at=created_at,
            )
        )
        session.commit()

    with Session(engine) as session:
        project = session.exec(
            select(Project).where(Project.id == "project-1")
        ).one()

    assert project.filename == "project.zip"
    assert project.status == ProjectStatus.PROCESSING
    assert project.created_at.replace(tzinfo=timezone.utc) == created_at


def test_project_status_can_record_processing_failure() -> None:
    project = Project(
        id="project-1",
        filename="project.zip",
        status=ProjectStatus.FAILED,
        error="invalid ZIP",
    )

    assert project.status == ProjectStatus.FAILED
    assert project.error == "invalid ZIP"
