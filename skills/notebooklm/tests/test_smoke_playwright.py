from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
REMOTE_MANAGER = SCRIPTS_DIR / "remote_manager.py"
AUTH_MANAGER = SCRIPTS_DIR / "auth_manager.py"


def _run_json(command: list[str]) -> dict:
    proc = subprocess.run(
        command,
        cwd=str(SKILL_DIR),
        check=False,
        text=True,
        capture_output=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise AssertionError(f"Command failed ({proc.returncode}): {' '.join(command)}\n{proc.stdout}\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Invalid JSON output from command: {' '.join(command)}\n{proc.stdout}") from exc


@pytest.mark.smoke
def test_remote_manager_create_list_add_delete_smoke() -> None:
    if os.environ.get("NOTEBOOKLM_E2E") != "1":
        pytest.skip("Set NOTEBOOKLM_E2E=1 to run live smoke tests")

    profile = os.environ.get("NOTEBOOKLM_SMOKE_PROFILE", "default")

    status = _run_json([
        "python3",
        str(AUTH_MANAGER),
        "status",
        "--profile",
        profile,
    ])
    if not status.get("authenticated"):
        pytest.skip(f"NotebookLM profile '{profile}' is not authenticated")

    notebook_name = f"Codex Smoke {int(time.time())}"
    created = _run_json(
        [
            "python3",
            str(REMOTE_MANAGER),
            "create-remote",
            "--name",
            notebook_name,
            "--profile",
            profile,
        ]
    )

    notebook_id = created.get("library_notebook", {}).get("id")
    assert notebook_id, created

    added = _run_json(
        [
            "python3",
            str(REMOTE_MANAGER),
            "add-source",
            "--notebook-id",
            notebook_id,
            "--text",
            f"smoke source {int(time.time())}",
            "--profile",
            profile,
        ]
    )
    assert added.get("status") == "success", added

    listed = _run_json(
        [
            "python3",
            str(REMOTE_MANAGER),
            "list-sources",
            "--notebook-id",
            notebook_id,
            "--profile",
            profile,
        ]
    )
    assert listed.get("status") == "success", listed
    assert listed.get("count", 0) >= 1, listed

    source_to_delete = listed["sources"][0]["title"]

    deleted = _run_json(
        [
            "python3",
            str(REMOTE_MANAGER),
            "delete-source",
            "--notebook-id",
            notebook_id,
            "--source-title",
            source_to_delete,
            "--all-matches",
            "--profile",
            profile,
        ]
    )
    assert deleted.get("status") == "success", deleted
