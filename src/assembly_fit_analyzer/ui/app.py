"""Single-page Streamlit workspace; engineering behavior lives in core APIs."""

import streamlit as st

from assembly_fit_analyzer.calculations import (
    CalculationError,
    WorstCaseResult,
    analyze_project,
)
from assembly_fit_analyzer.domain import (
    AcceptanceLimits,
    AnalysisProject,
    DimensionContribution,
)
from assembly_fit_analyzer.persistence import PersistenceError, dumps_project
from assembly_fit_analyzer.persistence.json_project import check_json_size
from assembly_fit_analyzer.reporting import ReportError, generate_pdf_report
from assembly_fit_analyzer.ui.visualization import compact, interval_svg
from assembly_fit_analyzer.ui.workspace import (
    Draft,
    add_dimension,
    capture_draft,
    contribution_summary,
    draft_from_project,
    editor_rows,
    literal_message,
    new_draft,
    project_from_draft,
    project_from_upload,
    range_description,
    remove_dimensions,
)
from assembly_fit_analyzer.validation import ValidationError
from assembly_fit_analyzer.validation.resources import MAX_JSON_BYTES


def _example() -> Draft:
    return draft_from_project(
        AnalysisProject(
            "Housing clearance",
            "mm",
            [
                DimensionContribution("A", "Housing", "10.000", "-0.100", "0.200", 1),
                DimensionContribution("B", "Insert", "4.000", "-0.300", "0.100", -1),
            ],
            AcceptanceLimits("5.800", "6.500"),
        )
    )


def _replace_workspace(draft: Draft) -> None:
    st.session_state.base_draft = draft
    st.session_state.revision += 1
    st.session_state.result = None
    st.session_state.analyzed_draft = None
    st.session_state.validation_requested = False
    st.session_state.calculation_error = None
    st.session_state.pending = None
    st.session_state.editor_revision = 0
    st.session_state.export_draft = None
    st.session_state.export_data = None
    _clear_pdf()


def _clear_pdf() -> None:
    st.session_state.pdf_draft = None
    st.session_state.pdf_data = None


def _file_controls() -> None:
    with st.expander("Create or load a project", expanded=False):
        left, right = st.columns(2)
        if left.button("New project", width="stretch"):
            st.session_state.pending = new_draft()
        if right.button("Use worked example", width="stretch"):
            st.session_state.pending = _example()
        upload = st.file_uploader(
            "Upload a project JSON file",
            type=["json"],
            key=f"upload_{st.session_state.revision}",
            max_upload_size=MAX_JSON_BYTES // (1024 * 1024),
        )
        if st.button("Load uploaded project", disabled=upload is None):
            try:
                check_json_size(upload.size)
                st.session_state.pending = draft_from_project(
                    project_from_upload(upload.getvalue())
                )
            except PersistenceError as exc:
                st.session_state.pending = None
                st.error(
                    literal_message(
                        f"Could not load this file: {exc}. Your workspace is unchanged."
                    )
                )
        st.caption(
            "Downloads and uploads use your browser. No local file path is required."
        )
    if st.session_state.pending is not None:
        with st.container(border=True):
            st.warning(
                "Replace the current workspace? Download any edits you want to keep "
                "before continuing. You can keep editing below."
            )
            left, right = st.columns(2)
            if left.button("Replace workspace", type="primary"):
                _replace_workspace(st.session_state.pending)
                st.rerun()
            if right.button("Keep editing"):
                st.session_state.pending = None
                st.rerun()


def _rebase_chain(draft: Draft) -> None:
    """Rebase only after a structural row action; metadata widget keys stay stable."""
    st.session_state.base_draft = draft
    st.session_state.editor_revision += 1
    st.rerun()


