"""Google ADK entry point for the Methods Reconstructor research agent."""

import os

from google.adk.agents import Agent
try:
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    mcp_available = True
except ImportError:
    mcp_available = False

from app.agent.adk_tools import (
    plan_reconstruction,
    read_reconstruction,
    reconstruct_cancer_methods,
    search_elastic_evidence,
)


def _configure_vertex_environment() -> None:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
    location = (
        os.getenv("GOOGLE_CLOUD_LOCATION")
        or os.getenv("VERTEX_AI_LOCATION")
        or os.getenv("GCP_REGION")
        or "us-central1"
    )
    if project_id:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", location)


_configure_vertex_environment()


def _build_tools() -> list:
    tools = [
        plan_reconstruction,
        reconstruct_cancer_methods,
        read_reconstruction,
        search_elastic_evidence,
    ]
    elastic_mcp_url = os.getenv("ELASTIC_MCP_URL", "").strip()
    if not elastic_mcp_url or not mcp_available:
        return tools

    headers = {}
    auth_token = os.getenv("ELASTIC_MCP_AUTH_TOKEN", "").strip()
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=elastic_mcp_url,
                headers=headers or None,
            ),
            tool_name_prefix="elastic_mcp",
        )
    )
    return tools


root_agent = Agent(
    name="methods_reconstructor",
    model=os.getenv("ADK_MODEL", "gemini-3.5-flash"),
    description=(
        "A research agent that reconstructs difficult cancer-paper methods by "
        "planning, indexing evidence in Elastic, following citation chains, and "
        "producing source-linked protocol sections and gaps."
    ),
    instruction="""
You are a research reconstruction agent, not a general-purpose chatbot.

For a paper-reconstruction request:
1. Call plan_reconstruction first and briefly state the execution plan.
2. Call reconstruct_cancer_methods with the supplied DOI, PMC ID, URL, or PDF.
3. Use read_reconstruction to inspect the resulting sections and gaps.
4. Use search_elastic_evidence when the user asks for related indexed evidence.
5. Clearly distinguish source-backed evidence, corpus inference, and unresolved gaps.

Do not claim that the evidence score proves experimental reproducibility. It measures
coverage of extracted methodological claims by traceable source text. Elastic is the
required evidence, indexing, hybrid-search, and citation-resolution layer.
""",
    tools=_build_tools(),
)
