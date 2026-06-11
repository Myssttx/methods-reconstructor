from app.agent.adk_tools import plan_reconstruction
from methods_agent.agent import _build_tools, root_agent


def test_reconstruction_plan_keeps_elastic_central():
    plan = plan_reconstruction("10.1000/example")

    assert plan["identifier"] == "10.1000/example"
    assert "Elastic" in plan["search_layer"]
    assert any("citation" in step.casefold() for step in plan["steps"])
    assert any("reconstruction" in step.casefold() for step in plan["steps"])


def test_google_adk_entrypoint_loads_production_tools():
    assert root_agent.name == "methods_reconstructor"
    assert root_agent.model == "gemini-3.0-flash"
    assert len(root_agent.tools) == 4


def test_google_adk_entrypoint_can_attach_elastic_mcp(monkeypatch):
    monkeypatch.setenv("ELASTIC_MCP_URL", "https://elastic.example.test/mcp")
    monkeypatch.setenv("ELASTIC_MCP_AUTH_TOKEN", "placeholder-token")

    tools = _build_tools()

    from methods_agent.agent import mcp_available
    assert len(tools) == (5 if mcp_available else 4)
    if mcp_available:
        assert type(tools[-1]).__name__ == "McpToolset"
