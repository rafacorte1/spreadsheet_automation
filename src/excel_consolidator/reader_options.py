"""Immutable format selection and CSV settings for one run."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import ConsolidationError

INPUT_FORMATS: tuple[str, ...] = ("xlsx", "xls", "csv")


@dataclass(frozen=True)
class ReaderOptions:
    """Select input formats and distinguish automatic from explicit CSV settings."""

    formats: tuple[str, ...] = INPUT_FORMATS
    csv_encoding: str | None = None
    csv_delimiter: str | None = None

    def __post_init__(self) -> None:
        """Freeze the format sequence and validate supported values."""
        formats = tuple(self.formats)
        if not formats or any(item not in INPUT_FORMATS for item in formats):
            raise ConsolidationError(
                f"key 'formats': expected one or more of {', '.join(INPUT_FORMATS)}; got {formats!r}"
            )
        if self.csv_delimiter is not None and len(self.csv_delimiter) != 1:
            raise ConsolidationError("key 'csv.delimiter': expected a str of one character")
        object.__setattr__(self, "formats", formats)
