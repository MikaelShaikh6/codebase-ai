from pathlib import Path

from app.services.storage import LocalProjectStorage


def test_local_storage_saves_and_restores_archive(tmp_path: Path) -> None:
    storage = LocalProjectStorage(tmp_path / "objects")
    storage.save_archive("project-1", b"zip-content")

    restored = storage.restore_archive("project-1", tmp_path / "worker")

    assert restored.read_bytes() == b"zip-content"
