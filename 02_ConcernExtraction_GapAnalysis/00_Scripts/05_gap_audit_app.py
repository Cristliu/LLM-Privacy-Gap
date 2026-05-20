#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Double Coding Audit App Anonymized Demo
=======================================

Streamlit workspace for the rebuttal double-coding experiment.

Input:
    02_Outputs/double_coding_audit_anonymized/00_Data/sampled_data_demo10.json

Primary output:
    02_Outputs/double_coding_audit_anonymized/audit_runs/independent_audit_run_{expert_name}.json

The output is shaped to match the anonymized independent_audit_run_Expert_*.json
schema used by downstream comparison and reporting scripts.
"""

from __future__ import annotations

import json
import re
from html import escape
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent

WEB_OUTPUT_DIR = APP_ROOT / "02_Outputs" / "double_coding_audit_anonymized"
WEB_DATA_DIR = WEB_OUTPUT_DIR / "00_Data"
RESULTS_DIR = WEB_OUTPUT_DIR / "01_Results"
WEB_AUDIT_DIR = WEB_OUTPUT_DIR / "audit_runs"
WEB_COMPARISON_DIR = WEB_OUTPUT_DIR / "comparisons"

DEFAULT_SAMPLED_DATA = WEB_DATA_DIR / "sampled_data_demo10.json"

DIMENSIONS = ["concern", "necessity", "gap"]
RESULT_VALUES = ["TRUE", "FALSE"]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return slug.strip("_") or "expert"


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_result(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    text = str(value or "").strip().upper()
    return text if text in RESULT_VALUES else ""


def result_to_bool(value: Any) -> bool | None:
    normalized = normalize_result(value)
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    return None


def derive_record_result(parsed: dict[str, Any]) -> str:
    values = [
        normalize_result(parsed.get("concern_audit_result")),
        normalize_result(parsed.get("necessity_audit_result")),
        normalize_result(parsed.get("gap_audit_result")),
    ]
    if all(value == "TRUE" for value in values):
        return "TRUE"
    if all(value in RESULT_VALUES for value in values):
        return "FALSE"
    return ""


def is_complete(parsed: dict[str, Any]) -> bool:
    for dim in DIMENSIONS:
        if normalize_result(parsed.get(f"{dim}_audit_result")) not in RESULT_VALUES:
            return False
    return True


def build_evidence_url(thread_url: str, record_id: str, record_type: str) -> str:
    if not thread_url:
        return ""
    if record_type == "comment" and str(record_id).startswith("t1_"):
        comment_id = record_id.replace("t1_", "")
        return f"{thread_url.rstrip('/')}/{comment_id}/"
    return thread_url


def audit_file_for_expert(expert_name: str) -> Path:
    return WEB_AUDIT_DIR / f"independent_audit_run_{safe_slug(expert_name)}.json"


def collect_audit_files() -> list[Path]:
    files: list[Path] = []
    for directory in [WEB_AUDIT_DIR, RESULTS_DIR]:
        if directory.exists():
            files.extend(sorted(directory.glob("independent_audit_run*.json")))
    deduped: dict[str, Path] = {}
    for path in files:
        deduped[str(path.resolve())] = path
    return list(deduped.values())


def collect_analysis_files() -> list[Path]:
    patterns = [
        (WEB_COMPARISON_DIR, "final_resolution*.json"),
        (RESULTS_DIR, "independent_audit_final_resolution*.json"),
        (WEB_AUDIT_DIR, "independent_audit_run*.json"),
        (RESULTS_DIR, "independent_audit_run*.json"),
    ]
    files: list[Path] = []
    for directory, pattern in patterns:
        if directory.exists():
            files.extend(sorted(directory.glob(pattern)))
    deduped: dict[str, Path] = {}
    for path in files:
        if path.name.startswith("independent_audit_final_resolution") and "demo" not in path.name:
            continue
        deduped[str(path.resolve())] = path
    return list(deduped.values())


def relative_label(path: Path) -> str:
    return path.name


def resolve_sampled_path(path_text: str) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.exists():
        return candidate
    if path_text.strip() == DEFAULT_SAMPLED_DATA.name:
        return DEFAULT_SAMPLED_DATA
    return candidate


def reset_audit_index() -> None:
    st.session_state["audit_current_index"] = 0


def render_global_sidebar() -> str:
    """Render a V4-style persistent sidebar and return the active page."""
    with st.sidebar:
        st.header("Double Coding Demo")
        st.caption("Anonymized privacy-preserving demo workspace")

        active_page = st.radio(
            "Workspace",
            [
                "Independent audit",
                "Expert comparison",
                "Result analysis",
            ],
            key="sidebar_workspace",
        )

        st.divider()
        sampled = st.session_state.get("audit_sampled_path")
        expert = st.session_state.get("audit_expert_name")
        started = st.session_state.get("audit_started", False)
        if started and sampled and expert:
            st.success("Audit session active")
            st.write(f"**Expert:** {expert}")
            st.caption(Path(sampled).name)
            if st.button("Reset audit session", key="sidebar_reset_audit"):
                for key in [
                    "audit_started",
                    "audit_sampled_path",
                    "audit_expert_name",
                    "audit_current_index",
                    "audit_last_saved",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()
        else:
            st.info("Start by selecting the anonymized demo data and entering an expert name.")

        st.divider()
        with st.expander("Workflow", expanded=False):
            st.markdown(
                """
1. Select `sampled_data_demo10.json`
2. Enter expert name
3. Review each item
4. Export `independent_audit_run_*.json`
5. Compare two expert JSON files
"""
            )

    return active_page


def inject_v4_like_style() -> None:
    st.markdown(
        """
<style>
section[data-testid="stSidebar"] {
    border-right: 1px solid #e5e7eb;
}
.block-container {
    padding-top: 1.3rem;
    max-width: 1500px;
}
div[data-testid="stMetric"] {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 0.7rem 0.9rem;
}
div[data-testid="stMetricValue"] {
    font-size: 1.35rem;
}
div[data-testid="stAlert"] {
    border-radius: 6px;
}
.audit-highlight {
    border: 1px solid #dbe3ee;
    border-radius: 6px;
    padding: 0.85rem 0.95rem;
    margin: 0.45rem 0 0.75rem 0;
}
.audit-highlight-title {
    color: #1f2937;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    margin-bottom: 0.35rem;
    text-transform: uppercase;
}
.audit-highlight-body {
    color: #111827;
    font-size: 0.95rem;
    line-height: 1.55;
}
.audit-blue {
    background: #eff6ff;
    border-color: #bfdbfe;
}
.audit-green {
    background: #ecfdf5;
    border-color: #a7f3d0;
}
.audit-amber {
    background: #fffbeb;
    border-color: #fde68a;
}
.audit-purple {
    background: #f5f3ff;
    border-color: #ddd6fe;
}
.audit-slate {
    background: #f8fafc;
    border-color: #cbd5e1;
}
.audit-red {
    background: #fef2f2;
    border-color: #fecaca;
}
.status-chip {
    display: inline-block;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.82rem;
    padding: 0.2rem 0.65rem;
    margin: 0.25rem 0 0.6rem 0;
}
.status-edited {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
}
.status-needs-review {
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fcd34d;
}
.status-auto-agree {
    background: #e0f2fe;
    color: #075985;
    border: 1px solid #7dd3fc;
}
</style>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# sampled_data adapter
# ---------------------------------------------------------------------------

