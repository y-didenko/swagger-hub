"""Render structured test-case data to a markdown document."""
from typing import List


def render_markdown(
    entry: dict,
    scope_summary: str,
    assumptions: List[str],
    spec_gaps: List[str],
    test_cases: List[dict],
    generated_at: str,
) -> str:
    lines = []
    title = (
        entry.get("display_name")
        or entry.get("info_title")
        or entry.get("service_id", "Unknown")
    )

    lines.append(f"# {title} — API Test Case Pack\n")

    # --- Source Metadata ---
    lines.append("## Source Metadata\n")
    lines.append(f"- **Service ID:** {entry.get('service_id', '')}")
    lines.append(f"- **Source Path:** {entry.get('source_path', '')}")
    lines.append(f"- **OpenAPI Version:** {entry.get('openapi_version', '')}")
    lines.append(f"- **Spec Version:** {entry.get('info_version', '')}")
    lines.append(f"- **Spec Hash:** `{entry.get('spec_hash', '')}`")
    lines.append(f"- **Generated At:** {generated_at}")
    if entry.get("source_commit"):
        lines.append(f"- **Source Commit:** `{entry['source_commit']}`")
    if entry.get("published_url"):
        lines.append(f"- **Published URL:** {entry['published_url']}")
    lines.append("")

    # --- Scope Summary ---
    lines.append("## Scope Summary\n")
    lines.append(scope_summary or "_No scope summary generated._")
    lines.append("")

    # --- Assumptions and Limitations ---
    lines.append("## Assumptions and Limitations\n")
    if assumptions:
        for item in assumptions:
            lines.append(f"- {item}")
    else:
        lines.append("_None noted._")
    lines.append("")

    # --- Major Spec Gaps ---
    lines.append("## Major Spec Gaps\n")
    if spec_gaps:
        for gap in spec_gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("_No major gaps identified._")
    lines.append("")

    # --- Test Cases ---
    lines.append("## Test Cases\n")
    if not test_cases:
        lines.append("_No test cases generated._")
    else:
        for tc in test_cases:
            tc_id = tc.get("id", "TC-???")
            tc_title = tc.get("title", "Untitled")
            lines.append(f"### {tc_id} {tc_title}\n")
            lines.append(f"- **Endpoint:** `{tc.get('endpoint', '')}`")
            lines.append(f"- **Method:** `{tc.get('method', '')}`")
            if tc.get("operationId"):
                lines.append(f"- **OperationId:** `{tc['operationId']}`")
            lines.append(f"- **Objective:** {tc.get('objective', '')}")
            lines.append(f"- **Preconditions:** {tc.get('preconditions', '')}")
            lines.append(f"- **Input / Request:** {tc.get('input', '')}")
            lines.append(f"- **Expected Result:** {tc.get('expected_result', '')}")

            vp = tc.get("validation_points", [])
            if isinstance(vp, list) and vp:
                lines.append("- **Validation Points:**")
                for v in vp:
                    lines.append(f"  - {v}")
            elif isinstance(vp, str) and vp:
                lines.append(f"- **Validation Points:** {vp}")

            lines.append(f"- **Priority:** {tc.get('priority', '')}")
            lines.append(f"- **Scenario Type:** {tc.get('scenario_type', '')}")
            if tc.get("notes"):
                lines.append(f"- **Notes:** {tc['notes']}")
            lines.append("")

    return "\n".join(lines)
