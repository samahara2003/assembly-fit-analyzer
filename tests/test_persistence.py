"""Strict schema, exact Decimal round trips, and atomic file failure behavior."""

import json
import os
from contextlib import contextmanager
from decimal import localcontext

import pytest

from assembly_fit_analyzer.calculations import analyze_project
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.persistence import (
    SCHEMA_VERSION,
    PersistenceError,
    dumps_project,
    json_project,
    load_project,
    loads_project,
    save_project,
)


@pytest.fixture
def project():
    return AnalysisProject(
        "Ajuste — análisis 日本語",
        "mm",
        [
            DimensionContribution("B", "Carcasa", "10.0000", "-0.100", "0.2000", 1),
            DimensionContribution("A", "Inserto", "11.000", "0.000", "0.100", -1),
            DimensionContribution("C", "Espaciador", "0.1000", "-0.1000", "0.0000", 1),
        ],
        AcceptanceLimits("-1.2000", "-0.7000"),
    )


@pytest.fixture
def document(project):
    return json.loads(dumps_project(project))


def assert_decimal_tuples_equal(before, after):
    for left, right in zip(before.contributions, after.contributions, strict=True):
        for field in ("nominal", "lower_deviation", "upper_deviation"):
            assert getattr(left, field).as_tuple() == getattr(right, field).as_tuple()
    for field in ("lower", "upper"):
        assert (
            getattr(before.acceptance_limits, field).as_tuple()
            == getattr(after.acceptance_limits, field).as_tuple()
        )


def test_round_trip_exactness_order_and_engine_integration(project, tmp_path):
    path = tmp_path / "ajuste 日本語.json"
    save_project(project, path)
    restored = load_project(path)
    assert restored == project
    assert [item.dimension_id for item in restored.contributions] == ["B", "A", "C"]
    assert_decimal_tuples_equal(project, restored)
    assert analyze_project(restored) == analyze_project(project)
    assert restored.acceptance_limits.lower < 0
    assert loads_project(dumps_project(project)) == project
    assert load_project(str(path)) == project


def test_schema_and_decimal_strings(project, document):
    assert set(document) == {"schema_version", "project"}
    assert document["schema_version"] == SCHEMA_VERSION == 2
    assert set(document["project"]) == {
        "name",
        "unit",
        "contributions",
        "acceptance_limits",
    }
    assert document["project"]["name"] == project.name
    item = document["project"]["contributions"][0]
    assert item == {
        "dimension_id": "B",
        "label": "Carcasa",
        "nominal": "10.0000",
        "lower_deviation": "-0.100",
        "upper_deviation": "0.2000",
        "sign": 1,
    }
    assert document["project"]["acceptance_limits"] == {
        "lower": "-1.2000",
        "upper": "-0.7000",
    }


def test_deterministic_utf8_and_overwrite(project, tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    save_project(project, first)
    save_project(project, second)
    expected = dumps_project(project).encode("utf-8")
    assert first.read_bytes() == second.read_bytes() == expected
    assert expected.endswith(b"\n") and b"\r" not in expected
    assert "日本語" in expected.decode("utf-8")
    assert b"\\u65e5" not in expected
    first.write_text("old contents", encoding="utf-8")
    save_project(project, first)
    assert first.read_bytes() == expected
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "first.json",
        "second.json",
    ]
    assert dumps_project(loads_project(dumps_project(project))) == dumps_project(
        project
    )


@pytest.mark.parametrize("nominal", ["1.2300", "1.2300E+100", "1E-100", "-0.000"])
def test_decimal_scale_exponent_signed_zero_and_context(nominal):
    project = AnalysisProject(
        "Exact",
        "in",
        [DimensionContribution("A", "Part", nominal, "-0.00", "0.000", -1)],
        AcceptanceLimits("-1.00000E+200", "0.00000"),
    )
    with localcontext() as context:
        context.prec = 1
        context.Emax, context.Emin = 1, -1
        for signal in context.traps:
            context.traps[signal] = True
        context.capitals = 0
        text = dumps_project(project)
        context.capitals = 1
        assert text == dumps_project(project)
        restored = loads_project(text)
        assert_decimal_tuples_equal(project, restored)
        assert not any(context.flags.values())


def section(document, location):
    if location == "document":
        return document
    if location == "project":
        return document["project"]
    if location == "dimension":
        return document["project"]["contributions"][0]
    return document["project"]["acceptance_limits"]


SCHEMA_FIELDS = {
    "document": ("schema_version", "project"),
    "project": ("name", "unit", "contributions", "acceptance_limits"),
    "dimension": (
        "dimension_id",
        "label",
        "nominal",
        "lower_deviation",
        "upper_deviation",
        "sign",
    ),
    "limits": ("lower", "upper"),
}


@pytest.mark.parametrize(
    ("location", "field"),
    [
        (location, field)
        for location, fields in SCHEMA_FIELDS.items()
        for field in fields
    ],
)
def test_missing_fields(document, location, field):
    del section(document, location)[field]
    with pytest.raises(PersistenceError, match=f"missing required fields: {field}"):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("location", SCHEMA_FIELDS)
