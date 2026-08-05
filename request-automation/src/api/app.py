from __future__ import annotations

import logging

import structlog
from fastapi import FastAPI

from api.routes import router
from config.settings import get_settings
from infrastructure.factory import build_jsm, build_llm, build_ocr
from orchestration.graph import build_graph


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Request Automation — Request Intelligence", version="0.1.0")
    jsm = build_jsm(settings)
    ocr = build_ocr(settings)
    llm = build_llm(settings)
    app.state.graph = build_graph(jsm, ocr, llm, settings)
    app.state.settings = settings
    app.include_router(router)
    return app


app = create_app()