def _editor() -> Draft:
    base = st.session_state.base_draft
    revision = st.session_state.revision
    epoch = st.session_state.editor_revision
    with st.container(border=True):
        st.subheader("Project workspace")
        name_col, unit_col = st.columns([2, 1])
        name = name_col.text_input(
            "Project name", value=base.name, key=f"name_{revision}"
        )
        unit = unit_col.selectbox(
            "Units",
            ["mm", "in"],
            index=0 if base.unit == "mm" else 1,
            format_func=lambda value: (
                "Inches (in)" if value == "in" else "Millimeters (mm)"
            ),
            key=f"unit_{revision}",
            help="Labels all values. Changing units does not convert numbers.",
        )
        lower_col, upper_col = st.columns(2)
        lower = lower_col.text_input(
            "Lower functional limit",
            value=base.lower,
            placeholder="Optional — leave both blank",
            key=f"lower_{revision}",
            help="Inclusive lower bound. Provide both limits or leave both blank.",
        )
        upper = upper_col.text_input(
            "Upper functional limit",
            value=base.upper,
            placeholder="Optional — leave both blank",
            key=f"upper_{revision}",
            help="Inclusive upper bound. Provide both limits or leave both blank.",
        )
        st.subheader("Dimensional chain")
        config = {
            "dimension_id": st.column_config.TextColumn(
                "Dimension ID",
                width=150,
                required=True,
                help="Stable dimension identifier; must be unique within the project.",
            ),
            "sign": st.column_config.SelectboxColumn(
                "Sign",
                options=["+1", "-1"],
                default="+1",
                width=100,
                required=True,
                help="+1 adds; -1 subtracts the physical dimension. "
                "Lengths remain nonnegative.",
            ),
            "label": st.column_config.TextColumn("Label", width=230, required=True),
            "nominal": st.column_config.TextColumn(
                "Nominal",
                width=180,
                required=True,
                help="Nonnegative physical length, entered as decimal text.",
            ),
            "lower_deviation": st.column_config.TextColumn(
                "Lower deviation",
                width=180,
                required=True,
                help="Signed offset from nominal, e.g. -0.100.",
            ),
            "upper_deviation": st.column_config.TextColumn(
                "Upper deviation",
                width=180,
                required=True,
                help="Signed offset from nominal, e.g. +0.200.",
            ),
        }
        # Stable input and identity preserve cumulative edits. Only explicit
        # structural actions rebase the source and advance the editor key.
        editor_key = f"chain_{revision}" if epoch == 0 else f"chain_{revision}_{epoch}"
        rows = st.data_editor(
            editor_rows(base),
            column_config=config,
            column_order=list(config),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            row_height=38,
            key=editor_key,
            # Default rerun mode debounces synchronization by 150 ms: another
            # widget can export before the committed cell reaches widget state.
            # Supported buffering writes in a microtask; every explicit action
            # then submits that state without racing the editor's rerun timer.
            on_change="ignore",
        )
        draft = capture_draft(name, unit, lower, upper, rows)
        st.caption(
            "Scroll horizontally for additional columns. Table edits are buffered "
            "until the next action; results show the last analyzed snapshot."
        )
        # Native wrapping keeps controls readable without squeezing their labels.
        with st.container(horizontal=True, gap="medium"):
            if st.button("Add dimension"):
                _rebase_chain(add_dimension(draft))
            with st.popover("Remove dimensions", disabled=not rows):
                selected = st.multiselect(
                    "Dimensions to remove",
                    list(range(len(rows))),
                    format_func=lambda index: (
                        f"Row {index + 1} · "
                        f"{rows[index].get('dimension_id') or 'No ID'} · "
                        f"{rows[index].get('label') or 'No label'}"
                    ),
                    key=f"remove_{revision}_{epoch}",
                )
                if st.button("Remove selected", disabled=not selected):
                    _rebase_chain(remove_dimensions(draft, selected))
            with st.popover("Input guide"):
                st.markdown(
                    "- Enter decimal text; scientific notation is supported.\n"
                    "- Deviations are signed offsets from nominal.\n"
                    "- Sign +1 adds; sign -1 subtracts the entire physical dimension.\n"
                    "- Use Add dimension or the table's last row to add a row.\n"
                    "- Commit edits with Enter, Tab, or by leaving the field.\n"
                    "- Analyze or open an export/report to synchronize table edits.\n"
                    "- Units never convert automatically. Download work before leaving."
                )
        if not rows:
            st.info("The chain is empty. Select Add dimension to begin.")
    return draft


