"""Reporting errors are available even when the optional PDF extra is absent."""


class ReportError(ValueError):
    """Missing/inconsistent analysis, unsupported text, or PDF rendering failure."""
