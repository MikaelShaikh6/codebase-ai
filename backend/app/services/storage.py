from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class ProjectStorage(Protocol):
    def save_archive(self, project_id: str, content: bytes) -> None:
        ...

    def restore_archive(self, project_id: str, destination: Path) -> Path:
        ...


class LocalProjectStorage:
    def __init__(self, root: Path = Path("data/projects")) -> None:
        self.root = root.resolve()

    def save_archive(self, project_id: str, content: bytes) -> None:
        directory = self.root / project_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "upload.zip").write_bytes(content)

    def restore_archive(self, project_id: str, destination: Path) -> Path:
        source = self.root / project_id / "upload.zip"
        destination.mkdir(parents=True, exist_ok=True)
        archive = destination / "upload.zip"
        if source != archive:
            archive.write_bytes(source.read_bytes())
        return archive


class S3ProjectStorage:
    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as error:
            raise RuntimeError(
                "boto3 is required when STORAGE_BACKEND=s3."
            ) from error
        self.client = boto3.client(
            "s3",
            endpoint_url=os.environ["S3_ENDPOINT_URL"],
            aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
            region_name=os.getenv("S3_REGION", "auto"),
        )
        self.bucket = os.environ["S3_BUCKET"]

    def save_archive(self, project_id: str, content: bytes) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=f"projects/{project_id}/upload.zip",
            Body=content,
            ContentType="application/zip",
        )

    def restore_archive(self, project_id: str, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        archive = destination / "upload.zip"
        self.client.download_file(
            self.bucket,
            f"projects/{project_id}/upload.zip",
            str(archive),
        )
        return archive


def get_project_storage() -> ProjectStorage:
    if os.getenv("STORAGE_BACKEND", "local").lower() == "s3":
        return S3ProjectStorage()
    return LocalProjectStorage()