def _export_panel(
    project: AnalysisProject | None, draft: Draft, error: str | None
) -> None:
    # Opening is a server rerun that collects current editor/widget values.
    # No download link exists in a closed panel, so an old prepared link cannot
    # be clicked while the opening rerun refreshes the snapshot.
    panel = st.popover(
        "Export project",
        key=f"export_{st.session_state.revision}",
        on_change="rerun",
        width="stretch",
    )
    st.session_state.export_draft = None
    st.session_state.export_data = None
    with panel:
        if not panel.open:
            st.caption("Open to refresh the export from current inputs.")
            return
        if project is None:
            st.error(literal_message(f"Correct the inputs before exporting: {error}"))
            return
        try:
            data = dumps_project(project)
        except PersistenceError as exc:
            st.error(literal_message(f"Could not export this project: {exc}"))
            return
        st.session_state.export_draft = draft
        st.session_state.export_data = data
        st.text(project.name)
        st.caption(
            f"{len(project.contributions)} dimensions · {project.unit} · Inputs only"
        )
        st.download_button(
            "Download JSON",
            data=data,
            mime="application/json",
            file_name="assembly-project.json",
            on_click="ignore",
            width="stretch",
        )


def _trace(result: WorstCaseResult) -> None:
    st.subheader("Contribution summary")
    st.dataframe(
        contribution_summary(result),
        hide_index=True,
        width="stretch",
        row_height=38,
        column_config={
            "Dimension": st.column_config.TextColumn(width=250),
            **{
                field: st.column_config.TextColumn(width=200)
                for field in ("Minimum", "Nominal", "Maximum")
            },
        },
    )
    st.caption(
        "Exact contributions in project units. Scroll horizontally on smaller screens; "
        "double-click a cell to inspect or copy its full value."
    )
    with st.expander("Complete engineering trace"):
        st.caption(
            "Exact decimal strings in project units. "
            "Totals above are the engine outputs."
        )
        st.dataframe(
            [
                {
                    "Dimension ID": trace.dimension.dimension_id,
                    "Label": trace.dimension.label,
                    "Sign": "+1" if trace.dimension.sign == 1 else "-1",
                    "Nominal input": str(trace.dimension.nominal),
                    "Lower deviation": str(trace.dimension.lower_deviation),
                    "Upper deviation": str(trace.dimension.upper_deviation),
                    "Physical minimum": str(trace.minimum),
                    "Physical maximum": str(trace.maximum),
                    "Minimum contribution": str(trace.minimum_contribution),
                    "Nominal contribution": str(trace.nominal_contribution),
                    "Maximum contribution": str(trace.maximum_contribution),
                }
                for trace in result.traces
            ],
            hide_index=True,
            width="stretch",
        )


def _pdf_panel(result: WorstCaseResult) -> None:
    panel = st.popover(
        "Download PDF report",
        key=f"pdf_{st.session_state.revision}",
        on_change="rerun",
        width="content",
    )
    with panel:
        if not panel.open:
            st.caption("Open to generate a report for the current analyzed snapshot.")
            return
        if st.session_state.get("pdf_draft") != st.session_state.current_draft:
            _clear_pdf()
            try:
                with st.spinner("Generating engineering report…"):
                    data = generate_pdf_report(result)
                st.session_state.pdf_data = data
                st.session_state.pdf_draft = st.session_state.current_draft
            except ReportError as exc:
                st.error(literal_message(f"Could not generate the PDF report: {exc}"))
                return
        st.caption("Current analysis · Exact values and complete trace · PDF")
        st.download_button(
            "Download PDF",
            data=st.session_state.pdf_data,
            mime="application/pdf",
            file_name="assembly-analysis-report.pdf",
            on_click="ignore",
            width="stretch",
        )


