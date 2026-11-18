"""Read delimited text without inferring cell types."""
from __future__ import annotations

import codecs
from collections.abc import Callable, Iterator
import csv
import io
from itertools import islice
from pathlib import Path

from .errors import ConsolidationError
from .reader_options import ReaderOptions

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")
_DELIMITERS = (",", ";", "\t", "|")
_SAMPLE_SIZE = 50


def _decode(path: Path, raw: bytes, explicit: str | None) -> tuple[str, str]:
    encodings = (explicit,) if explicit is not None else _ENCODINGS
    for index, encoding in enumerate(encodings, start=1):
        try:
            decoded = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            if index == len(encodings):
                position = exc.start
                if raw.startswith(codecs.BOM_UTF8) and codecs.lookup(encoding).name == "utf-8-sig":
                    position += len(codecs.BOM_UTF8)
                raise ConsolidationError(
                    f"csv {path}: cannot decode with {encoding!r} at byte {position}: {exc.reason}"
                ) from exc
        except (LookupError, UnicodeError) as exc:
            raise ConsolidationError(f"csv {path}: cannot decode with {encoding!r}: {exc}") from exc
        else:
            if explicit is None and encoding == "utf-8-sig" and not raw.startswith(codecs.BOM_UTF8):
                encoding = "utf-8"
            return decoded, encoding
    raise AssertionError("at least one CSV encoding is required")


def _records(text: str, delimiter: str) -> Iterator[list[str]]:
    with io.StringIO(text, newline="") as stream:
        yield from csv.reader(stream, delimiter=delimiter)


def _detect_delimiter(text: str) -> tuple[str, bool]:
    with io.StringIO(text, newline="") as stream:
        sample = list(islice((line for line in stream if line.rstrip("\r\n")), _SAMPLE_SIZE))
    best = _DELIMITERS[0]
    best_width = 1
    for candidate in _DELIMITERS:
        try:
            widths = {len(row) for row in csv.reader(sample, delimiter=candidate)}
        except csv.Error:
            continue
        if len(widths) == 1 and (width := widths.pop()) > best_width:
            best, best_width = candidate, width
    return best, best_width == 1


def read(
    path: Path,
    csv_options: ReaderOptions,
    *,
    report_detection: Callable[[str], None] | None = None,
) -> tuple[tuple[object, ...], list[tuple[object, ...]]]:
    """Return raw header and rows, optionally reporting the automatic choices."""
    try:
        text, encoding = _decode(path, path.read_bytes(), csv_options.csv_encoding)
        delimiter = csv_options.csv_delimiter
        used_comma_fallback = False
        if delimiter is None:
            delimiter, used_comma_fallback = _detect_delimiter(text)
        rows = (tuple(value if value != "" else None for value in row)
                for row in _records(text, delimiter))
        header = next(rows, ())
        raw_rows = list(rows)
    except (OSError, TypeError, csv.Error) as exc:
        raise ConsolidationError(f"could not read {path}: {exc}") from exc
    if report_detection is not None and (csv_options.csv_encoding is None or csv_options.csv_delimiter is None):
        message = f"csv {path}: encoding={encoding} delimiter={delimiter!r}"
        if used_comma_fallback:
            message += " (no consistent multi-column delimiter; using comma)"
        report_detection(message)
    return header, raw_rows
