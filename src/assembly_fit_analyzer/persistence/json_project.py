"""Strict versioned JSON documents and atomic local file replacement."""

import json
import os
import tempfile
from decimal import Decimal, DecimalException, localcontext
from pathlib import Path
from typing import Any

from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.validation import ValidationError
from assembly_fit_analyzer.validation.resources import (
    MAX_DECIMAL_TEXT_CHARS,
    MAX_DIMENSION_ID_CHARS,
    MAX_JSON_BYTES,
    MAX_LABEL_CHARS,
    MAX_PERSISTENCE_ERROR_CHARS,
    MAX_PROJECT_NAME_CHARS,
    check_dimension_count,
    check_project_limits,
    check_text_limit,
)

SCHEMA_VERSION = 2
_PROJECT_FIELDS = {"name", "unit", "contributions", "acceptance_limits"}
_DIMENSION_FIELDS = {
    "dimension_id",
    "label",
    "nominal",
    "lower_deviation",
    "upper_deviation",
    "sign",
}
_DECIMAL_FIELDS = ("nominal", "lower_deviation", "upper_deviation")


class PersistenceError(ValueError):
    """A malformed project document or a failed local file operation."""

    def __init__(self, message: str) -> None:
        # Paths and decoder diagnostics can also contain surrogate escapes.
        # Keep every public diagnostic UTF-8-safe and bounded for browser display.
        safe = str(message).encode("utf-8", "backslashreplace").decode("utf-8")
        if len(safe) > MAX_PERSISTENCE_ERROR_CHARS:
            safe = safe[: MAX_PERSISTENCE_ERROR_CHARS - 1] + "…"
        super().__init__(safe)


def check_json_size(size: int) -> None:
    """Reject oversized bytes before decoding or reading a complete file."""
    if size > MAX_JSON_BYTES:
        raise PersistenceError(
            f"document: exceeds the limit of {MAX_JSON_BYTES} bytes (8 MiB); "
            "use a smaller project file"
        )


