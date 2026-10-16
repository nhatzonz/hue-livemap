"""Lưu file ảnh. MVP: đĩa cục bộ. Production: thay bằng S3Storage (cùng giao diện) qua cấu hình."""

from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...


class LocalDiskStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):  # chặn path traversal
            raise ValueError(f"Khoá lưu trữ không hợp lệ: {key}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()