def load_sampled_items(sampled_path: Path) -> list[dict[str, Any]]:
    data = read_json(sampled_path, default={})
    items: list[dict[str, Any]] = []
    item_index = 1

    for provider, provider_data in data.get("by_provider", {}).items():
        provider_name = str(provider).lower()
        for thread in provider_data.get("threads", []):
            thread_id = thread.get("thread_id", "")
            thread_title = thread.get("title", "")
            thread_url = thread.get("url", "")

            record_map: dict[str, dict[str, Any]] = {}
            post = thread.get("post") or {}
            if post.get("record_id"):
                record_map[post["record_id"]] = post
            for record in thread.get("records", []):
                if record.get("record_id"):
                    record_map[record["record_id"]] = record

            for concern in thread.get("_extracted_concerns", []):
                concern_id = concern.get("concern_id", "")
                if not concern_id:
                    continue

                record_id = concern.get("record_id", "")
                record_type = concern.get("record_type", "post")
                record = record_map.get(record_id, {})
                gap_result = concern.get("gap_result") or {}

                items.append({
                    "item_index": item_index,
                    "concern_id": concern_id,
                    "provider": provider_name,
                    "thread_id": concern.get("thread_id", thread_id),
                    "record_id": record_id,
                    "record_type": record_type,
                    "thread_title": thread_title,
                    "thread_url": thread_url,
                    "evidence_url": build_evidence_url(thread_url, record_id, record_type),
                    "record_body": record.get("body", ""),
                    "record_rewritten": bool(record.get("rewritten") or thread.get("rewritten")),
                    "record_author": record.get("author", "[deleted]"),
                    "record_score": record.get("score", 0),
                    "topics": concern.get("topics", []),
                    "concern_statement": concern.get("concern_statement", ""),
                    "user_assumption": concern.get("user_assumption", ""),
                    "supporting_quote": concern.get("supporting_quote", ""),
                    "supporting_quote_rewritten": bool(concern.get("supporting_quote_rewritten")),
                    "gap_index": concern.get("gap_index", ""),
                    "gap_types": concern.get("gap_types", gap_result.get("gap_types", [])),
                    "gap_result": gap_result,
                })
                item_index += 1

    return items


def parsed_template(concern_id: str) -> dict[str, Any]:
    return {
        "concern_id": concern_id,
        "concern_audit_result": "",
        "concern_audit_reason": "",
        "necessity_audit_result": "",
        "necessity_audit_reason": "",
        "gap_audit_result": "",
        "gap_audit_reason": "",
    }


# ---------------------------------------------------------------------------
# Audit run schema
# ---------------------------------------------------------------------------

def raw_response_stub(parsed: dict[str, Any], expert_name: str) -> dict[str, Any]:
    """Keep the raw_response slot schema-compatible for downstream inspection."""
    payload = {"results": [parsed]}
    return {
        "id": f"web_manual_{safe_slug(expert_name)}_{safe_slug(parsed.get('concern_id', 'item'))}",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            }
        ],
        "source": "web_manual_audit",
    }


