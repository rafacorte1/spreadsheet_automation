"""Factories for the synthetic inputs used by the acceptance tests."""
from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from openpyxl import Workbook
import pytest


@pytest.fixture(autouse=True, scope="function")
def isolate_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep files created through relative paths inside each test's temporary directory."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def make_xlsx() -> Callable[[Path, list[list[object]]], Path]:
    def create(path: Path, rows: list[list[object]]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        for row in rows:
            workbook.active.append(row)
        workbook.save(path)
        workbook.close()
        return path
    return create
