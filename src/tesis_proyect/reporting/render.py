from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence

from tesis_proyect.models.enums import RunStatus
from tesis_proyect.models.execution import RunManifest
from tesis_proyect.models.protocols import RunInspection, StageInspection
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.models.scientific import CountingResult
from tesis_proyect.models.stages import (
    EdgeValidationOutcome,
    ForestValidationOutcome,
)


def _method_line(name: str, result: CountingResult | None) -> str:
    if result is None:
        return f"  {name}: unavailable"
    if result.status == "success":
        return f"  {name}: success — value {result.value}"
    skip = result.skip
    return f"  {name}: skipped — {skip.code}: {skip.message}"


def _available_actions(status: RunStatus) -> tuple[str, str]:
    if status == RunStatus.CREATED:
        return "run, cancel, inspect", "No — run has not started."
    if status == RunStatus.RUNNING:
        return "cancel, inspect", "Only if the previous runner no longer owns the lock."
    if status == RunStatus.FAILED:
        return "resume, inspect, export", "Yes — provided no runner is active."
    if status == RunStatus.CANCELLED:
        return "inspect, export", "No — cancelled runs are terminal."
    return "resume, inspect, export", "Yes — integrity check and checkpoint repair only."


def _conclusion(report: ReportSummary) -> list[str]:
    if report.run_status == RunStatus.CANCELLED:
        return ["The run was cancelled; available evidence may be incomplete."]
    if report.diagnostics:
        return [
            f"The run has {len(report.diagnostics)} domain diagnostic(s); no valid scientific "
            "comparison was established."
        ]
    comparison = report.comparison
    if comparison is not None and comparison.status == "match":
        return [f"Both methods agree on {comparison.value_reference} undirected path(s)."]
    if comparison is not None and comparison.status == "mismatch":
        return [
            f"The methods disagree: exact={comparison.value_exact}, "
            f"reference={comparison.value_reference}."
        ]
    reference = report.methods.reference
    if reference is not None and reference.status == "success":
        return [
            f"The reference method found {reference.value} undirected Hamiltonian path(s).",
            "No exact/reference agreement could be established.",
        ]
    if report.run_status == RunStatus.FAILED:
        return ["The run failed before a conclusive scientific result was available."]
    return ["No conclusive scientific result is available yet."]


