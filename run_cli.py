"""Terminal runner — test the pipeline without the UI.

Usage:
    python run_cli.py                      # interactive human approval
    python run_cli.py --auto-approve       # for quick smoke checks
    python run_cli.py "Build a URL shortener API"
"""
import sys
import uuid

from langgraph.types import Command

from src.graph.build_graph import get_app
from src.observability.token_tracker import totals


def print_event(event: dict) -> None:
    for node, update in event.items():
        if node == "__interrupt__":
            continue
        for message in (update or {}).get("agent_messages", []):
            print(f"  [{message['from_agent']} -> {message['to_agent']}] {message['content']}")


def main() -> None:
    auto = "--auto-approve" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    request = args[0] if args else "Build a to-do list REST API with Flask"

    app = get_app()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    print(f"=== DevCrew AI ===\nProject request: {request}\n")

    payload = {"project_request": request}
    while True:
        interrupted = False
        for event in app.stream(payload, config, stream_mode="updates"):
            if "__interrupt__" in event:
                interrupted = True
                info = event["__interrupt__"][0].value
                print(f"\n*** HUMAN APPROVAL NEEDED: {info['question']} ***")
                print(info["document"][:500], "...\n")
                if auto:
                    decision = {"action": "approve"}
                    print("(auto-approved)")
                else:
                    answer = input("approve / reject? > ").strip().lower()
                    if answer.startswith("r"):
                        feedback = input("feedback for the analyst > ").strip()
                        decision = {"action": "reject", "feedback": feedback}
                    else:
                        decision = {"action": "approve"}
                payload = Command(resume=decision)
            else:
                print_event(event)
        if not interrupted:
            break

    state = app.get_state(config).values
    print("\n=== FINAL REPORT ===")
    print(state.get("final_report", "(missing)"))
    print("Token totals:", totals(state.get("token_usage", {})))


if __name__ == "__main__":
    main()
