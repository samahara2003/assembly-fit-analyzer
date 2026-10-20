"""Application I/O budgets, independent of domain and arithmetic validity."""

from typing import TYPE_CHECKING

from .inputs import ValidationError

if TYPE_CHECKING:
    from assembly_fit_analyzer.domain import AnalysisProject

MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_DIMENSIONS = 1_000
MAX_PROJECT_NAME_CHARS = 512
MAX_DIMENSION_ID_CHARS = 128
MAX_LABEL_CHARS = 8_192
MAX_DECIMAL_TEXT_CHARS = 10_032
MAX_PERSISTENCE_ERROR_CHARS = 2_000
MAX_PDF_DIMENSIONS = 250
MAX_PDF_TEXT_CHARS = 100_000


def check_text_limit(value: object, *, field: str, maximum: int) -> None:
    """Check raw text before parsing; other types remain domain validation's job."""
    if isinstance(value, str):
        if len(value) > maximum:
            raise ValidationError(field, f"exceeds the limit of {maximum} characters")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValidationError(
                field, "invalid Unicode text (not valid UTF-8)"
            ) from exc


def check_dimension_count(count: int, *, maximum: int = MAX_DIMENSIONS) -> None:
    if count > maximum:
        raise ValidationError(
            "contributions", f"exceeds the limit of {maximum} dimensions"
        )


def check_project_limits(project: "AnalysisProject") -> None:
    """Bound programmatically constructed projects at I/O/rendering boundaries."""
    check_dimension_count(len(project.contributions))
    check_text_limit(project.name, field="name", maximum=MAX_PROJECT_NAME_CHARS)
    for index, item in enumerate(project.contributions):
        location = f"contributions[{index}]"
        check_text_limit(
            item.dimension_id,
            field=f"{location}.dimension_id",
            maximum=MAX_DIMENSION_ID_CHARS,
        )
        check_text_limit(item.label, field=f"{location}.label", maximum=MAX_LABEL_CHARS)
        for field in ("nominal", "lower_deviation", "upper_deviation"):
            check_text_limit(
                str(getattr(item, field)),
                field=f"{location}.{field}",
                maximum=MAX_DECIMAL_TEXT_CHARS,
            )
    if project.acceptance_limits is not None:
        for field in ("lower", "upper"):
            check_text_limit(
                str(getattr(project.acceptance_limits, field)),
                field=f"acceptance_limits.{field}",
                maximum=MAX_DECIMAL_TEXT_CHARS,
            )
