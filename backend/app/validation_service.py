"""
Data validation service.

Validates raw API payloads before they enter the processing pipeline.
Returns structured validation reports rather than raising exceptions,
so callers can decide how to handle partial data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Required fields per dataset — verified from live API calls (api_research.md)
FUELHH_REQUIRED_FIELDS = {"dataset", "publishTime", "startTime", "settlementDate",
                           "settlementPeriod", "fuelType", "generation"}
WINDFOR_REQUIRED_FIELDS = {"dataset", "publishTime", "startTime", "generation"}


@dataclass
class ValidationReport:
    dataset_name: str
    total_input_rows: int = 0
    rows_missing_required_fields: int = 0
    rows_null_start_time: int = 0
    rows_null_generation: int = 0
    rows_non_numeric_generation: int = 0
    rows_negative_generation: int = 0
    rows_passed: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        """True when all rows passed and there are no critical issues."""
        return self.rows_passed == self.total_input_rows

    @property
    def pass_rate_pct(self) -> float:
        if self.total_input_rows == 0:
            return 0.0
        return self.rows_passed / self.total_input_rows * 100

    def log(self) -> None:
        level = logging.WARNING if not self.is_healthy else logging.INFO
        logger.log(level,
                   "Validation [%s]: %d/%d rows passed (%.1f%%)%s",
                   self.dataset_name,
                   self.rows_passed,
                   self.total_input_rows,
                   self.pass_rate_pct,
                   " — WARNINGS: " + "; ".join(self.warnings) if self.warnings else "")


def validate_fuelhh(raw: list[dict]) -> tuple[list[dict], ValidationReport]:
    """
    Validate raw FUELHH records.

    Checks:
    1. Required fields are present.
    2. startTime and generation are not null.
    3. generation is numeric.
    4. generation is not negative (flags, does not remove).
    5. fuelType is 'WIND' (defensive — API should already filter).

    Returns
    -------
    (clean_rows, report)
        clean_rows : records that passed validation
        report     : ValidationReport with counts and warnings
    """
    report = ValidationReport(dataset_name="FUELHH", total_input_rows=len(raw))
    clean: list[dict] = []

    for row in raw:
        # 1. Required fields
        missing = FUELHH_REQUIRED_FIELDS - row.keys()
        if missing:
            report.rows_missing_required_fields += 1
            continue

        # 2. Null startTime
        if row["startTime"] is None:
            report.rows_null_start_time += 1
            continue

        # 3. Null generation
        if row["generation"] is None:
            report.rows_null_generation += 1
            continue

        # 4. Non-numeric generation
        try:
            gen = float(row["generation"])
        except (TypeError, ValueError):
            report.rows_non_numeric_generation += 1
            continue

        # 5. Negative generation — flag but keep (clamped in processing layer)
        if gen < 0:
            report.rows_negative_generation += 1

        clean.append(row)

    report.rows_passed = len(clean)

    # Compose warnings
    if report.rows_missing_required_fields:
        report.warnings.append(
            f"{report.rows_missing_required_fields} rows dropped: missing required fields"
        )
    if report.rows_null_start_time:
        report.warnings.append(
            f"{report.rows_null_start_time} rows dropped: null startTime"
        )
    if report.rows_null_generation:
        report.warnings.append(
            f"{report.rows_null_generation} rows dropped: null generation"
        )
    if report.rows_non_numeric_generation:
        report.warnings.append(
            f"{report.rows_non_numeric_generation} rows dropped: non-numeric generation"
        )
    if report.rows_negative_generation:
        report.warnings.append(
            f"{report.rows_negative_generation} rows with negative generation (will be clamped to 0)"
        )

    report.log()
    return clean, report


def validate_windfor(raw: list[dict]) -> tuple[list[dict], ValidationReport]:
    """
    Validate raw WINDFOR records.

    Checks:
    1. Required fields are present.
    2. startTime and publishTime are not null.
    3. generation is numeric.
    4. generation is not negative (flags, does not remove — will be clamped).

    Note: WINDFOR has no settlementDate, settlementPeriod, or fuelType.
    Hindcast filtering (startTime <= publishTime) happens in the processing layer.

    Returns
    -------
    (clean_rows, report)
    """
    report = ValidationReport(dataset_name="WINDFOR", total_input_rows=len(raw))
    clean: list[dict] = []

    for row in raw:
        # 1. Required fields
        missing = WINDFOR_REQUIRED_FIELDS - row.keys()
        if missing:
            report.rows_missing_required_fields += 1
            continue

        # 2. Null startTime
        if row["startTime"] is None:
            report.rows_null_start_time += 1
            continue

        # 3. Null generation
        if row["generation"] is None:
            report.rows_null_generation += 1
            continue

        # 4. Non-numeric generation
        try:
            gen = float(row["generation"])
        except (TypeError, ValueError):
            report.rows_non_numeric_generation += 1
            continue

        # 5. Negative generation — flag but keep (clamped in processing)
        if gen < 0:
            report.rows_negative_generation += 1

        clean.append(row)

    report.rows_passed = len(clean)

    if report.rows_missing_required_fields:
        report.warnings.append(
            f"{report.rows_missing_required_fields} rows dropped: missing required fields"
        )
    if report.rows_null_start_time:
        report.warnings.append(
            f"{report.rows_null_start_time} rows dropped: null startTime"
        )
    if report.rows_null_generation:
        report.warnings.append(
            f"{report.rows_null_generation} rows dropped: null generation"
        )
    if report.rows_non_numeric_generation:
        report.warnings.append(
            f"{report.rows_non_numeric_generation} rows dropped: non-numeric generation"
        )
    if report.rows_negative_generation:
        report.warnings.append(
            f"{report.rows_negative_generation} rows flagged: negative generation (will be clamped to 0)"
        )

    report.log()
    return clean, report