def render_run_inspection_human(view: RunInspection, report: ReportSummary) -> str:
    """Render an explanatory read-only run view without changing NDJSON contracts."""
    lines = [
        f"Run {view.run.run_id}",
        f"Status: {view.run.status}",
        f"Experiment: {view.run.experiment_id}",
        f"Counting convention: {view.run.counting_convention}",
        "",
        "Instance",
    ]
    if report.instance is None:
        lines.append("  No canonical instance is available.")
    else:
        edges = ", ".join(f"[{u},{v}]" for u, v in report.instance.edges) or "none"
        lines.extend(
            [
                f"  Vertices: {report.instance.n}",
                f"  Prescribed edges: {edges}",
                f"  Source: {report.instance.source_metadata.kind}",
                f"  Hash: {report.instance.instance_hash}",
            ]
        )
    lines.extend(["", "Structure"])
    if report.structure is None:
        lines.append("  No structural analysis is available.")
    else:
        free = ", ".join(str(value) for value in report.structure.free_vertices) or "none"
        lengths = ", ".join(str(value) for value in report.structure.component_lengths) or "none"
        lines.extend(
            [
                f"  Case: {report.structure.case_type}",
                f"  Component edge lengths: {lengths}",
                f"  Free vertices: {free}",
                f"  Blocks: {report.structure.blocks}",
            ]
        )
    lines.extend(
        [
            "",
            "Methods",
            _method_line("Exact", report.methods.exact),
            _method_line("Reference", report.methods.reference),
            "",
            "Comparison",
        ]
    )
    if report.comparison is None:
        lines.append("  Unavailable")
    elif report.comparison.status == "not_applicable":
        reason = report.comparison.reason
        detail = f" — {reason.code}: {reason.message}" if reason is not None else ""
        lines.append(f"  Not applicable{detail}")
    else:
        lines.append(
            f"  {report.comparison.status}: exact={report.comparison.value_exact}, "
            f"reference={report.comparison.value_reference}"
        )
    lines.extend(["", "Diagnostics"])
    if report.diagnostics:
        lines.extend(f"  {item.code}: {item.message}" for item in report.diagnostics)
    else:
        lines.append("  None")
    counts = Counter(state.status.value for state in view.pipeline.ordered_stages)
    lines.extend(
        [
            "",
            "Pipeline",
            "  " + ", ".join(f"{status}={count}" for status, count in sorted(counts.items())),
        ]
    )
    lines.extend(
        f"  {state.ordinal:02d}. {state.stage}: {state.status} (attempts={state.attempt_count})"
        for state in view.pipeline.ordered_stages
    )
    actions, resume = _available_actions(view.run.status)
    lines.extend(["", "Conclusion"])
    lines.extend(f"  {line}" for line in _conclusion(report))
    lines.extend(
        [
            "",
            "Files",
            f"  JSON report: runs/{view.run.run_id}/reports/result.json",
            f"  Markdown report: runs/{view.run.run_id}/reports/report.md",
            "",
            "Available actions",
            f"  Commands: {actions}",
            f"  Resume: {resume}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_stage_inspection_human(view: StageInspection) -> str:
    """Render the terminal evidence and last attempt of one stage."""
    result = view.result
    attempt = result.attempts[-1]
    lines = [
        f"Run {view.run_id}",
        f"Stage: {view.stage}",
        f"Status: {result.status}",
        f"Attempts: {len(result.attempts)}",
        "",
        "Last attempt",
        f"  Number: {attempt.number}",
        f"  Started: {attempt.started_at}",
        f"  Finished: {attempt.finished_at}",
        f"  Duration: {attempt.duration_ms} ms",
        f"  Termination: {attempt.termination}",
    ]
    metrics = attempt.metrics
    producer = (
        f"{metrics.producer.id}@{metrics.producer.version}"
        if metrics.producer is not None
        else "not applicable"
    )
    lines.extend(
        [
            f"  Producer: {producer}",
            f"  Worker duration: {metrics.worker_duration_ms} ms"
            if metrics.worker_duration_ms is not None
            else "  Worker duration: not applicable",
            f"  Candidates examined: {metrics.candidates_examined}"
            if metrics.candidates_examined is not None
            else "  Candidates examined: not applicable",
        ]
    )
    if attempt.error is not None:
        lines.append(f"  Error: {attempt.error.code} — {attempt.error.message}")
    if attempt.skip is not None:
        lines.append(f"  Skip: {attempt.skip.kind}/{attempt.skip.code} — {attempt.skip.message}")
    lines.extend(["", "Outcome"])
    if result.outcome is None:
        lines.append("  Unavailable")
    else:
        lines.append(f"  Kind: {result.outcome.kind}")
        if isinstance(result.outcome, (EdgeValidationOutcome, ForestValidationOutcome)):
            validation = result.outcome.validation
            lines.append(f"  Valid: {validation.valid}")
            lines.append(f"  Diagnostics: {len(validation.errors)}")
    lines.extend(["", "Artifacts"])
    if result.artifacts:
        lines.extend(
            f"  {artifact.path} ({artifact.size_bytes} bytes, {artifact.sha256})"
            for artifact in result.artifacts
        )
    else:
        lines.append("  None")
    return "\n".join(lines) + "\n"


def render_run_listing_human(rows: Sequence[tuple[str, RunManifest]]) -> str:
    """Render a deterministic human table from validated run manifests."""

    if not rows:
        return "No runs found.\n"
    values = [
        (
            reference,
            manifest.run_id,
            manifest.experiment_id,
            manifest.status.value,
            manifest.created_at,
            manifest.updated_at,
        )
        for reference, manifest in rows
    ]
    headers = ("REF", "RUN ID", "EXPERIMENT", "STATUS", "CREATED", "UPDATED")
    widths = tuple(
        max(len(headers[index]), *(len(row[index]) for row in values))
        for index in range(len(headers))
    )

    def render_row(row: tuple[str, ...]) -> str:
        return " ".join(
            value.ljust(widths[index]) if index < len(row) - 1 else value
            for index, value in enumerate(row)
        )

    return "\n".join((render_row(headers), *(render_row(row) for row in values))) + "\n"


def render_markdown(report: ReportSummary) -> str:
    lines = [
        "# Experiment result",
        "",
        f"- Run: `{report.run_id}`",
        f"- Experiment: `{report.experiment_id}`",
        f"- Status: `{report.run_status}`",
        "",
        "## Evidence",
        "",
    ]
    if report.instance is None:
        lines.append("No canonical instance is available.")
    else:
        lines.extend(
            [
                f"- Instance hash: `{report.instance.instance_hash}`",
                f"- Vertices: {report.instance.n}",
                f"- Prescribed edges: {len(report.instance.edges)}",
            ]
        )
    lines.extend(["", "## Methods", ""])
    for name, result in (("Exact", report.methods.exact), ("Reference", report.methods.reference)):
        if result is None:
            lines.append(f"- {name}: unavailable")
        elif result.status == "success":
            lines.append(f"- {name}: success, value `{result.value}`")
        else:
            lines.append(f"- {name}: skipped (`{result.skip.code}`)")
    lines.extend(["", "## Diagnostics", ""])
    if not report.diagnostics:
        lines.append("No domain diagnostics.")
    else:
        lines.extend(f"- `{item.code}`: {item.message}" for item in report.diagnostics)
    return "\n".join(lines) + "\n"


def render_json(report: ReportSummary) -> bytes:
    return (
        json.dumps(
            report.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
