# Excel Consolidator: Specification v0.1

## Objective

Build a Python CLI tool that consolidates `.xlsx` files from a folder vertically, preserving the origin of every row.

## Architecture

Python >=3.11; pandas, openpyxl; pytest. Package `src/excel_consolidator` with `cli.py`, `reader.py`, `consolidator.py`, `writer.py`. Folders `data/input` and `data/output`. No APIs, no database, no UI.

## Roadmap (mandatory gates)

- Sprint 1: MVP for reading, structural validation and export.
- Sprint 2: data quality (nulls, duplicates, standardisation and inconsistency report), only after explicit approval.
- Sprint 3: configuration, logs and recurring execution, only after explicit approval.

## Sprint 1 requirements

1. Discover `.xlsx` files directly in `data/input`, in alphabetical order; ignore `~$*`.
2. Read only the first sheet of each file.
3. Require headers that are non-empty, unique and identical across files, regardless of order; compare names literally, without normalisation.
4. Reorder columns to the order of the first file; concatenate vertically without deduplicating, with an extra `source_file` column holding the file name.
5. Reject input that already has a `source_file` column, to avoid a collision.
6. Export `data/output/consolidated.xlsx` with one sheet, only after all files are validated; write to a temporary file in the output directory and replace atomically at the end, so a previous result is not overwritten on error.
7. Report on the terminal the total number of files and rows and the output path.
8. If there are no files, or a file is corrupted, has no header, has no data rows or has incompatible columns, exit with a non-zero code and a useful message.
9. Do not modify the input files.

## Tests and acceptance for Sprint 1

- Two files with the same columns in different orders produce all rows and the correct `source_file`.
- Temporary files are ignored.
- An empty directory, a corrupted file, incompatible headers, duplicate headers, a `source_file` collision and a file with no records each produce a controlled error.
- The previous result stays intact after a failure.
- Automated tests via pytest pass; the CLI command is demonstrated with synthetic data.
- README contains installation, usage, limitations and examples.

## Limits

No header normalisation, deduplication, value validation, `.xls` or `.csv` processing, scheduling, graphical interface or email sending in Sprint 1.

## Definition of done

Working code, tests executed, documentation, a demonstration with synthetic data and a final Hermes report with evidence. User approval is required to start Sprint 2.
