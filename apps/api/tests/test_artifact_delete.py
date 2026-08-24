import uuid

from app.config import settings
from app.services.studio.media import remove_artifact_files


def test_remove_artifact_files_deletes_media_and_keeps_others(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "file_store", str(tmp_path))
    notebook_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    other_id = uuid.uuid4()
    folder = tmp_path / str(notebook_id) / "artifacts"
    folder.mkdir(parents=True)
    (folder / f"{artifact_id}.mp3").write_bytes(b"audio")
    (folder / f"{artifact_id}.mp4").write_bytes(b"video")
    work = folder / f"{artifact_id}-parts"
    work.mkdir()
    (work / "clip.mp3").write_bytes(b"clip")
    (folder / f"{other_id}.mp3").write_bytes(b"keep")

    remove_artifact_files(notebook_id, artifact_id)

    assert not (folder / f"{artifact_id}.mp3").exists()
    assert not (folder / f"{artifact_id}.mp4").exists()
    assert not work.exists()
    assert (folder / f"{other_id}.mp3").read_bytes() == b"keep"
