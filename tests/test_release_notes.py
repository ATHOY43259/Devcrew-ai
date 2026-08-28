"""Smoke test for the (not-yet-wired) Release Notes agent.

Runs in mock mode (conftest.py forces MOCK_MODE=1) and calls the node
function directly with a fake state dict, so it needs no graph wiring and
no API key to pass.
"""
from src.agents.release_notes import release_notes_node


def test_release_notes_node_returns_expected_keys():
    fake_state = {
        "requirements_doc": "# SRS\n## Functional requirements\n- FR1: do a thing",
        "code_files": {"app.py": "..."},
        "deployment_files": {"Dockerfile": "..."},
        "revision_count": 1,
    }

    result = release_notes_node(fake_state)

    assert result["release_notes"], "release_notes text missing"
    assert result["agent_messages"][0]["from_agent"] == "release_notes"
    assert result["logs"][0]["agent"] == "release_notes"
