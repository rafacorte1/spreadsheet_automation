"""Layout e totais do relatório de qualidade."""
from pathlib import Path

from excel_consolidator.reader import SheetData
from excel_consolidator.quality import DuplicateReport, QualityOptions, standardize
from excel_consolidator.report import REPORT_COLUMNS, QualitySummary, build_report, count_nulls, summarize


def test_exact_layout_and_summary():
    sheets = [SheetData(Path(name), ("B", "A"), ((" x ", None),)) for name in ("z.xlsx", "a.xlsx")]
    options = QualityOptions(trim_text=True)
    results = [standardize(sheet, options) for sheet in sheets]
    report = build_report([r.sheet for r in results], {r.sheet.path.name: r.stats for r in results},
                          DuplicateReport(1, 1, "linhas_identicas"), options)
    expected = [("resumo", name, "", "linhas_lidas", 1) for name in ("a.xlsx", "z.xlsx")]
    expected += [("nulos", name, col, "nulos", count) for name in ("a.xlsx", "z.xlsx") for col, count in (("B", 0), ("A", 1))]
    expected += [("padronizacao", name, col, metric, value) for name in ("a.xlsx", "z.xlsx")
                 for col, count in (("B", 1), ("A", 0))
                 for metric, value in (("alterados_trim_texto", count), ("falhas_trim_texto", 0))]
    expected += [("duplicados", "", "", metric, value) for metric, value in
                 (("modo", "linhas_identicas"), ("linhas_duplicadas", 1), ("linhas_removidas", 1))]
    assert tuple(report.columns) == REPORT_COLUMNS
    assert list(report.itertuples(index=False, name=None)) == expected
    assert summarize(report) == QualitySummary(2, 1, 1, 2)


def test_nulls_only_data_and_no_inactive_rules():
    sheet = SheetData(Path("a.xlsx"), ("A", "arquivo_origem"), ((None, None), ("   ", ""), ("", ""), (0, None)))
    assert count_nulls(sheet) == {"A": 3}
    report = build_report([sheet], {}, DuplicateReport(0, 0, "linhas_identicas"), QualityOptions())
    assert report.secao.tolist() == ["resumo", "nulos", "duplicados", "duplicados", "duplicados"]
    assert summarize(report) == QualitySummary(3, 0, 0, 0)


def test_counts_each_active_rule_separately():
    options = QualityOptions(trim_text=True, normalize_numbers=True, dates_iso=True)
    result = standardize(SheetData(Path("a.xlsx"), ("A",), ((" 007 ",), ("01/02/2024",), ("no",))), options)
    report = build_report([result.sheet], {"a.xlsx": result.stats}, DuplicateReport(0, 0, "linhas_identicas"), options)
    metrics = report[report.secao == "padronizacao"].set_index("metrica").valor.to_dict()
    assert metrics == {"alterados_trim_texto": 1, "falhas_trim_texto": 0,
                       "alterados_normalizar_numeros": 1, "falhas_normalizar_numeros": 1,
                       "alterados_datas_iso": 1, "falhas_datas_iso": 1}
    assert summarize(report).changed == 3
