"""Aceite da publicação atômica e limpeza dos temporários."""
from __future__ import annotations

import pandas as pd
from openpyxl import load_workbook
import pytest

from excel_consolidator import writer
from excel_consolidator.reader import ConsolidationError


def test_workbook_values_and_created_directory(tmp_path):
    output = tmp_path / "new" / "nested" / "result.xlsx"
    frame = pd.DataFrame([["Ana", 1.25, True, None], ["Bia", 2, False, "fim"]], columns=["nome", "valor", "ativo", "opcional"], dtype=object)
    writer.write_atomic(frame, output)
    workbook = load_workbook(output, data_only=True)
    try:
        assert workbook.sheetnames == ["consolidado"]
        assert list(workbook.active.values) == [tuple(frame.columns), *map(tuple, frame.values.tolist())]
    finally:
        workbook.close()
    assert list(output.parent.iterdir()) == [output]


@pytest.mark.parametrize("stage", ["serialize", "replace"])
def test_failure_preserves_previous_output_and_cleans_temp(tmp_path, monkeypatch, stage):
    output = tmp_path / "result.xlsx"
    writer.write_atomic(pd.DataFrame({"A": [1]}), output)
    before = output.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("falha forçada")

    if stage == "replace":
        def fail_replace(source, destination):
            assert source.parent == destination.parent
            workbook = load_workbook(source)
            workbook.close()
            fail()
        monkeypatch.setattr(writer.os, "replace", fail_replace)
    else:
        original = pd.DataFrame.to_excel
        def fail_serialization(self, *args, **kwargs):
            original(self, *args, **kwargs)
            fail()
        monkeypatch.setattr(pd.DataFrame, "to_excel", fail_serialization)
    with pytest.raises(ConsolidationError, match=str(output)):
        writer.write_atomic(pd.DataFrame({"A": [2]}), output)
    assert output.read_bytes() == before
    assert list(tmp_path.iterdir()) == [output]


def test_directory_creation_failure_is_controlled(tmp_path):
    parent = tmp_path / "file"
    parent.write_bytes(b"existing")
    output = parent / "result.xlsx"
    with pytest.raises(ConsolidationError, match=str(output)):
        writer.write_atomic(pd.DataFrame({"A": [1]}), output)
    assert parent.read_bytes() == b"existing"
