"""Apply the hand labels from the Langfuse queue to the newest run in both tools, then print accuracy for each."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import logfire
from logfire.experimental.annotations import record_feedback
from logfire.query_client import LogfireQueryClient
from langfuse import Langfuse
from opentelemetry.sdk.trace import TracerProvider

from ticket_router.labels import LabeledPrediction, accuracy_by_source, traceparent
from ticket_router.settings import Settings

SCORE_NAME = "true_category"
RUN_SIZE = 16
LOGFIRE_REAL_RUN = f"""
SELECT trace_id, span_id,
       attributes->'input'->>'ticket_id' AS ticket_id,
       attributes->'output'->>'source' AS source,
       attributes->'output'->>'category' AS category
FROM records
WHERE span_name = 'route_ticket' AND parent_span_id IS NULL AND kind = 'span'
ORDER BY start_timestamp DESC
LIMIT {RUN_SIZE}
"""


def json_field(value: object) -> dict:
    return json.loads(value) if isinstance(value, str) else value  # type: ignore[return-value]


def read_labels(base: str, auth: tuple[str, str]) -> dict[str, str]:
    """Read labels via the v2 metrics API, the only score read path in Langfuse v4 events_only mode."""
    query = {
        "view": "scores-categorical",
        "metrics": [{"measure": "count", "aggregation": "count"}],
        "dimensions": [{"field": "traceId"}, {"field": "stringValue"}],
        "filters": [{"column": "name", "operator": "=", "value": SCORE_NAME, "type": "string"}],
        "fromTimestamp": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
        "toTimestamp": datetime.now(UTC).isoformat(),
        "orderBy": [{"field": "count_count", "direction": "desc"}],
        "config": {"row_limit": 1000},
    }
    rows = httpx.get(f"{base}/v2/metrics", auth=auth, params={"query": json.dumps(query)}).raise_for_status().json()["data"]
    labels: dict[str, str] = {}
    for row in rows:
        if labels.setdefault(row["traceId"], row["stringValue"]) != row["stringValue"]:
            raise ValueError(f"trace {row['traceId']} has conflicting {SCORE_NAME} labels")
    return labels


def langfuse_rows(settings: Settings) -> tuple[dict[str, str], list[LabeledPrediction]]:
    """Read the hand labels by ticket, then label and grade the newest Langfuse run."""
    assert settings.langfuse_public_key and settings.langfuse_secret_key
    auth = (settings.langfuse_public_key, settings.langfuse_secret_key.get_secret_value())
    base = f"{settings.langfuse_base_url}/api/public"
    label_by_trace = read_labels(base, auth)
    roots = httpx.get(
        f"{base}/v2/observations", auth=auth, params={"limit": 100, "name": "route_ticket", "fields": "core,basic,io"}
    ).json()["data"]
    labels = {json_field(r["input"])["ticket_id"]: label_by_trace[r["traceId"]] for r in roots if r["traceId"] in label_by_trace}

    # Own provider, so logfire.configure can still set the global one without a warning.
    client = Langfuse(public_key=auth[0], secret_key=auth[1], base_url=settings.langfuse_base_url, tracer_provider=TracerProvider())
    rows = []
    for root in sorted(roots, key=lambda r: r["startTime"])[-RUN_SIZE:]:
        ticket, output = json_field(root["input"]), json_field(root.get("output") or "{}")
        if ticket["ticket_id"] in labels and output.get("category"):
            label = labels[ticket["ticket_id"]]
            if root["traceId"] not in label_by_trace:
                client.create_score(name=SCORE_NAME, value=label, trace_id=root["traceId"], data_type="CATEGORICAL")
            rows.append(LabeledPrediction(ticket["ticket_id"], output["source"], output["category"], label))
    client.flush()
    return labels, rows


def logfire_rows(settings: Settings, labels: dict[str, str]) -> list[LabeledPrediction]:
    assert settings.logfire_read_token and settings.logfire_token
    logfire.configure(token=settings.logfire_token.get_secret_value(), service_name="ticket-router", console=False)
    since = datetime.now(UTC) - timedelta(days=2)
    with LogfireQueryClient(read_token=settings.logfire_read_token.get_secret_value()) as client:
        spans = client.query_json_rows(LOGFIRE_REAL_RUN, min_timestamp=since)["rows"]
    rows = []
    for span in spans:
        if span["ticket_id"] in labels and span["category"]:
            label = labels[span["ticket_id"]]
            record_feedback(traceparent(span["trace_id"], span["span_id"]), SCORE_NAME, label)
            rows.append(LabeledPrediction(span["ticket_id"], span["source"], span["category"], label))
    logfire.force_flush()
    return rows


def print_accuracy(tool: str, rows: list[LabeledPrediction]) -> None:
    for source, (correct, total) in sorted(accuracy_by_source(rows).items()):
        print(f"{tool:<9} {source:<8} {correct}/{total}")


def main() -> None:
    settings = Settings()
    labels, langfuse = langfuse_rows(settings)
    print_accuracy("langfuse", langfuse)
    print_accuracy("logfire", logfire_rows(settings, labels))


if __name__ == "__main__":
    main()
