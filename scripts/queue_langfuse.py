"""Add the newest run's answered traces to the Langfuse annotation queue `ticket-router`."""

import json

import httpx
from langfuse import Langfuse

from ticket_router.settings import Settings

QUEUE_NAME = "ticket-router"
RUN_SIZE = 16


def ticket_id(observation: dict) -> str:
    raw = observation["input"]
    return (json.loads(raw) if isinstance(raw, str) else raw)["ticket_id"]


def main() -> None:
    settings = Settings()
    assert settings.langfuse_public_key and settings.langfuse_secret_key
    auth = (settings.langfuse_public_key, settings.langfuse_secret_key.get_secret_value())
    client = Langfuse(public_key=auth[0], secret_key=auth[1], base_url=settings.langfuse_base_url)

    queue = next(q for q in client.api.annotation_queues.list_queues().data if q.name == QUEUE_NAME)
    roots = httpx.get(
        f"{settings.langfuse_base_url}/api/public/v2/observations",
        auth=auth,
        params={"limit": 100, "name": "route_ticket", "fields": "core,basic,io"},
    ).json()["data"]
    newest_run = sorted(roots, key=lambda o: o["startTime"])[-RUN_SIZE:]
    answered = [o for o in newest_run if o.get("output")]
    for root in sorted(answered, key=ticket_id):
        client.api.annotation_queues.create_queue_item(queue.id, object_id=root["traceId"], object_type="TRACE")
    print(f"added {len(answered)} traces to {QUEUE_NAME} ({queue.id})")


if __name__ == "__main__":
    main()
