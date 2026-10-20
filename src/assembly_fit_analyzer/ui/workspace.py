"""Decimal-safe editor adapters and immutable rerun snapshots; no UI imports."""

import re
from dataclasses import dataclass
from typing import Any, Literal

from assembly_fit_analyzer.calculations import WorstCaseResult
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.domain.interpretation import (
    range_description as range_description,
)
from assembly_fit_analyzer.persistence import PersistenceError, loads_project
from assembly_fit_analyzer.persistence.json_project import check_json_size
from assembly_fit_analyzer.validation import ValidationError
from assembly_fit_analyzer.validation.resources import (
    MAX_DECIMAL_TEXT_CHARS,
    MAX_DIMENSION_ID_CHARS,
    MAX_LABEL_CHARS,
    MAX_PROJECT_NAME_CHARS,
    check_dimension_count,
    check_project_limits,
    check_text_limit,
)

FIELDS = (
    "dimension_id",
    "label",
    "nominal",
    "lower_deviation",
    "upper_deviation",
    "sign",
)


def literal_message(message: str) -> str:
    """Render diagnostics as literal code; Markdown escaping still autolinks URLs."""
    safe = message.encode("utf-8", "backslashreplace").decode("utf-8")
    # A longer fence prevents arbitrary input from closing the literal block.
    fence = "`" * max(3, max(map(len, re.findall(r"`+", safe)), default=0) + 1)
    return f"{fence}text\n{safe}\n{fence}"


@dataclass(frozen=True)
class Draft:
    """Raw input snapshot: incomplete and invalid edits must survive reruns."""

    name: str
    unit: Literal["mm", "in"]
    lower: str
    upper: str
    rows: tuple[tuple[Any, ...], ...]


def new_draft() -> Draft:
    return Draft("Untitled project", "mm", "", "", (("D1", "", "", "0", "0", "+1"),))


def editor_rows(draft: Draft) -> list[dict[str, Any]]:
    return [dict(zip(FIELDS, row, strict=True)) for row in draft.rows]


def capture_draft(
    name: str,
    unit: Literal["mm", "in"],
    lower: str,
    upper: str,
    rows: list[dict[str, Any]],
) -> Draft:
    return Draft(
        name,
        unit,
        lower,
        upper,
        tuple(tuple(row.get(field) for field in FIELDS) for row in rows),
    )


def draft_from_project(project: AnalysisProject) -> Draft:
    check_project_limits(project)
    return Draft(
        project.name,
        project.unit,
        str(project.acceptance_limits.lower) if project.acceptance_limits else "",
        str(project.acceptance_limits.upper) if project.acceptance_limits else "",
        tuple(
            (
                item.dimension_id,
                item.label,
                str(item.nominal),
                str(item.lower_deviation),
                str(item.upper_deviation),
                "+1" if item.sign == 1 else "-1",
            )
            for item in project.contributions
        ),
    )


def project_from_draft(draft: Draft) -> AnalysisProject:
    """Delegate engineering validation to domain constructors, adding row context."""
    check_dimension_count(len(draft.rows))
    check_text_limit(draft.name, field="name", maximum=MAX_PROJECT_NAME_CHARS)
    for field, text in (("lower", draft.lower), ("upper", draft.upper)):
        check_text_limit(
            text, field=f"acceptance_limits.{field}", maximum=MAX_DECIMAL_TEXT_CHARS
        )
    dimensions = []
    for index, row in enumerate(editor_rows(draft), start=1):
        try:
            for field, maximum in (
                ("dimension_id", MAX_DIMENSION_ID_CHARS),
                ("label", MAX_LABEL_CHARS),
                ("nominal", MAX_DECIMAL_TEXT_CHARS),
                ("lower_deviation", MAX_DECIMAL_TEXT_CHARS),
                ("upper_deviation", MAX_DECIMAL_TEXT_CHARS),
            ):
                check_text_limit(row[field], field=field, maximum=maximum)
            sign_text = row.pop("sign")
            if sign_text not in ("+1", "-1"):
                raise ValidationError("sign", "select +1 or -1")
            sign = 1 if sign_text == "+1" else -1
            dimensions.append(DimensionContribution(**row, sign=sign))
        except ValidationError as exc:
            raise ValidationError(
                exc.field, f"row {index}: {exc}", dimension_id=exc.dimension_id
            ) from exc
    lower_blank = isinstance(draft.lower, str) and not draft.lower.strip()
    upper_blank = isinstance(draft.upper, str) and not draft.upper.strip()
    if lower_blank != upper_blank:
        field = "lower" if lower_blank else "upper"
        raise ValidationError(
            f"acceptance_limits.{field}",
            "provide both functional limits or leave both blank for analysis only",
        )
    return AnalysisProject(
        name=draft.name,
        unit=draft.unit,
        contributions=dimensions,
        acceptance_limits=(
            None
            if lower_blank and upper_blank
            else AcceptanceLimits(draft.lower, draft.upper)
        ),
    )


def project_from_upload(data: bytes) -> AnalysisProject:
    check_json_size(len(data))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PersistenceError("Upload must be a UTF-8 JSON project file") from exc
    return loads_project(text)


def add_dimension(draft: Draft) -> Draft:
    """Append a blank row with an unused suggested ID, preserving all raw edits."""
    used = {str(row[0]).strip() for row in draft.rows}
    index = 1
    while f"D{index}" in used:
        index += 1
    row = (f"D{index}", "", "", "0", "0", "+1")
    return Draft(draft.name, draft.unit, draft.lower, draft.upper, draft.rows + (row,))


def remove_dimensions(draft: Draft, indices: list[int]) -> Draft:
    """Remove selected editor positions without parsing or normalizing text."""
    if any(
        type(index) is not int or not 0 <= index < len(draft.rows) for index in indices
    ):
        raise ValueError("Selected dimension row is out of range")
    removed = set(indices)
    return Draft(
        draft.name,
        draft.unit,
        draft.lower,
        draft.upper,
        tuple(row for index, row in enumerate(draft.rows) if index not in removed),
    )


def contribution_summary(result: WorstCaseResult) -> list[dict[str, str]]:
    """Present exact trace values; totals come directly from the engine result."""
    rows = [
        {
            "Dimension": f"{trace.dimension.dimension_id} · {trace.dimension.label}",
            "Minimum": str(trace.minimum_contribution),
            "Nominal": str(trace.nominal_contribution),
            "Maximum": str(trace.maximum_contribution),
        }
        for trace in result.traces
    ]
    rows.append(
        {
            "Dimension": "Total",
            "Minimum": str(result.minimum),
            "Nominal": str(result.nominal),
            "Maximum": str(result.maximum),
        }
    )
    return rows
