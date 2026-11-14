import argparse
from pathlib import Path
from typing import Literal

from anthropic import Anthropic
from langfuse import Langfuse

from ticket_router.classifier import SklearnRouter
from ticket_router.data import load_tickets, load_training_set
from ticket_router.llm import AnthropicClassifier, FlakyClassifier, LlmClassifier, StubClassifier
from ticket_router.router import Router
from ticket_router.settings import Settings
from ticket_router.telemetry.base import Telemetry

Backend = Literal["logfire", "langfuse", "console"]
DATA = Path(__file__).resolve().parents[2] / "data"


def make_telemetry(backend: Backend, settings: Settings, native: bool) -> Telemetry:
    if backend == "langfuse":
        from ticket_router.telemetry.langfuse_adapter import LangfuseTelemetry

        if settings.langfuse_public_key is None or settings.langfuse_secret_key is None:
            raise SystemExit("Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env")
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            base_url=settings.langfuse_base_url,
            tracer_provider=provider,
        )
        return LangfuseTelemetry(client, native, provider)

    import logfire

    from ticket_router.telemetry.logfire_adapter import LogfireTelemetry

    if backend == "logfire" and settings.logfire_token is None:
        raise SystemExit("Set LOGFIRE_TOKEN in .env")
    token = settings.logfire_token.get_secret_value() if backend == "logfire" and settings.logfire_token else None
    instance = logfire.configure(
        service_name="ticket-router",
        resource_attributes={"host.name": "demo", "host.id": "demo"},
        token=token,
        send_to_logfire=backend == "logfire",
        console=None if backend == "console" else False,
    )
    return LogfireTelemetry(instance, native)


def make_llm(kind: Literal["anthropic", "stub"], settings: Settings, fail_every: int, telemetry: Telemetry) -> LlmClassifier:
    if kind == "anthropic":
        if settings.anthropic_api_key is None:
            raise SystemExit("Set ANTHROPIC_API_KEY in .env")
        client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value(), open_telemetry=False)
        llm: LlmClassifier = AnthropicClassifier(telemetry.instrument(client))
    else:
        llm = StubClassifier()
    return FlakyClassifier(llm, fail_every) if fail_every > 0 else llm


def main() -> None:
    parser = argparse.ArgumentParser(description="Route the eval tickets and send traces to one backend.")
    parser.add_argument("--backend", choices=["logfire", "langfuse", "console"], default="console")
    parser.add_argument("--llm", choices=["anthropic", "stub"], default="stub")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--native", action="store_true", help="let each tool's own LLM integration record tokens and cost")
    parser.add_argument("--fail-every", type=int, default=4, help="inject an LLM timeout every n-th call, 0 = off")
    args = parser.parse_args()

    settings = Settings()
    texts, labels = load_training_set(DATA / "train.csv")
    telemetry = make_telemetry(args.backend, settings, args.native)
    router = Router(
        SklearnRouter.train(texts, labels),
        make_llm(args.llm, settings, args.fail_every, telemetry),
        telemetry,
        args.threshold,
    )
    for ticket in load_tickets(DATA / "eval.csv"):
        try:
            p = router.route(ticket)
            print(f"{p.ticket_id}  {p.source:<7} {p.category:<16} conf={p.confidence:.2f}  ${p.cost_usd:.6f}")
        except Exception as error:
            print(f"{ticket['ticket_id']}  ERROR   {type(error).__name__}")
    telemetry.flush()
