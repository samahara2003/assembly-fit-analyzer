# Assembly Fit & Tolerance Analyzer v1.0.0

First release of a local application for deterministic worst-case tolerance
analysis of linear, one-dimensional dimensional chains.

- Exact Decimal calculations with signed contributions and auditable traces.
- Symmetric, asymmetric, unilateral and zero dimensional tolerances.
- Optional inclusive functional limits; analysis-only projects receive no verdict.
- Streamlit workspace with interval visualization and explicit analysis actions.
- Schema-v2 JSON persistence, retaining Decimal strings and contribution order;
  version-1 assessed projects remain readable.
- Engineering PDF reports with exact results, inputs, traces and provenance.
- Preliminary bearing axial-clearance case study with four JSON/PDF example pairs.

The analysis assumes consistent units and independently attainable endpoints.
It does not provide statistical tolerance analysis, GD&T, thermal simulation,
CAD integration, bearing-life validation or ISO/ASME certification. The bearing
study is a preliminary engineering example, not a production-ready assembly.

License: MIT. See the repository LICENSE and engineering documentation.