def test_unknown_fields(document, location):
    section(document, location)["unexpected"] = 0
    with pytest.raises(PersistenceError, match="unknown fields: unexpected"):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("version", [None, True, False, "1", 1.0, 0, -1, 3, {}, []])
def test_unsupported_versions(document, version):
    document["schema_version"] = version
    with pytest.raises(PersistenceError, match="schema_version.*expected integer 1"):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("root", [None, [], 1, True, "project"])
def test_invalid_root(root):
    with pytest.raises(PersistenceError, match="document: expected a JSON object"):
        loads_project(json.dumps(root))


@pytest.mark.parametrize(
    "location", ["project", "contributions", "dimension", "limits"]
)
@pytest.mark.parametrize("value", [None, "invalid", 1, True])
def test_invalid_structures(document, location, value):
    document["schema_version"] = 1  # V1 still requires a limits object.
    if location == "project":
        document["project"] = value
    elif location == "dimension":
        document["project"]["contributions"][0] = value
    else:
        field = "acceptance_limits" if location == "limits" else location
        document["project"][field] = value
    with pytest.raises(PersistenceError, match="expected a JSON"):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("field", ["nominal", "lower_deviation", "upper_deviation"])
@pytest.mark.parametrize(
    "value", [1, 0.1, True, None, [], {}, "NaN", "Infinity", "sNaN", "bad", ""]
)
def test_invalid_dimension_decimals(document, field, value):
    document["project"]["contributions"][0][field] = value
    with pytest.raises(PersistenceError) as caught:
        loads_project(json.dumps(document))
    assert field in str(caught.value)
    assert "dimension 'B'" in str(caught.value)


@pytest.mark.parametrize("field", ["lower", "upper"])
@pytest.mark.parametrize("value", [1, 0.1, False, None, "NaN", "-Infinity", "bad"])
def test_invalid_acceptance_decimals(document, field, value):
    document["project"]["acceptance_limits"][field] = value
    with pytest.raises(PersistenceError, match=f"acceptance_limits.{field}"):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("sign", [True, False, 0, 2, -2, "1", 1.0, None, []])
def test_invalid_signs(document, sign):
    document["project"]["contributions"][0]["sign"] = sign
    with pytest.raises(PersistenceError, match="sign"):
        loads_project(json.dumps(document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nominal", "-1"),
        ("lower_deviation", "0.3"),
        ("lower_deviation", "-10.0001"),
        ("dimension_id", ""),
        ("label", " "),
        ("label", 1),
    ],
)
def test_domain_dimension_rules_reused(document, field, value):
    document["project"]["contributions"][0][field] = value
    with pytest.raises(PersistenceError, match=field):
        loads_project(json.dumps(document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", " "),
        ("name", None),
        ("unit", "cm"),
        ("unit", 1),
        ("contributions", []),
    ],
)
def test_domain_project_rules_reused(document, field, value):
    document["project"][field] = value
    with pytest.raises(PersistenceError, match=field):
        loads_project(json.dumps(document))


def test_duplicate_ids_and_invalid_acceptance_interval(document):
    document["project"]["contributions"][1]["dimension_id"] = " B "
    with pytest.raises(PersistenceError, match="dimension 'B'.*duplicate ID"):
        loads_project(json.dumps(document))
    document["project"]["contributions"][1]["dimension_id"] = "A"
    document["project"]["acceptance_limits"]["lower"] = "1"
    with pytest.raises(
        PersistenceError, match="acceptance_limits.lower.*must be <= upper"
    ):
        loads_project(json.dumps(document))


@pytest.mark.parametrize(
    "text", ["", "{", '{"a": 1,}', "{} {}", "// comment", "\ufeff{}"]
)
def test_malformed_json(text):
    with pytest.raises(PersistenceError, match="malformed JSON at line .*column"):
        loads_project(text)


@pytest.mark.parametrize(
    "text",
    [
        '{"schema_version": 1, "schema_version": 2}',
        '{"project": {"name": "one", "name": "two"}}',
        '{"a": {"sign": 1, "sign": -1}}',
        '{"a": {"name": "one", "na\\u006de": "two"}}',
    ],
)
def test_duplicate_json_keys(text):
    with pytest.raises(PersistenceError, match="duplicate JSON key"):
        loads_project(text)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonstandard_json_constants(constant):
    with pytest.raises(PersistenceError, match="invalid JSON constant"):
        loads_project('{"schema_version": ' + constant + "}")


def test_huge_json_float_exponent_is_wrapped():
    with pytest.raises(PersistenceError):
        loads_project('{"schema_version": 1e9999999999999999999999999999999999999}')


def test_unpaired_surrogate_rejected(document):
    document["project"]["name"] = "bad\ud800"
    with pytest.raises(PersistenceError, match="name: invalid Unicode"):
        loads_project(json.dumps(document))


def test_persistence_does_not_apply_calculation_resource_limits():
    project = AnalysisProject(
        "Large valid input",
        "mm",
        [DimensionContribution("A", "Part", "1e10001", 0, 0, 1)],
        AcceptanceLimits(0, "1e10002"),
    )
    assert loads_project(dumps_project(project)) == project