def build_audit_run(
    expert_name: str,
    sampled_path: Path,
    items: list[dict[str, Any]],
    audit_state: dict[str, dict[str, Any]],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = existing or {}
    now = utc_now()
    results: list[dict[str, Any]] = []

    for item in items:
        concern_id = item["concern_id"]
        state = audit_state.get(concern_id)
        if not state:
            continue
        parsed = state.get("parsed_result", parsed_template(concern_id))
        if not any(normalize_result(parsed.get(f"{dim}_audit_result")) for dim in DIMENSIONS):
            continue

        results.append({
            "concern_id": concern_id,
            "item_index": item["item_index"],
            "processed_at": state.get("processed_at") or now,
            "parsed_result": {
                "concern_id": concern_id,
                "concern_audit_result": normalize_result(parsed.get("concern_audit_result")),
                "concern_audit_reason": str(parsed.get("concern_audit_reason", "")).strip(),
                "necessity_audit_result": normalize_result(parsed.get("necessity_audit_result")),
                "necessity_audit_reason": str(parsed.get("necessity_audit_reason", "")).strip(),
                "gap_audit_result": normalize_result(parsed.get("gap_audit_result")),
                "gap_audit_reason": str(parsed.get("gap_audit_reason", "")).strip(),
            },
        })
        results[-1]["raw_response"] = raw_response_stub(results[-1]["parsed_result"], expert_name)

    return {
        "description": f"Independent audit run generated from web interface for {expert_name}",
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "source_file": sampled_path.name,
        "prompt_file": "web_manual_double_coding_audit",
        "config_snapshot": {
            "mode": "web_manual_audit",
            "expert_name": expert_name,
            "input_format": "sampled_data.json",
            "output_schema_reference": "independent_audit_run_HZ.json",
        },
        "total_items": len(items),
        "processed_count": len(results),
        "results": results,
        "errors": existing.get("errors", []),
    }


def load_audit_run(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    data = read_json(path, default={})
    state: dict[str, dict[str, Any]] = {}
    for result in data.get("results", []):
        concern_id = result.get("concern_id") or result.get("parsed_result", {}).get("concern_id")
        if not concern_id:
            continue
        state[concern_id] = {
            "processed_at": result.get("processed_at", ""),
            "parsed_result": result.get("parsed_result", parsed_template(concern_id)),
        }
    return data, state


def save_audit_state(
    output_path: Path,
    expert_name: str,
    sampled_path: Path,
    items: list[dict[str, Any]],
    audit_state: dict[str, dict[str, Any]],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = build_audit_run(expert_name, sampled_path, items, audit_state, existing=existing)
    write_json(output_path, run)
    return run


# ---------------------------------------------------------------------------
# Tables and metrics
# ---------------------------------------------------------------------------

def audit_to_map(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for result in run.get("results", []):
        parsed = result.get("parsed_result", {})
        concern_id = parsed.get("concern_id") or result.get("concern_id")
        if concern_id:
            dimension_results = parsed.get("dimension_results", {})
            if dimension_results:
                parsed = {
                    "concern_id": concern_id,
                    "concern_audit_result": normalize_result(dimension_results.get("concern", {}).get("final_result")),
                    "concern_audit_reason": dimension_results.get("concern", {}).get("final_reason", ""),
                    "necessity_audit_result": normalize_result(dimension_results.get("necessity", {}).get("final_result")),
                    "necessity_audit_reason": dimension_results.get("necessity", {}).get("final_reason", ""),
                    "gap_audit_result": normalize_result(dimension_results.get("gap", {}).get("final_result")),
                    "gap_audit_reason": dimension_results.get("gap", {}).get("final_reason", ""),
                }
            mapped[concern_id] = parsed
    for result in run.get("final_results", []):
        concern_id = result.get("concern_id")
        dims = result.get("final_dimensions", {})
        if not concern_id:
            continue
        mapped[concern_id] = {
            "concern_id": concern_id,
            "concern_audit_result": normalize_result(dims.get("concern", {}).get("final_result")),
            "concern_audit_reason": dims.get("concern", {}).get("final_reason", ""),
            "necessity_audit_result": normalize_result(dims.get("necessity", {}).get("final_result")),
            "necessity_audit_reason": dims.get("necessity", {}).get("final_reason", ""),
            "gap_audit_result": normalize_result(dims.get("gap", {}).get("final_result")),
            "gap_audit_reason": dims.get("gap", {}).get("final_reason", ""),
        }
    return mapped


def audit_rows(items: list[dict[str, Any]], run: dict[str, Any]) -> list[dict[str, Any]]:
    mapped = audit_to_map(run)
    rows = []
    for item in items:
        parsed = mapped.get(item["concern_id"], parsed_template(item["concern_id"]))
        rows.append({
            "item_index": item["item_index"],
            "concern_id": item["concern_id"],
            "provider": item["provider"],
            "record_id": item["record_id"],
            "topics": "; ".join(item.get("topics", [])),
            "gap_types": "; ".join(item.get("gap_types", [])),
            "concern_result": normalize_result(parsed.get("concern_audit_result")),
            "necessity_result": normalize_result(parsed.get("necessity_audit_result")),
            "gap_result": normalize_result(parsed.get("gap_audit_result")),
            "record_result": derive_record_result(parsed),
            "complete": is_complete(parsed),
        })
    return rows


def pipeline_retention_rows(items: list[dict[str, Any]], run: dict[str, Any]) -> list[dict[str, Any]]:
    mapped = audit_to_map(run)
    rows = []
    for item in items:
        parsed = mapped.get(item["concern_id"], parsed_template(item["concern_id"]))
        gap = item.get("gap_result", {})
        row = {
            "item_index": item["item_index"],
            "concern_id": item["concern_id"],
            "provider": item["provider"],
            "record_id": item["record_id"],
            "pipeline_concern_statement": item.get("concern_statement", ""),
            "pipeline_topics": "; ".join(item.get("topics", [])),
            "pipeline_gap_detected": gap.get("gap_detected", ""),
            "pipeline_gap_types": "; ".join(item.get("gap_types", [])),
            "pipeline_coverage_status": gap.get("coverage_status", ""),
            "final_concern_accept": normalize_result(parsed.get("concern_audit_result")),
            "final_necessity_accept": normalize_result(parsed.get("necessity_audit_result")),
            "final_gap_accept": normalize_result(parsed.get("gap_audit_result")),
            "final_concern_reason": parsed.get("concern_audit_reason", ""),
            "final_necessity_reason": parsed.get("necessity_audit_reason", ""),
            "final_gap_reason": parsed.get("gap_audit_reason", ""),
        }
        row["final_record_accept"] = derive_record_result({
            "concern_audit_result": row["final_concern_accept"],
            "necessity_audit_result": row["final_necessity_accept"],
            "gap_audit_result": row["final_gap_accept"],
        })
        rows.append(row)
    return rows


def pipeline_retention_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []
    if df.empty:
        return pd.DataFrame(columns=[
            "dimension",
            "pipeline_outputs",
            "final_accept",
            "final_reject",
            "missing",
            "final_consistency",
        ])
    for dim in ["concern", "necessity", "gap", "record"]:
        col = f"final_{dim}_accept"
        counts = df[col].value_counts().to_dict() if col in df else {}
        n = len(df)
        accepted = counts.get("TRUE", 0)
        rejected = counts.get("FALSE", 0)
        missing = int((df[col] == "").sum()) if col in df else n
        summary_rows.append({
            "dimension": dim,
            "pipeline_outputs": n,
            "final_accept": accepted,
            "final_reject": rejected,
            "missing": missing,
            "final_consistency": round(accepted / n, 4) if n else 0.0,
        })
    return pd.DataFrame(summary_rows)


def comparison_rows(
    items: list[dict[str, Any]],
    run_a: dict[str, Any],
    run_b: dict[str, Any],
    label_a: str,
    label_b: str,
) -> list[dict[str, Any]]:
    map_a = audit_to_map(run_a)
    map_b = audit_to_map(run_b)
    rows = []

    for item in items:
        cid = item["concern_id"]
        pa = map_a.get(cid, parsed_template(cid))
        pb = map_b.get(cid, parsed_template(cid))

        row = {
            "item_index": item["item_index"],
            "concern_id": cid,
            "provider": item["provider"],
            "record_id": item["record_id"],
            "topics": "; ".join(item.get("topics", [])),
            "gap_types": "; ".join(item.get("gap_types", [])),
        }

        disagreed = []
        for dim in DIMENSIONS:
            a_value = normalize_result(pa.get(f"{dim}_audit_result"))
            b_value = normalize_result(pb.get(f"{dim}_audit_result"))
            row[f"{label_a}_{dim}_result"] = a_value
            row[f"{label_a}_{dim}_reason"] = pa.get(f"{dim}_audit_reason", "")
            row[f"{label_b}_{dim}_result"] = b_value
            row[f"{label_b}_{dim}_reason"] = pb.get(f"{dim}_audit_reason", "")
            is_disagreement = bool(a_value and b_value and a_value != b_value)
            row[f"{dim}_disagreed"] = is_disagreement
            if is_disagreement:
                disagreed.append(dim)

        record_a = derive_record_result(pa)
        record_b = derive_record_result(pb)
        row[f"{label_a}_record_result"] = record_a
        row[f"{label_b}_record_result"] = record_b
        row["record_disagreed"] = bool(record_a and record_b and record_a != record_b)
        if row["record_disagreed"]:
            disagreed.append("record")
        row["disagreed_dimensions"] = "; ".join(disagreed)
        row["has_disagreement"] = bool(disagreed)
        rows.append(row)

    return rows


def default_adjudication(row: dict[str, Any], label_a: str, label_b: str) -> dict[str, Any]:
    final: dict[str, Any] = {"discussion_note": ""}
    for dim in DIMENSIONS:
        a_value = normalize_result(row.get(f"{label_a}_{dim}_result"))
        b_value = normalize_result(row.get(f"{label_b}_{dim}_result"))
        a_reason = str(row.get(f"{label_a}_{dim}_reason", "") or "")
        b_reason = str(row.get(f"{label_b}_{dim}_reason", "") or "")

        if a_value and b_value and a_value == b_value:
            final[f"{dim}_audit_result"] = a_value
            final[f"{dim}_audit_reason"] = a_reason or b_reason
            final[f"{dim}_resolution_source"] = "agreement"
        elif a_value:
            final[f"{dim}_audit_result"] = a_value
            final[f"{dim}_audit_reason"] = a_reason
            final[f"{dim}_resolution_source"] = label_a
        elif b_value:
            final[f"{dim}_audit_result"] = b_value
            final[f"{dim}_audit_reason"] = b_reason
            final[f"{dim}_resolution_source"] = label_b
        else:
            final[f"{dim}_audit_result"] = ""
            final[f"{dim}_audit_reason"] = ""
            final[f"{dim}_resolution_source"] = "unresolved"
    return final


def get_adjudication(
    row: dict[str, Any],
    label_a: str,
    label_b: str,
    state: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cid = row["concern_id"]
    merged = default_adjudication(row, label_a, label_b)
    merged.update(state.get(cid, {}))
    return merged


def adjudication_option_label(
    cid: str,
    row_map: dict[str, dict[str, Any]],
    state: dict[str, dict[str, Any]],
) -> str:
    row = row_map.get(cid, {})
    if cid in state:
        return f"{cid} [edited]"
    if row.get("has_disagreement"):
        dims = row.get("disagreed_dimensions", "disagreement")
        return f"{cid} [needs-review: {dims}]"
    return f"{cid} [auto-agree]"


def adjudication_status(
    cid: str,
    row_map: dict[str, dict[str, Any]],
    state: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    row = row_map.get(cid, {})
    if cid in state:
        return "edited", "Edited"
    if row.get("has_disagreement"):
        dims = row.get("disagreed_dimensions", "disagreement")
        return "needs-review", f"Needs review: {dims}"
    return "auto-agree", "Auto agree"


def render_status_chip(status_key: str, label: str) -> None:
    st.markdown(
        f'<span class="status-chip status-{status_key}">{escape(label)}</span>',
        unsafe_allow_html=True,
    )


def final_summary_df(final_df: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []
    if final_df.empty:
        return pd.DataFrame(columns=["dimension", "TRUE", "FALSE", "missing"])
    for dim in ["concern", "necessity", "gap", "record"]:
        col = f"final_{dim}_result"
        counts = final_df[col].value_counts().to_dict() if col in final_df else {}
        summary_rows.append({
            "dimension": dim,
            "TRUE": counts.get("TRUE", 0),
            "FALSE": counts.get("FALSE", 0),
            "missing": int((final_df[col] == "").sum()) if col in final_df else len(final_df),
        })
    return pd.DataFrame(summary_rows)


def final_resolution_rows(
    items: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    label_a: str,
    label_b: str,
    state: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    item_map = {item["concern_id"]: item for item in items}
    final_rows = []
    for row in rows:
        cid = row["concern_id"]
        item = item_map.get(cid, {})
        final = get_adjudication(row, label_a, label_b, state)
        parsed = {
            "concern_id": cid,
            "concern_audit_result": normalize_result(final.get("concern_audit_result")),
            "concern_audit_reason": final.get("concern_audit_reason", ""),
            "necessity_audit_result": normalize_result(final.get("necessity_audit_result")),
            "necessity_audit_reason": final.get("necessity_audit_reason", ""),
            "gap_audit_result": normalize_result(final.get("gap_audit_result")),
            "gap_audit_reason": final.get("gap_audit_reason", ""),
        }
        out = {
            "item_index": row["item_index"],
            "concern_id": cid,
            "provider": row.get("provider", ""),
            "record_id": row.get("record_id", ""),
            "topics": row.get("topics", ""),
            "gap_types": row.get("gap_types", ""),
            "has_disagreement": row.get("has_disagreement", False),
            "disagreed_dimensions": row.get("disagreed_dimensions", ""),
            "final_concern_result": parsed["concern_audit_result"],
            "final_concern_reason": parsed["concern_audit_reason"],
            "final_concern_source": final.get("concern_resolution_source", ""),
            "final_necessity_result": parsed["necessity_audit_result"],
            "final_necessity_reason": parsed["necessity_audit_reason"],
            "final_necessity_source": final.get("necessity_resolution_source", ""),
            "final_gap_result": parsed["gap_audit_result"],
            "final_gap_reason": parsed["gap_audit_reason"],
            "final_gap_source": final.get("gap_resolution_source", ""),
            "final_record_result": derive_record_result(parsed),
            "discussion_note": final.get("discussion_note", ""),
            "adjudication_status": "edited" if cid in state else "auto",
            "adjudication_revision": final.get("_revision", 0),
            "adjudication_saved_at": final.get("_saved_at", ""),
            "thread_id": item.get("thread_id", ""),
            "evidence_url": item.get("evidence_url", ""),
        }
        for dim in DIMENSIONS:
            out[f"{label_a}_{dim}_result"] = row.get(f"{label_a}_{dim}_result", "")
            out[f"{label_a}_{dim}_reason"] = row.get(f"{label_a}_{dim}_reason", "")
            out[f"{label_b}_{dim}_result"] = row.get(f"{label_b}_{dim}_result", "")
            out[f"{label_b}_{dim}_reason"] = row.get(f"{label_b}_{dim}_reason", "")
        final_rows.append(out)
    return final_rows


def final_resolution_json(
    final_rows: list[dict[str, Any]],
    label_a: str,
    label_b: str,
    source_a: Path,
    source_b: Path,
) -> dict[str, Any]:
    now = utc_now()
    results = []
    for row in final_rows:
        parsed = {
            "concern_id": row["concern_id"],
            "concern_audit_result": row["final_concern_result"],
            "concern_audit_reason": row["final_concern_reason"],
            "necessity_audit_result": row["final_necessity_result"],
            "necessity_audit_reason": row["final_necessity_reason"],
            "gap_audit_result": row["final_gap_result"],
            "gap_audit_reason": row["final_gap_reason"],
        }
        results.append({
            "concern_id": row["concern_id"],
            "item_index": row["item_index"],
            "processed_at": now,
            "parsed_result": parsed,
            "adjudication": {
                "experts": [label_a, label_b],
                "has_disagreement": bool(row["has_disagreement"]),
                "disagreed_dimensions": row["disagreed_dimensions"],
                "discussion_note": row["discussion_note"],
                "status": row.get("adjudication_status", "auto"),
                "revision": row.get("adjudication_revision", 0),
                "saved_at": row.get("adjudication_saved_at", ""),
                "resolution_sources": {
                    "concern": row["final_concern_source"],
                    "necessity": row["final_necessity_source"],
                    "gap": row["final_gap_source"],
                },
            },
        })
    return {
        "description": f"Final adjudicated resolution for {label_a} vs {label_b}",
        "created_at": now,
        "updated_at": now,
        "source_files": [source_a.name, source_b.name],
        "total_items": len(final_rows),
        "disagreement_items": sum(1 for row in final_rows if row["has_disagreement"]),
        "results": results,
    }


def binary_agreement_metrics(rows: list[dict[str, Any]], col_a: str, col_b: str) -> dict[str, Any]:
    pairs = []
    for row in rows:
        a = result_to_bool(row.get(col_a))
        b = result_to_bool(row.get(col_b))
        if a is not None and b is not None:
            pairs.append((a, b))

    n = len(pairs)
    tt = sum(1 for a, b in pairs if a and b)
    tf = sum(1 for a, b in pairs if a and not b)
    ft = sum(1 for a, b in pairs if not a and b)
    ff = sum(1 for a, b in pairs if not a and not b)
    agreement = (tt + ff) / n if n else 0.0

    if n:
        a_true = (tt + tf) / n
        b_true = (tt + ft) / n
        a_false = 1 - a_true
        b_false = 1 - b_true
        pe_kappa = a_true * b_true + a_false * b_false
        kappa = (agreement - pe_kappa) / (1 - pe_kappa) if pe_kappa != 1 else 0.0
        pabak = 2 * agreement - 1
        p_yes = ((tt + tf) + (tt + ft)) / (2 * n)
        pe_ac1 = 2 * p_yes * (1 - p_yes)
        ac1 = (agreement - pe_ac1) / (1 - pe_ac1) if pe_ac1 != 1 else 0.0
    else:
        kappa = pabak = ac1 = 0.0

    return {
        "N": n,
        "TT": tt,
        "TF": tf,
        "FT": ft,
        "FF": ff,
        "Agreement": round(agreement, 4),
        "Cohen_kappa": round(kappa, 4),
        "PABAK": round(pabak, 4),
        "Gwet_AC1": round(ac1, 4),
    }


def dataframe_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def scroll_to_top() -> None:
    scroll_key = st.session_state.get("_scroll_to_top_key", 0) + 1
    st.session_state["_scroll_to_top_key"] = scroll_key
    scroll_html = """
<script>
// scroll-run-__SCROLL_KEY__
(function () {
  const scrollOnce = () => {
    try {
      const doc = window.parent.document;
      const targets = [
        doc.querySelector('[data-testid="stAppViewContainer"]'),
        doc.querySelector('section.main'),
        doc.scrollingElement,
        doc.documentElement,
        doc.body
      ];
      for (const target of targets) {
        if (target && typeof target.scrollTo === 'function') {
          target.scrollTo({ top: 0, left: 0, behavior: 'auto' });
        }
      }
    } catch (error) {
      console.debug('scroll_to_top skipped during Streamlit rerender', error);
    }
  };
  window.requestAnimationFrame(() => window.setTimeout(scrollOnce, 60));
})();
</script>
""".replace("__SCROLL_KEY__", str(scroll_key))
    components.html(
        scroll_html,
        height=1,
    )


def highlight_card(title: str, body: Any, tone: str = "blue", rewritten: bool = False) -> None:
    text = str(body or "N/A")
    rewritten_badge = ""
    if rewritten:
        rewritten_badge = '<div style="color:#b91c1c;font-weight:800;margin-bottom:0.55rem;">📝 [Rewritten]</div>'
    st.markdown(
        f"""
<div class="audit-highlight audit-{tone}">
  <div class="audit-highlight-title">{escape(title)}</div>
  <div class="audit-highlight-body">{rewritten_badge}{escape(text).replace(chr(10), "<br>")}</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# UI render helpers
# ---------------------------------------------------------------------------

def render_item_context(item: dict[str, Any]) -> None:
    gap = item.get("gap_result", {})
    policy = gap.get("policy_analysis", {}) if isinstance(gap, dict) else {}

    st.markdown(f"**Concern ID:** `{item['concern_id']}`")
    st.markdown(
        f"**Provider:** `{item['provider']}`  "
        f"**Record:** `{item['record_id']}`  "
        f"**Type:** `{item['record_type']}`"
    )
    if item.get("evidence_url"):
        st.markdown(f"[Open Reddit evidence]({item['evidence_url']})")

    with st.expander("Source record", expanded=True):
        highlight_card(
            "Source record",
            item.get("record_body") or "No source text available.",
            "slate",
            rewritten=bool(item.get("record_rewritten")),
        )

    col1, col2 = st.columns(2)
    with col1:
        highlight_card("Pipeline concern statement", item.get("concern_statement") or "N/A", "blue")
        highlight_card("User assumption", item.get("user_assumption") or "N/A", "amber")
        highlight_card(
            "Supporting quote",
            item.get("supporting_quote") or "N/A",
            "green",
            rewritten=bool(item.get("supporting_quote_rewritten")),
        )

    with col2:
        highlight_card("Topics", ", ".join(item.get("topics", [])) or "N/A", "slate")
        highlight_card("Gap types", ", ".join(item.get("gap_types", [])) or "N/A", "purple")
        highlight_card(
            "Coverage / confidence",
            f"{gap.get('coverage_status', 'N/A')} / {gap.get('confidence', 'N/A')}",
            "blue",
        )

    with st.expander("Policy analysis and necessity rationale", expanded=False):
        sections = policy.get("relevant_sections", [])
        highlight_card("Relevant policy sections", "\n".join(f"- {section}" for section in sections) if sections else "N/A", "purple")
        highlight_card("Found content", policy.get("found_content") or "N/A", "green")
        highlight_card("Coverage assessment", policy.get("coverage_assessment") or "N/A", "amber")
        highlight_card("Justification", gap.get("justification") or "N/A", "blue")
        highlight_card("Recommendation", gap.get("recommendation") or "N/A", "slate")


def filter_items(
    items: list[dict[str, Any]],
    audit_state: dict[str, dict[str, Any]],
    provider: str,
    status: str,
    keyword: str,
) -> list[dict[str, Any]]:
    keyword_norm = keyword.strip().lower()
    filtered = []

    for item in items:
        if provider != "All" and item["provider"] != provider:
            continue

        state = audit_state.get(item["concern_id"], {})
        parsed = state.get("parsed_result", {})
        complete = is_complete(parsed)
        if status == "Incomplete only" and complete:
            continue
        if status == "Complete only" and not complete:
            continue

        if keyword_norm:
            haystack = " ".join([
                item.get("concern_id", ""),
                item.get("record_id", ""),
                item.get("thread_title", ""),
                item.get("record_body", ""),
                item.get("concern_statement", ""),
                item.get("supporting_quote", ""),
                " ".join(item.get("topics", [])),
                " ".join(item.get("gap_types", [])),
            ]).lower()
            if keyword_norm not in haystack:
                continue

        filtered.append(item)
    return filtered


def get_query_index(max_index: int) -> int:
    current = st.session_state.get("audit_current_index", 0)
    if max_index <= 0:
        return 0
    return min(max(current, 0), max_index - 1)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_audit() -> None:
    st.header("Independent audit")

    if not st.session_state.get("audit_started", False):
        st.markdown("### 1. Configure audit session")
        with st.container(border=True):
            sampled_text = st.text_input(
                "sampled_data.json path",
                DEFAULT_SAMPLED_DATA.name,
                key="audit_setup_sampled_path",
            )
            expert_name_input = st.text_input(
                "Expert name",
                value=st.session_state.get("audit_expert_name", ""),
                placeholder="e.g. Expert_1",
                key="audit_setup_expert_name",
            )
            sampled_candidate = resolve_sampled_path(sampled_text)
            if sampled_candidate.exists():
                try:
                    preview_items = load_sampled_items(sampled_candidate)
                    st.success(f"Loaded {sampled_candidate.name}: {len(preview_items)} audit items")
                except Exception as exc:
                    st.error(f"Unable to parse sampled_data: {exc}")
            else:
                st.warning("Select a valid sampled_data.json file before starting.")

            if st.button("Start audit session", type="primary", key="audit_start_button"):
                if not sampled_candidate.exists():
                    st.error("sampled_data.json was not found.")
                    st.stop()
                if not expert_name_input.strip():
                    st.error("Expert name is required.")
                    st.stop()
                st.session_state["audit_sampled_path"] = str(sampled_candidate)
                st.session_state["audit_expert_name"] = expert_name_input.strip()
                st.session_state["audit_started"] = True
                st.session_state["audit_current_index"] = 0
                st.rerun()
        return

    sampled_path = Path(st.session_state["audit_sampled_path"])
    expert_name = st.session_state["audit_expert_name"]

    if not sampled_path.exists():
        st.error("The selected sampled_data.json no longer exists. Reset the session and choose it again.")
        return

    items = load_sampled_items(sampled_path)
    output_path = audit_file_for_expert(expert_name)
    existing_run, audit_state = load_audit_run(output_path)

    if "audit_last_saved" in st.session_state:
        last = st.session_state.pop("audit_last_saved")
        scroll_to_top()
        st.toast(f"Saved {last['concern_id']}", icon="✅")
        st.success(
            f"Saved item `{last['concern_id']}`. File: `{last['output_name']}` "
            f"({last['processed_count']} processed)."
        )
        st.caption(f"Output folder: {last['output_folder']}")
        if last.get("export_requested") and output_path.exists():
            st.download_button(
                "Download exported audit JSON",
                data=output_path.read_bytes(),
                file_name=output_path.name,
                mime="application/json",
                key=f"audit_export_after_save_{last['concern_id']}",
            )

    st.markdown("### 2. Audit queue")
    with st.container(border=True):
        st.write(f"**Expert:** {expert_name}")
        st.caption(f"Input: {sampled_path.name}")
        st.caption(f"Output: {output_path.name}")

    completed = sum(1 for item in items if is_complete(audit_state.get(item["concern_id"], {}).get("parsed_result", {})))
    col1, col2, col3 = st.columns(3)
    col1.metric("Items", len(items))
    col2.metric("Completed", completed)
    col3.metric("Pending", max(len(items) - completed, 0))
    st.caption(f"Current output file: {output_path.name}")
    st.progress(completed / len(items) if items else 0.0)

    providers = ["All"] + sorted({item["provider"] for item in items})
    f1, f2, f3 = st.columns([1, 1, 2])
    provider = f1.selectbox(
        "Provider",
        providers,
        key="audit_provider_filter",
        on_change=reset_audit_index,
    )
    status = f2.selectbox(
        "Status",
        ["Incomplete only", "All", "Complete only"],
        key="audit_status_filter",
        on_change=reset_audit_index,
    )
    keyword = f3.text_input("Search", key="audit_search", on_change=reset_audit_index)

    filtered = filter_items(items, audit_state, provider, status, keyword)
    if not filtered:
        st.info("No item matches the current filters.")
        return

    current_index = get_query_index(len(filtered))
    nav1, nav2, nav3 = st.columns([1, 2, 1])
    if nav1.button("Previous", disabled=current_index == 0, key="audit_prev"):
        st.session_state["audit_current_index"] = current_index - 1
        st.rerun()
    nav2.markdown(f"**Item {current_index + 1} / {len(filtered)}**")
    if nav3.button("Next", disabled=current_index >= len(filtered) - 1, key="audit_next"):
        st.session_state["audit_current_index"] = current_index + 1
        st.rerun()

    item = filtered[current_index]
    st.divider()
    st.markdown("### 3. Review current item")

    current_state = audit_state.get(item["concern_id"], {})
    parsed = current_state.get("parsed_result", parsed_template(item["concern_id"]))

    read_col, judge_col = st.columns([1.45, 0.85], gap="large")
    with read_col:
        with st.container(border=True):
            render_item_context(item)

    with judge_col:
        with st.container(border=True):
            with st.form(f"audit_form_{item['concern_id']}"):
                st.subheader("Expert judgment")
                values: dict[str, Any] = {}
                for dim in DIMENSIONS:
                    label = dim.capitalize()
                    default_result = normalize_result(parsed.get(f"{dim}_audit_result")) or "TRUE"
                    st.markdown(f"**{label}**")
                    values[f"{dim}_audit_result"] = st.radio(
                        f"{label} audit result",
                        RESULT_VALUES,
                        index=RESULT_VALUES.index(default_result),
                        horizontal=True,
                        key=f"{item['concern_id']}_{dim}_result",
                    )
                    values[f"{dim}_audit_reason"] = st.text_area(
                        f"{label} audit reason",
                        value=parsed.get(f"{dim}_audit_reason", ""),
                        height=84,
                        key=f"{item['concern_id']}_{dim}_reason",
                    )

                save_clicked = st.form_submit_button("Save judgment", type="primary", width="stretch")
                export_clicked = st.form_submit_button("Save judgment and show JSON download", width="stretch")
                st.caption("Download buttons export the last saved JSON file; unsaved form edits are not included until you save.")

    if save_clicked or export_clicked:
        new_parsed = {"concern_id": item["concern_id"], **values}
        audit_state[item["concern_id"]] = {
            "processed_at": current_state.get("processed_at") or utc_now(),
            "parsed_result": new_parsed,
        }
        run = save_audit_state(output_path, expert_name, sampled_path, items, audit_state, existing_run)
        st.session_state["audit_last_saved"] = {
            "concern_id": item["concern_id"],
            "output_name": output_path.name,
            "output_folder": output_path.parent.name,
            "processed_count": run["processed_count"],
            "export_requested": export_clicked,
        }
        if status != "Incomplete only" and current_index < len(filtered) - 1:
            st.session_state["audit_current_index"] = current_index + 1
        else:
            st.session_state["audit_current_index"] = current_index
        st.rerun()

    if output_path.exists():
        run_data = output_path.read_bytes()
        st.caption("Downloads the audit JSON currently saved on disk. It does not save unsaved edits in the form above.")
        st.download_button(
            "Download saved audit JSON",
            data=run_data,
            file_name=output_path.name,
            mime="application/json",
            key="audit_download_json",
        )


def page_compare() -> None:
    st.header("Expert comparison")
    sampled_path = resolve_sampled_path(
        st.text_input("sampled_data.json path", DEFAULT_SAMPLED_DATA.name, key="compare_sample")
    )
    items = load_sampled_items(sampled_path) if sampled_path.exists() else []
    files = collect_audit_files()

    if len(files) < 2:
        st.info("At least two independent_audit_run*.json files are needed.")
        return

    labels = [relative_label(path) for path in files]
    col1, col2 = st.columns(2)
    idx_a = col1.selectbox(
        "Expert 1 result JSON",
        range(len(files)),
        format_func=lambda i: labels[i],
        key="compare_expert_a_file",
    )
    idx_b = col2.selectbox(
        "Expert 2 result JSON",
        range(len(files)),
        index=1,
        format_func=lambda i: labels[i],
        key="compare_expert_b_file",
    )
    if idx_a == idx_b:
        st.warning("Choose two different files.")
        return

    run_a = read_json(files[idx_a], default={})
    run_b = read_json(files[idx_b], default={})
    label_a = safe_slug(run_a.get("config_snapshot", {}).get("expert_name") or files[idx_a].stem)
    label_b = safe_slug(run_b.get("config_snapshot", {}).get("expert_name") or files[idx_b].stem)
    rows = comparison_rows(items, run_a, run_b, label_a, label_b)
    df = pd.DataFrame(rows)

    only_disagreements = st.checkbox("Show disagreements only", value=True, key="compare_only_disagreements")
    dimension = st.selectbox(
        "Dimension filter",
        ["Any", "concern", "gap", "necessity", "record"],
        key="compare_dimension_filter",
    )
    provider = st.selectbox(
        "Provider",
        ["All"] + sorted(df["provider"].dropna().unique().tolist()),
        key="compare_provider_filter",
    )

    view = df
    if only_disagreements:
        view = view[view["has_disagreement"]]
    if dimension != "Any":
        view = view[view[f"{dimension}_disagreed"]]
    if provider != "All":
        view = view[view["provider"] == provider]

    adjudication_key = f"adjudication_{safe_slug(files[idx_a].stem)}__{safe_slug(files[idx_b].stem)}"
    adjudication_state = st.session_state.setdefault(adjudication_key, {})
    all_rows = df.to_dict("records")
    row_map = {row["concern_id"]: row for row in all_rows}
    if st.session_state.get("compare_last_consensus_key") == adjudication_key:
        last_cid = st.session_state.pop("compare_last_consensus_cid", "")
        last_revision = st.session_state.pop("compare_last_consensus_revision", "")
        st.session_state.pop("compare_last_consensus_key", None)
        scroll_to_top()
        st.success(
            f"Saved consensus for `{last_cid}`"
            f"{f' (revision {last_revision})' if last_revision else ''}. "
            "The final adjudicated table below has been updated."
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Items", len(df))
    c2.metric("Rows shown", len(view))
    c3.metric("Disagreements", int(df["has_disagreement"].sum()))

    st.dataframe(view, width="stretch", height=420)
    csv_name = f"{label_a}_vs_{label_b}_comparison.csv"
    st.download_button(
        "Download comparison CSV",
        data=dataframe_csv_bytes(view),
        file_name=csv_name,
        mime="text/csv",
        key="compare_download_csv",
    )

    if not view.empty:
        inspect_options = view["concern_id"].tolist()
        selected_cid = st.selectbox(
            "Inspect item",
            inspect_options,
            format_func=lambda cid: adjudication_option_label(cid, row_map, adjudication_state),
            key="compare_inspect_item",
        )
        status_key, status_label = adjudication_status(selected_cid, row_map, adjudication_state)
        render_status_chip(status_key, status_label)
        selected_item = next(item for item in items if item["concern_id"] == selected_cid)
        selected_row = df[df["concern_id"] == selected_cid].iloc[0].to_dict()
        st.divider()
        left, right = st.columns([1.35, 0.95], gap="large")
        with left:
            render_item_context(selected_item)
            st.subheader("Expert reasons")
            for dim in DIMENSIONS:
                st.markdown(f"**{dim.capitalize()}**")
                a_col, b_col = st.columns(2)
                a_col.write(f"{label_a}: {selected_row.get(f'{label_a}_{dim}_result', '')}")
                a_col.info(selected_row.get(f"{label_a}_{dim}_reason", "") or "No reason")
                b_col.write(f"{label_b}: {selected_row.get(f'{label_b}_{dim}_result', '')}")
                b_col.info(selected_row.get(f"{label_b}_{dim}_reason", "") or "No reason")

        with right:
            current_final = get_adjudication(selected_row, label_a, label_b, adjudication_state)
            with st.container(border=True):
                st.subheader("Consensus adjudication")
                st.caption("Adjust only where the discussion changes the final decision.")
                if selected_cid in adjudication_state:
                    saved_at = current_final.get("_saved_at", "")
                    st.success(
                        f"Manual consensus saved. Revision "
                        f"{current_final.get('_revision', 1)}"
                        f"{f' at {saved_at}' if saved_at else ''}."
                    )
                else:
                    st.info("No manual consensus has been saved for this item yet.")
                with st.form(f"adjudication_form_{selected_cid}"):
                    updated: dict[str, Any] = {}
                    source_options = ["agreement", label_a, label_b, "discussion"]
                    for dim in DIMENSIONS:
                        label = dim.capitalize()
                        st.markdown(f"**{label} final decision**")
                        default_result = normalize_result(current_final.get(f"{dim}_audit_result")) or "TRUE"
                        updated[f"{dim}_audit_result"] = st.radio(
                            f"{label} final result",
                            RESULT_VALUES,
                            index=RESULT_VALUES.index(default_result),
                            horizontal=True,
                            key=f"adjudication_{selected_cid}_{dim}_result",
                        )
                        source_value = current_final.get(f"{dim}_resolution_source", "discussion")
                        if source_value not in source_options:
                            source_value = "discussion"
                        updated[f"{dim}_resolution_source"] = st.selectbox(
                            f"{label} resolution source",
                            source_options,
                            index=source_options.index(source_value),
                            key=f"adjudication_{selected_cid}_{dim}_source",
                        )
                        updated[f"{dim}_audit_reason"] = st.text_area(
                            f"{label} final reason",
                            value=current_final.get(f"{dim}_audit_reason", ""),
                            height=82,
                            key=f"adjudication_{selected_cid}_{dim}_reason",
                        )
                    updated["discussion_note"] = st.text_area(
                        "Discussion note",
                        value=current_final.get("discussion_note", ""),
                        height=90,
                        key=f"adjudication_{selected_cid}_note",
                    )
                    action_label = "Update consensus for this item" if selected_cid in adjudication_state else "Save consensus for this item"
                    if st.form_submit_button(
                        action_label,
                        type="primary",
                        width="stretch",
                        key=f"adjudication_save_{selected_cid}",
                    ):
                        previous = adjudication_state.get(selected_cid, {})
                        revision = int(previous.get("_revision", 0)) + 1
                        updated["_revision"] = revision
                        updated["_saved_at"] = utc_now()
                        next_state = dict(adjudication_state)
                        next_state[selected_cid] = updated
                        st.session_state[adjudication_key] = next_state
                        st.session_state["compare_last_consensus_key"] = adjudication_key
                        st.session_state["compare_last_consensus_cid"] = selected_cid
                        st.session_state["compare_last_consensus_revision"] = revision
                        st.session_state["compare_pending_consensus_autosave"] = adjudication_key
                        st.rerun()

    final_rows = final_resolution_rows(items, all_rows, label_a, label_b, adjudication_state)
    final_df = pd.DataFrame(final_rows)
    final_json = final_resolution_json(final_rows, label_a, label_b, files[idx_a], files[idx_b])
    resolution_base = f"final_resolution_{label_a}_vs_{label_b}"
    resolution_json_path = WEB_COMPARISON_DIR / f"{resolution_base}.json"
    resolution_csv_path = WEB_COMPARISON_DIR / f"{resolution_base}.csv"

    if st.session_state.get("compare_pending_consensus_autosave") == adjudication_key:
        write_json(resolution_json_path, final_json)
        resolution_csv_path.write_text(final_df.to_csv(index=False), encoding="utf-8")
        st.session_state.pop("compare_pending_consensus_autosave", None)
        st.success(f"Consensus file updated: `{resolution_json_path.name}`")

    st.divider()
    st.subheader("Final adjudicated output")
    r1, r2, r3 = st.columns(3)
    r1.metric("Final items", len(final_df))
    r2.metric("Disagreement items", int(final_df["has_disagreement"].sum()) if not final_df.empty else 0)
    r3.metric("Manually adjusted", len(adjudication_state))
    st.info(
        "Consensus edits update the final adjudicated output below and the exported final JSON/CSV. "
        "They do not change the two-expert agreement metrics, which are computed from the original independent audit JSON files."
    )
    st.markdown("**Final result summary after consensus**")
    final_summary = final_summary_df(final_df)
    st.dataframe(final_summary, width="stretch")
    st.download_button(
        "Download final summary CSV",
        data=dataframe_csv_bytes(final_summary),
        file_name=f"{resolution_base}_summary.csv",
        mime="text/csv",
        key="download_final_summary_csv",
    )
    st.dataframe(final_df, width="stretch", height=320)

    save_col, json_col, csv_col = st.columns(3)
    if save_col.button("Save / update consensus JSON and CSV", key="save_final_resolution", type="primary"):
        write_json(resolution_json_path, final_json)
        resolution_csv_path.write_text(final_df.to_csv(index=False), encoding="utf-8")
        st.success(f"Saved {resolution_json_path.name} and {resolution_csv_path.name}")
    json_col.download_button(
        "Download final JSON",
        data=json.dumps(final_json, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=resolution_json_path.name,
        mime="application/json",
        key="download_final_resolution_json",
    )
    csv_col.download_button(
        "Download final CSV",
        data=dataframe_csv_bytes(final_df),
        file_name=resolution_csv_path.name,
        mime="text/csv",
        key="download_final_resolution_csv",
    )


def page_analysis() -> None:
    st.header("Result analysis")
    sampled_path = resolve_sampled_path(
        st.text_input("sampled_data.json path", DEFAULT_SAMPLED_DATA.name, key="analysis_sample")
    )
    items = load_sampled_items(sampled_path) if sampled_path.exists() else []
    files = collect_analysis_files()

    if not files:
        st.info("No expert or consensus JSON files found.")
        return

    labels = [relative_label(path) for path in files]
    st.info(
        "Fixed workflow: LLM Pipeline output is taken from sampled_data.json. "
        "Select an expert or, ideally, a consensus final_resolution JSON to measure which pipeline outputs are finally retained."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Fixed LLM Pipeline output**")
        st.caption(sampled_path.name)
        st.metric("Pipeline items", len(items))
    with right:
        preferred_index = next(
            (
                i for i, path in enumerate(files)
                if path.name.startswith("final_resolution")
                or path.name.startswith("independent_audit_final_resolution")
            ),
            0,
        )
        idx = st.selectbox(
            "Expert / consensus JSON",
            range(len(files)),
            index=preferred_index,
            format_func=lambda i: labels[i],
            key="analysis_expert_or_consensus_file",
        )

    selected_file = files[idx]
    selected_run = read_json(selected_file, default={})
    rows = pipeline_retention_rows(items, selected_run)
    df = pd.DataFrame(rows)
    summary = pipeline_retention_summary(df)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Items", len(df))
    c2.metric("Concern retained", int((df["final_concern_accept"] == "TRUE").sum()) if not df.empty else 0)
    c3.metric("Necessity retained", int((df["final_necessity_accept"] == "TRUE").sum()) if not df.empty else 0)
    c4.metric("Gap retained", int((df["final_gap_accept"] == "TRUE").sum()) if not df.empty else 0)
    c5.metric("Record retained", int((df["final_record_accept"] == "TRUE").sum()) if not df.empty else 0)

    st.subheader("Pipeline retention / final consistency")
    st.dataframe(summary, width="stretch")
    st.download_button(
        "Download pipeline retention summary CSV",
        data=dataframe_csv_bytes(summary),
        file_name=f"{selected_file.stem}_pipeline_retention_summary.csv",
        mime="text/csv",
        key="analysis_pipeline_retention_summary_download",
    )

    st.subheader("Item-level pipeline vs final decision")
    st.dataframe(df, width="stretch", height=420)
    st.download_button(
        "Download item-level pipeline retention CSV",
        data=dataframe_csv_bytes(df),
        file_name=f"{selected_file.stem}_pipeline_retention_items.csv",
        mime="text/csv",
        key="analysis_pipeline_retention_items_download",
    )



def main() -> None:
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    WEB_COMPARISON_DIR.mkdir(parents=True, exist_ok=True)

    st.set_page_config(
        page_title="Privacy Gap Double Coding Demo",
        page_icon="🛡️",
        layout="wide",
    )
    inject_v4_like_style()
    active_page = render_global_sidebar()

    st.title("🛡️ Privacy Gap Double Coding Demo")

    if active_page == "Independent audit":
        page_audit()
    elif active_page == "Expert comparison":
        page_compare()
    elif active_page == "Result analysis":
        page_analysis()


if __name__ == "__main__":
    main()