def _object(value: Any, fields: set[str], location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PersistenceError(f"{location}: expected a JSON object")
    missing = fields - value.keys()
    unknown = value.keys() - fields
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing required fields: {', '.join(sorted(missing))}")
        if unknown:
            details.append(f"unknown fields: {', '.join(sorted(unknown))}")
        raise PersistenceError(f"{location}: {'; '.join(details)}")
    return value


def _string(value: Any, location: str, maximum: int | None = None) -> str:
    if not isinstance(value, str):
        raise PersistenceError(f"{location}: expected a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PersistenceError(f"{location}: invalid Unicode text") from exc
    if maximum is not None:
        try:
            check_text_limit(value, field=location, maximum=maximum)
        except ValidationError as exc:
            raise PersistenceError(str(exc)) from exc
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        _string(key, "document key")
        if key in result:
            raise PersistenceError(f"duplicate JSON key {key!r}; keep only one value")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise PersistenceError(
        f"invalid JSON constant {value!r}; use finite decimal strings"
    )


def loads_project(text: str) -> AnalysisProject:
    """Decode strict V1/V2 JSON and reconstruct through domain validation."""
    if not isinstance(text, str):
        raise PersistenceError("document: expected JSON text as a string")
    check_json_size(len(text))
    try:
        check_json_size(len(text.encode("utf-8")))
    except UnicodeEncodeError as exc:
        raise PersistenceError("document: invalid Unicode text") from exc
    try:
        data = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_float=Decimal,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise PersistenceError(
            f"malformed JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except (ValueError, RecursionError, DecimalException) as exc:
        if isinstance(exc, PersistenceError):
            raise
        raise PersistenceError(f"document: cannot decode JSON: {exc}") from exc
    envelope = _object(data, {"schema_version", "project"}, "document")
    version = envelope["schema_version"]
    if type(version) is not int or version not in (1, SCHEMA_VERSION):
        raise PersistenceError(
            f"schema_version: unsupported version {version!r}; expected integer 1 or 2"
        )
    project = _object(envelope["project"], _PROJECT_FIELDS, "project")
    name = _string(project["name"], "project.name", MAX_PROJECT_NAME_CHARS)
    unit = _string(project["unit"], "project.unit")
    raw_items = project["contributions"]
    if not isinstance(raw_items, list):
        raise PersistenceError("project.contributions: expected a JSON array")
    try:
        check_dimension_count(len(raw_items))
    except ValidationError as exc:
        raise PersistenceError(f"project: {exc}") from exc
    dimensions = []
    for index, raw in enumerate(raw_items):
        location = f"project.contributions[{index}]"
        item = _object(raw, _DIMENSION_FIELDS, location)
        dimension_id = _string(
            item["dimension_id"], f"{location}.dimension_id", MAX_DIMENSION_ID_CHARS
        )
        location += f" (dimension {dimension_id!r})"
        label = _string(item["label"], f"{location}.label", MAX_LABEL_CHARS)
        values = {
            field: _string(item[field], f"{location}.{field}", MAX_DECIMAL_TEXT_CHARS)
            for field in _DECIMAL_FIELDS
        }
        try:
            dimensions.append(
                DimensionContribution(
                    dimension_id=dimension_id, label=label, sign=item["sign"], **values
                )
            )
        except ValidationError as exc:
            raise PersistenceError(f"{location}: {exc}") from exc
    acceptance = None
    if version == 1 or project["acceptance_limits"] is not None:
        limits = _object(
            project["acceptance_limits"],
            {"lower", "upper"},
            "project.acceptance_limits",
        )
        lower = _string(
            limits["lower"], "project.acceptance_limits.lower", MAX_DECIMAL_TEXT_CHARS
        )
        upper = _string(
            limits["upper"], "project.acceptance_limits.upper", MAX_DECIMAL_TEXT_CHARS
        )
        try:
            acceptance = AcceptanceLimits(lower, upper)
        except ValidationError as exc:
            raise PersistenceError(f"project: {exc}") from exc
    try:
        return AnalysisProject(
            name=name,
            unit=unit,
            contributions=dimensions,
            acceptance_limits=acceptance,
        )
    except ValidationError as exc:
        raise PersistenceError(f"project: {exc}") from exc


def dumps_project(project: AnalysisProject) -> str:
    """Encode inputs deterministically, preserving Decimal tuples via str()."""
    if not isinstance(project, AnalysisProject):
        raise PersistenceError("project: expected an AnalysisProject")
    try:
        check_project_limits(project)
    except ValidationError as exc:
        raise PersistenceError(str(exc)) from exc
    # Decimal.__str__ uses the context capitalization setting for exponents.
    with localcontext(capitals=1):
        data = {
            "schema_version": SCHEMA_VERSION,
            "project": {
                "name": project.name,
                "unit": project.unit,
                "contributions": [
                    {
                        "dimension_id": item.dimension_id,
                        "label": item.label,
                        "nominal": str(item.nominal),
                        "lower_deviation": str(item.lower_deviation),
                        "upper_deviation": str(item.upper_deviation),
                        "sign": item.sign,
                    }
                    for item in project.contributions
                ],
                "acceptance_limits": (
                    {
                        "lower": str(project.acceptance_limits.lower),
                        "upper": str(project.acceptance_limits.upper),
                    }
                    if project.acceptance_limits is not None
                    else None
                ),
            },
        }
    encoder = json.JSONEncoder(
        ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
    )
    # Domain text may originate outside JSON. Reject unpaired surrogates before
    # opening any files, rather than producing a document that UTF-8 cannot store.
    chunks = []
    size = 1  # Final LF is part of the file budget.
    try:
        for chunk in encoder.iterencode(data):
            size += len(chunk.encode("utf-8"))
            check_json_size(size)
            chunks.append(chunk)
    except UnicodeEncodeError as exc:
        raise PersistenceError("project: text cannot be encoded as UTF-8") from exc
    return "".join(chunks) + "\n"


def _path(path: str | os.PathLike[str]) -> Path:
    try:
        return Path(path)
    except (TypeError, ValueError, OSError) as exc:
        raise PersistenceError(
            f"path: expected a valid local file path: {exc}"
        ) from exc


def load_project(path: str | os.PathLike[str]) -> AnalysisProject:
    """Read a UTF-8 project file, reporting file and document errors uniformly."""
    source = _path(path)
    try:
        with source.open("rb") as stream:
            data = stream.read(MAX_JSON_BYTES + 1)
        check_json_size(len(data))
        return loads_project(data.decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise PersistenceError(f"Cannot load project '{source}': {exc}") from exc


def save_project(project: AnalysisProject, path: str | os.PathLike[str]) -> None:
    """Write and fsync a same-directory temp file, then atomically replace path.

    Parent directories must already exist. No calculation results are saved.
    """
    data = dumps_project(project).encode("utf-8")
    destination = _path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            if stream.write(data) != len(data):
                raise OSError("incomplete write to temporary project file")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except (OSError, ValueError) as exc:
        message = f"Cannot save project '{destination}': {exc}"
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                message += (
                    f"; could not remove temporary file '{temporary}': {cleanup_error}"
                )
        raise PersistenceError(message) from exc
