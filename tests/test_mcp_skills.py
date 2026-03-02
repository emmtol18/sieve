def test_mcp_tools_include_skills():
    from sieve.mcp.server import TOOLS

    tool_names = [t.name for t in TOOLS]
    assert "search_skills" in tool_names
    assert "get_skill" in tool_names


def test_api_client_has_skill_methods():
    from sieve.mcp.api_client import SieveAPIClient

    client = SieveAPIClient(api_url="http://localhost:8421", api_key="test")
    assert hasattr(client, "list_skills")
    assert hasattr(client, "get_skill")
