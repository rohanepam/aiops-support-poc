"""Pipeline nodes — placeholders for deferred Flow 1 stages."""

from domain.models import RequestContext


async def validation_stub(state: RequestContext) -> RequestContext:
    return state


async def clarification_stub(state: RequestContext) -> RequestContext:
    return state


async def catalog_stub(state: RequestContext) -> RequestContext:
    return state


async def policy_stub(state: RequestContext) -> RequestContext:
    return state


async def execution_stub(state: RequestContext) -> RequestContext:
    return state


async def closure_stub(state: RequestContext) -> RequestContext:
    return state
