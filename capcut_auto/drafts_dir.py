"""OS별 CapCut 기본 draft 폴더 경로."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def default_drafts_dir() -> Path | None:
    system = platform.system()
    if system == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if not local_appdata:
            return None
        return Path(local_appdata) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    if system == "Darwin":
        return Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    return None
