"""Stable, versioned, non-reversible project identity."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_SCP_REMOTE = re.compile(r"^(?:[^@/]+@)?([^:/]+):(.+)$")


def canonicalize_remote(remote: str) -> str:
    value = remote.strip().replace("\\", "/")
    match = _SCP_REMOTE.match(value) if "://" not in value else None
    if match:
        value = f"ssh://{match.group(1)}/{match.group(2)}"
    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold()
    if parsed.port is not None:
        host += f":{parsed.port}"
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    if path.casefold().endswith(".git"):
        path = path[:-4]
    return urlunsplit((scheme, host, path, "", ""))


class ProjectIdentityResolver:
    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()

    def resolve(self) -> str:
        remote = self._git("config", "--get", "remote.origin.url", required=False)
        if remote:
            identity_key = "remote:" + canonicalize_remote(remote)
        else:
            common = self._git("rev-parse", "--git-common-dir", required=True)
            path = Path(common)
            if not path.is_absolute():
                path = self.repository_root / path
            normalized = os.path.normcase(str(path.resolve())).replace("\\", "/")
            identity_key = "local:" + normalized
        digest = hashlib.sha256(
            b"coding-agent-project-v1\0" + identity_key.encode("utf-8")
        ).hexdigest()
        return "sha256:" + digest

    def _git(self, *arguments: str, required: bool) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.repository_root,
            check=False,
            capture_output=True,
            text=True,
        )
        value = completed.stdout.strip()
        if required and (completed.returncode != 0 or not value):
            raise RuntimeError("cannot resolve Git project identity")
        return value if completed.returncode == 0 else ""