def _results() -> None:
    result = st.session_state.result
    if result is None:
        st.subheader("Analysis results")
        st.info(
            "Complete the chain, optionally provide both functional limits, "
            "then select Analyze."
        )
        return
    if st.session_state.current_draft != st.session_state.analyzed_draft:
        st.subheader("Analysis results")
        st.warning(
            "Inputs changed. Analyze again to see results for the current workspace."
        )
        return
    st.subheader("Last analyzed results")
    _pdf_panel(result)
    unit = result.project.unit
    if result.passes is None:
        st.info("Analysis only · No functional acceptance assessment performed.")
    elif result.passes:
        st.success("Pass · Entire interval within inclusive functional limits.")
    else:
        st.error("Fail · Interval is not fully within the functional limits.")
    # Wrap whole metric cards rather than truncating values in narrow columns.
    with st.container(horizontal=True):
        for label, value in zip(
            ("Minimum", "Nominal", "Maximum"),
            (result.minimum, result.nominal, result.maximum),
            strict=True,
        ):
            st.metric(f"{label} ({unit})", compact(value), border=True, width=400)
    if result.acceptance_limits is not None:
        st.caption(
            f"Functional interval [{compact(result.acceptance_limits.lower)}, "
            f"{compact(result.acceptance_limits.upper)}] {unit} · Inclusive endpoints"
        )
    else:
        st.caption("Functional limits: not provided.")
    st.markdown(
        "**Signed range:** "
        + range_description(result.minimum, result.maximum).partition(":")[0]
    )
    st.caption("Physical meaning follows the defined reference direction.")
    svg = interval_svg(result)
    if svg is not None:
        st.image(svg, width="stretch")
    else:
        st.info(
            "The chart is outside its display range. "
            "Exact results remain available below."
        )
    with st.expander("Exact results and interpretation"):
        st.code(
            "\n".join(
                f"{label}: {value} {unit}"
                for label, value in (
                    ("Minimum", result.minimum),
                    ("Nominal", result.nominal),
                    ("Maximum", result.maximum),
                    *(
                        (
                            ("Lower functional limit", result.acceptance_limits.lower),
                            ("Upper functional limit", result.acceptance_limits.upper),
                        )
                        if result.acceptance_limits is not None
                        else ()
                    ),
                )
            ),
            language=None,
        )
        st.write(
            "Sign follows your reference direction; its physical meaning depends "
            "on the chain definition. Crossing zero may represent a transition between "
            "clearance and interference for a clearance chain, "
            "not guaranteed interference."
        )
        st.caption(
            "Chart labels may be compact. If absolute labels coincide, the chart shows "
            "offsets from nominal. Coordinates are presentation-only; "
            "acceptance uses Decimal."
        )
    _trace(result)


def main() -> None:
    st.set_page_config(page_title="Assembly Fit & Tolerance Analyzer", layout="wide")
    if "base_draft" not in st.session_state:
        st.session_state.revision = 0
        _replace_workspace(new_draft())
    if "editor_revision" not in st.session_state:
        st.session_state.base_draft = st.session_state.get(
            "current_draft", st.session_state.base_draft
        )
        st.session_state.editor_revision = 1
    st.title("Assembly Fit & Tolerance Analyzer")
    st.caption("Linear 1D · Deterministic worst-case · Exact Decimal arithmetic")
    _file_controls()
    draft = _editor()
    st.session_state.current_draft = draft
    if draft != st.session_state.analyzed_draft:
        _clear_pdf()
    project, validation_error = None, None
    try:
        project = project_from_draft(draft)
    except ValidationError as exc:
        validation_error = str(exc)
    left, right = st.columns(2)
    if left.button("Analyze", type="primary", width="stretch"):
        st.session_state.validation_requested = True
        st.session_state.calculation_error = None
        if project is not None:
            try:
                st.session_state.result = analyze_project(project)
                st.session_state.analyzed_draft = draft
            except CalculationError as exc:
                st.session_state.result = None
                st.session_state.calculation_error = (draft, str(exc))
    with right:
        _export_panel(project, draft, validation_error)
    if validation_error and st.session_state.validation_requested:
        st.error(literal_message(f"Check your inputs: {validation_error}"))
    error = st.session_state.calculation_error
    if error and error[0] == draft:
        st.error(
            literal_message(
                f"Analysis could not complete: {error[1]}. "
                "Adjust the dimensional inputs."
            )
        )
    st.divider()
    _results()
