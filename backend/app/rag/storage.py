import uuid
from pathlib import Path


class FileStorage:
    """Keeps uploaded files on local disk under generated names."""

    def __init__(self, root: str):
        self.root = Path(root)

    def save(self, data: bytes, extension: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + extension.lower()
        self.path(name).write_bytes(data)
        return name

    def path(self, name: str) -> Path:
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError(f"Invalid stored file name: {name!r}")
        return self.root / name

    def delete(self, name: str) -> None:
        self.path(name).unlink(missing_ok=True)
