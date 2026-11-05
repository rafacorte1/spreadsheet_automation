"""Aceite da consolidação vertical sem alteração das entradas."""
from __future__ import annotations

import pytest

from excel_consolidator.consolidator import consolidate
from excel_consolidator.reader import ConsolidationError


def test_vertical_sorted_raw_values_and_unchanged_inputs(tmp_path, make_xlsx):
    second = make_xlsx(tmp_path / "z.xlsx", [["B", "A"], [False, "repetido"], [7, "fim"]])
    first = make_xlsx(tmp_path / "a.xlsx", [["A", "B"], ["repetido", False], ["nulo", None], ["decimal", 1.23456789]])
    before = {path: path.read_bytes() for path in (first, second)}
    result = consolidate(tmp_path)
    assert [sheet.path for sheet in result.files] == [first, second]
    assert list(result.frame.columns) == ["A", "B", "arquivo_origem"]
    assert result.frame.values.tolist() == [
        ["repetido", False, "a.xlsx"], ["nulo", None, "a.xlsx"],
        ["decimal", 1.23456789, "a.xlsx"], ["repetido", False, "z.xlsx"],
        ["fim", 7, "z.xlsx"],
    ]
    assert result.frame.iloc[1, 1] is None
    assert result.frame.iloc[0, 1] is False
    assert result.rows == sum(len(sheet.rows) for sheet in result.files)
    assert result.frame.index.tolist() == list(range(result.rows))
    assert all(path.read_bytes() == content for path, content in before.items())


def test_empty_directory(tmp_path):
    with pytest.raises(ConsolidationError, match=f"nenhum arquivo .xlsx em {tmp_path}"):
        consolidate(tmp_path)


def test_origin_collision(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "a.xlsx", [["arquivo_origem"], ["x"]])
    with pytest.raises(ConsolidationError, match="arquivo_origem"):
        consolidate(tmp_path)


def test_incompatible_columns(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "a.xlsx", [["A"], [1]])
    make_xlsx(tmp_path / "b.xlsx", [["B"], [2]])
    with pytest.raises(ConsolidationError, match="faltantes"):
        consolidate(tmp_path)
