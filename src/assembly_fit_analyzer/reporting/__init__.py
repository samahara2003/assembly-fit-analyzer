"""Deterministic engineering reports; PDF dependencies load only when requested."""

from datetime import datetime

from assembly_fit_analyzer.calculations import WorstCaseResult

from .errors import ReportError

__all__ = ["ReportError", "generate_pdf_report"]


def generate_pdf_report(
    result: WorstCaseResult, *, generated_at: datetime | None = None
) -> bytes:
    """Return PDF bytes for a complete analyze_project result.

    Same input, timestamp, and software versions produce identical bytes.
    No current clock is read. Pass an aware datetime to record an issue time.
    """
    try:
        from .pdf import generate_pdf_report as generate
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("reportlab"):
            raise ReportError(
                "PDF reporting requires installation with .[reports] or .[ui]"
            ) from exc
        raise
    return generate(result, generated_at=generated_at)
