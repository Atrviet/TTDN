from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePath
from uuid import UUID, uuid4

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool


UPLOAD_CHUNK_SIZE = 1024 * 1024


class StorageError(Exception):
    """Raised when local document storage cannot complete an operation."""


class FileTooLargeError(Exception):
    """Raised as soon as a streamed upload exceeds its configured limit."""


class EmptyUploadError(Exception):
    """Raised when an uploaded file contains no bytes."""


@dataclass(frozen=True)
class TemporaryUpload:
    path: Path
    size: int
    original_filename: str


@dataclass(frozen=True)
class StagedDeletion:
    original_relative_path: str
    trash_path: Path | None


class LocalDocumentStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.staging_dir = self.root / ".staging"
        self.trash_dir = self.root / ".trash"

    @staticmethod
    def safe_original_filename(filename: str | None) -> str:
        candidate = PurePath((filename or "document.pdf").replace("\\", "/")).name
        candidate = candidate.replace("\x00", "").strip()
        return candidate[:255] or "document.pdf"

    def resolve_relative_path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise StorageError("Stored document path escapes the storage root") from exc
        return path

    async def save_temporary(self, upload: UploadFile, max_size: int) -> TemporaryUpload:
        temporary_path = self.staging_dir / f"{uuid4()}.part"
        total_size = 0
        handle = None
        try:
            await run_in_threadpool(self.staging_dir.mkdir, parents=True, exist_ok=True)
            handle = await run_in_threadpool(temporary_path.open, "xb")
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > max_size:
                    raise FileTooLargeError
                await run_in_threadpool(handle.write, chunk)
            if total_size == 0:
                raise EmptyUploadError
            await run_in_threadpool(handle.flush)
            return TemporaryUpload(
                path=temporary_path,
                size=total_size,
                original_filename=self.safe_original_filename(upload.filename),
            )
        except (FileTooLargeError, EmptyUploadError):
            await self._close_and_remove(handle, temporary_path)
            raise
        except OSError as exc:
            await self._close_and_remove(handle, temporary_path)
            raise StorageError("Unable to write uploaded file") from exc
        finally:
            if handle is not None and not handle.closed:
                await run_in_threadpool(handle.close)

    async def promote(self, temporary_path: Path, user_id: UUID) -> str:
        relative_path = f"{user_id}/{uuid4()}.pdf"
        destination = self.resolve_relative_path(relative_path)
        try:
            await run_in_threadpool(destination.parent.mkdir, parents=True, exist_ok=True)
            await run_in_threadpool(os.replace, temporary_path, destination)
        except OSError as exc:
            await self.remove_path(temporary_path)
            raise StorageError("Unable to finalize uploaded file") from exc
        return relative_path

    async def delete(self, relative_path: str) -> None:
        await self.remove_path(self.resolve_relative_path(relative_path))

    async def stage_deletion(self, relative_path: str) -> StagedDeletion:
        source = self.resolve_relative_path(relative_path)
        if not await run_in_threadpool(source.exists):
            return StagedDeletion(relative_path, None)
        trash_path = self.trash_dir / f"{uuid4()}.deleted"
        try:
            await run_in_threadpool(self.trash_dir.mkdir, parents=True, exist_ok=True)
            await run_in_threadpool(os.replace, source, trash_path)
        except OSError as exc:
            raise StorageError("Unable to stage document deletion") from exc
        return StagedDeletion(relative_path, trash_path)

    async def restore_deletion(self, staged: StagedDeletion) -> None:
        if staged.trash_path is None:
            return
        destination = self.resolve_relative_path(staged.original_relative_path)
        try:
            await run_in_threadpool(destination.parent.mkdir, parents=True, exist_ok=True)
            await run_in_threadpool(os.replace, staged.trash_path, destination)
        except OSError as exc:
            raise StorageError("Unable to restore document after database failure") from exc

    async def finalize_deletion(self, staged: StagedDeletion) -> None:
        if staged.trash_path is not None:
            await self.remove_path(staged.trash_path)

    async def remove_path(self, path: Path) -> None:
        try:
            await run_in_threadpool(path.unlink, missing_ok=True)
        except OSError as exc:
            raise StorageError("Unable to remove stored file") from exc

    async def _close_and_remove(self, handle: object, path: Path) -> None:
        try:
            if handle is not None and not getattr(handle, "closed", True):
                await run_in_threadpool(handle.close)
            await self.remove_path(path)
        except StorageError:
            pass

