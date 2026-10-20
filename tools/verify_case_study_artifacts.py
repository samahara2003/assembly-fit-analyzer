"""Check bundled case-study inputs and PDF evidence with production APIs.

Run from the repository root after installing .[dev,reports]. This checks
artifacts; the study's Fraction worksheet is the independent numerical oracle.
"""

import hashlib
import json
import re
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from assembly_fit_analyzer.calculations import analyze_project
from assembly_fit_analyzer.persistence import dumps_project, load_project, loads_project
from assembly_fit_analyzer.reporting import generate_pdf_report

EXAMPLES = (
    Path(__file__).resolve().parents[1]
    / "docs/case-studies/01-bearing-axial-clearance/examples"
)
CASES = {
    "original-chain-a": ("14.500", ("0.400", "0.500", "0.660")),
    "original-chain-b": ("14.500", ("0.150", "0.300", "0.510")),
    "cover-recess-chain-a": ("14.700", ("0.600", "0.700", "0.860")),
    "cover-recess-chain-b": ("14.700", ("0.350", "0.500", "0.710")),
}


def main() -> None:
    """Validate exact inputs, verdict absence, results, trace totals and PDFs."""
    for stem, (housing, expected) in CASES.items():
        path = EXAMPLES / f"{stem}.json"
        encoded = path.read_text(encoding="utf-8")
        raw = json.loads(encoded)
        assert raw["schema_version"] == 2, stem
        assert raw["project"]["acceptance_limits"] is None, stem
        project = load_project(path)
        assert encoded == dumps_project(project), stem
        assert project == loads_project(dumps_project(project)), stem
        assert project.unit == "mm" and project.acceptance_limits is None, stem
        assert project.name.startswith("Preliminary Case Study 01"), stem
        inputs = [
            ("H", housing, "-0.100", "0.100", 1),
            ("W", "14.000", "-0.060", "0.000", -1),
        ]
        if stem.endswith("-b"):
            inputs.append(("P", "0.200", "-0.050", "0.050", -1))
        for item, (identifier, nominal, lower, upper, sign) in zip(
            project.contributions, inputs, strict=True
        ):
            assert (item.dimension_id, item.sign) == (identifier, sign), stem
            for field, value in zip(
                ("nominal", "lower_deviation", "upper_deviation"),
                (nominal, lower, upper),
                strict=True,
            ):
                assert getattr(item, field).as_tuple() == Decimal(value).as_tuple(), (
                    stem
                )

        result = analyze_project(project)
        assert result.passes is None and result.acceptance_limits is None, stem
        for value, reference in zip(
            (result.minimum, result.nominal, result.maximum), expected, strict=True
        ):
            assert value.as_tuple() == Decimal(reference).as_tuple(), stem
        text = " ".join(
            " ".join(page.extract_text().split())
            for page in PdfReader(path.with_suffix(".pdf")).pages
        )
        assert project.name in text and "Dimensional units: mm" in text, stem
        assert "Acceptance: Not assessed" in text, stem
        assert "No functional acceptance assessment was performed" in text, stem
        assert not re.search(r"\b(?:Pass|Fail)\b", text), stem
        assert hashlib.sha256(path.read_bytes()).hexdigest() in text, stem
        for label, value in zip(
            ("Minimum", "Nominal", "Maximum"), expected, strict=True
        ):
            assert f"{label} result {value}" in text, stem
        assert f"Total - - {' '.join(expected)}" in text, stem
        for item in project.contributions:
            row = (
                f"{item.dimension_id} {item.label} {item.nominal} "
                f"{item.lower_deviation} {item.upper_deviation} {item.sign:+d}"
            )
            assert row in text, stem

        # Bundled PDFs record their original application version. Verify fresh
        # generation independently rather than requiring bytes across versions.
        pdf = generate_pdf_report(result)
        assert pdf == generate_pdf_report(result), stem
        assert len(PdfReader(BytesIO(pdf)).pages) >= 1, stem
        print(f"{stem}: {' / '.join(expected)} mm; JSON/PDF checks passed")
    print("Verified all four JSON/PDF pairs; no artifacts changed.")


if __name__ == "__main__":
    main()
