from __future__ import annotations

from langgraph.graph import END, StateGraph

from config.settings import Settings
from domain.interfaces import JsmPort, LlmPort, OcrPort
from domain.models import RequestContext
from orchestration.nodes.intake import make_intake_node
from orchestration.nodes.intelligence import make_intelligence_node


def build_graph(jsm: JsmPort, ocr: OcrPort, llm: LlmPort, settings: Settings):
    """Flow 1 skeleton: intake → intelligence → END (downstream deferred)."""
    graph = StateGraph(RequestContext)
    graph.add_node("intake", make_intake_node(jsm, ocr))
    graph.add_node("intelligence", make_intelligence_node(llm, settings))
    graph.set_entry_point("intake")
    graph.add_edge("intake", "intelligence")
    graph.add_edge("intelligence", END)
    return graph.compile()