def test_read_permission_error_includes_path(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(type(tmp_path), "open", denied)
    with pytest.raises(
        PersistenceError, match="Cannot load project.*private.json.*permission denied"
    ):
        load_project(tmp_path / "private.json")


@pytest.mark.parametrize("text", [None, b"{}", {}, 1])
def test_loads_rejects_nontext(text):
    with pytest.raises(PersistenceError, match="expected JSON text"):
        loads_project(text)


@pytest.mark.parametrize("path", [None, 1, b"path"])
def test_invalid_paths(project, path):
    with pytest.raises(PersistenceError, match="path"):
        load_project(path)
    with pytest.raises(PersistenceError, match="path"):
        save_project(project, path)


def test_read_errors_and_file_context(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(
        PersistenceError, match="Cannot load project.*missing.json"
    ) as caught:
        load_project(missing)
    assert isinstance(caught.value.__cause__, OSError)
    with pytest.raises(PersistenceError, match="Cannot load project"):
        load_project(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff\xfe")
    with pytest.raises(PersistenceError, match="Cannot load project.*bad.json"):
        load_project(bad)
    bad.write_text('{"schema_version": 3, "project": {}}', encoding="utf-8")
    with pytest.raises(PersistenceError, match="bad.json.*schema_version"):
        load_project(bad)


def test_missing_parent_and_directory_destination(project, tmp_path):
    with pytest.raises(PersistenceError, match="Cannot save project"):
        save_project(project, tmp_path / "missing" / "project.json")
    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(PersistenceError, match="Cannot save project"):
        save_project(project, directory)
    assert list(tmp_path.iterdir()) == [directory]


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "stage", ["create", "write", "short_write", "flush", "fsync", "replace"]
)
def test_atomic_save_failure_preserves_target_and_cleans_temp(
    project, tmp_path, monkeypatch, existing, stage
):
    path = tmp_path / "project.json"
    original = b"existing project contents"
    if existing:
        path.write_bytes(original)
    factory = json_project.tempfile.NamedTemporaryFile

    def fail(*args, **kwargs):
        raise OSError("simulated disk or permission failure")

    class FailingStream:
        def __init__(self, stream):
            self.stream = stream
            self.name = stream.name

        def write(self, data):
            if stage in ("write", "short_write"):
                self.stream.write(data[:5])
                if stage == "short_write":
                    return 5
                fail()
            return self.stream.write(data)

        def flush(self):
            if stage == "flush":
                fail()
            self.stream.flush()

        def fileno(self):
            return self.stream.fileno()

    @contextmanager
    def temporary(**kwargs):
        with factory(**kwargs) as stream:
            yield FailingStream(stream)

    if stage == "create":
        monkeypatch.setattr(json_project.tempfile, "NamedTemporaryFile", fail)
    elif stage in ("write", "short_write", "flush"):
        monkeypatch.setattr(json_project.tempfile, "NamedTemporaryFile", temporary)
    else:
        monkeypatch.setattr(json_project.os, stage, fail)
    with pytest.raises(PersistenceError, match="Cannot save project.*project.json"):
        save_project(project, path)
    if existing:
        assert path.read_bytes() == original
        assert list(tmp_path.iterdir()) == [path]
    else:
        assert not path.exists()
        assert list(tmp_path.iterdir()) == []


def test_fsync_precedes_replace_in_same_directory(project, tmp_path, monkeypatch):
    path = tmp_path / "project.json"
    path.write_bytes(b"old")
    original_fsync, original_replace = os.fsync, os.replace
    events = []

    def sync(fd):
        events.append("fsync")
        return original_fsync(fd)

    def replace(source, destination):
        assert events == ["fsync"]
        assert source.parent == destination.parent == tmp_path
        assert path.read_bytes() == b"old"
        assert load_project(source) == project
        events.append("replace")
        original_replace(source, destination)

    monkeypatch.setattr(json_project.os, "fsync", sync)
    monkeypatch.setattr(json_project.os, "replace", replace)
    save_project(project, path)
    assert events == ["fsync", "replace"]
    assert load_project(path) == project


def test_cleanup_failure_is_reported(project, tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise PermissionError("simulated permissions")

    monkeypatch.setattr(json_project.os, "replace", fail)
    monkeypatch.setattr(type(tmp_path), "unlink", fail)
    with pytest.raises(PersistenceError, match="could not remove temporary file"):
        save_project(project, tmp_path / "project.json")


def test_invalid_project_is_rejected_before_touching_file(tmp_path):
    path = tmp_path / "project.json"
    path.write_bytes(b"old")
    with pytest.raises(PersistenceError, match="expected an AnalysisProject"):
        save_project({}, path)
    assert path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [path]


def test_unencodable_domain_text_is_rejected_before_writing(tmp_path):
    project = AnalysisProject(
        "Bad\ud800",
        "mm",
        [DimensionContribution("A", "Part", 1, 0, 0, 1)],
        AcceptanceLimits(0, 1),
    )
    with pytest.raises(PersistenceError, match="UTF-8"):
        save_project(project, tmp_path / "project.json")
    assert list(tmp_path.iterdir()) == []
