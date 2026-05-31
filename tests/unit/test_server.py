import asyncio

from fastmcp import FastMCP

from local_subagent.server import create_server


def test_create_server_returns_fastmcp_instance():
    server = create_server()

    assert isinstance(server, FastMCP)
    assert server.name == "local-subagent"
    assert "mediated subagent" in (server.instructions or "").lower()


def test_create_server_registers_no_tools_yet():
    server = create_server()

    assert asyncio.run(server.get_tools()) == {}
