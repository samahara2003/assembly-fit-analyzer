"""Verify that the installed package and its architectural boundaries import."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "assembly_fit_analyzer",
        "assembly_fit_analyzer.domain",
        "assembly_fit_analyzer.calculations",
        "assembly_fit_analyzer.validation",
        "assembly_fit_analyzer.persistence",
        "assembly_fit_analyzer.reporting",
        "assembly_fit_analyzer.ui",
    ],
)
def test_package_import(module_name: str) -> None:
    assert import_module(module_name).__name__ == module_name
