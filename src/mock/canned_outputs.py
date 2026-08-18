"""Canned outputs for MOCK_MODE — the zero-cost, no-API-key demo path.

The mock scenario is: "Build a to-do list REST API with Flask".
It deliberately includes ONE review loop (reviewer rejects v1, developer
ships v2, reviewer approves) so the demo always shows agent collaboration —
even with no API key and no internet.

Every agent has a real LLM-backed implementation too (see src/agents/); each
one branches on config.MOCK_MODE and falls back to these canned outputs so
the UI stays demoable offline and the smoke tests never need an API key.
"""

REQUIREMENTS_DOC = """# Software Requirements Specification — To-Do REST API

## Functional requirements
- FR1: Create a to-do item (title required, max 200 chars).
- FR2: List all to-do items.
- FR3: Mark an item as done.
- FR4: Delete an item.

## Non-functional requirements
- NFR1: JSON REST API, responses < 200 ms locally.
- NFR2: Input validation with meaningful 4xx errors.
- NFR3: >= 80% unit-test coverage on route handlers.

## User stories
- As a user, I can add a task so that I remember it later.
- As a user, I can mark a task done so that my list stays clean.
"""

ARCHITECTURE_DOC = """# Architecture — To-Do REST API

## Tech stack
Python 3.11, Flask, in-memory store (dict), pytest.

## Components
- `app.py` — Flask app factory + route registration
- `store.py` — TodoStore class (in-memory, swappable for a DB later)
- `tests/test_app.py` — route-level unit tests

## API design
| Method | Path | Body | Response |
|---|---|---|---|
| POST | /todos | {"title": str} | 201 + item |
| GET | /todos | - | 200 + list |
| PATCH | /todos/<id>/done | - | 200 + item |
| DELETE | /todos/<id> | - | 204 |
"""

CODE_V1 = {
    "app.py": '''from flask import Flask, jsonify, request
from store import TodoStore

def create_app():
    app = Flask(__name__)
    store = TodoStore()

    @app.post("/todos")
    def add_todo():
        data = request.get_json(silent=True) or {}
        item = store.add(data.get("title"))
        return jsonify(item), 201

    @app.get("/todos")
    def list_todos():
        return jsonify(store.list())

    @app.patch("/todos/<int:todo_id>/done")
    def mark_done(todo_id):
        return jsonify(store.mark_done(todo_id))

    @app.delete("/todos/<int:todo_id>")
    def delete_todo(todo_id):
        store.delete(todo_id)
        return "", 204

    return app

if __name__ == "__main__":
    create_app().run(debug=True)
''',
    "store.py": '''class TodoStore:
    def __init__(self):
        self._items = {}
        self._next_id = 1

    def add(self, title):
        item = {"id": self._next_id, "title": title, "done": False}
        self._items[self._next_id] = item
        self._next_id += 1
        return item

    def list(self):
        return list(self._items.values())

    def mark_done(self, todo_id):
        self._items[todo_id]["done"] = True
        return self._items[todo_id]

    def delete(self, todo_id):
        self._items.pop(todo_id, None)
''',
}

REVIEW_ROUND_1 = """CHANGES REQUESTED

1. `add_todo` accepts a missing/empty title — violates FR1. Return 400 when
   the title is absent, empty, or longer than 200 characters.
2. `mark_done` raises KeyError (500) for an unknown id — return 404 instead.
3. No tests were included; QA cannot verify FR coverage.
"""

CODE_V2 = {
    "app.py": '''from flask import Flask, jsonify, request
from store import TodoStore

def create_app():
    app = Flask(__name__)
    store = TodoStore()

    @app.post("/todos")
    def add_todo():
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        if not title or len(title) > 200:
            return jsonify({"error": "title is required (1-200 chars)"}), 400
        return jsonify(store.add(title)), 201

    @app.get("/todos")
    def list_todos():
        return jsonify(store.list())

    @app.patch("/todos/<int:todo_id>/done")
    def mark_done(todo_id):
        item = store.mark_done(todo_id)
        if item is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(item)

    @app.delete("/todos/<int:todo_id>")
    def delete_todo(todo_id):
        store.delete(todo_id)
        return "", 204

    return app

if __name__ == "__main__":
    create_app().run(debug=True)
''',
    "store.py": '''class TodoStore:
    def __init__(self):
        self._items = {}
        self._next_id = 1

    def add(self, title):
        item = {"id": self._next_id, "title": title, "done": False}
        self._items[self._next_id] = item
        self._next_id += 1
        return item

    def list(self):
        return list(self._items.values())

    def mark_done(self, todo_id):
        item = self._items.get(todo_id)
        if item is not None:
            item["done"] = True
        return item

    def delete(self, todo_id):
        self._items.pop(todo_id, None)
''',
    "tests/test_app.py": '''import pytest
from app import create_app

@pytest.fixture()
def client():
    return create_app().test_client()

def test_add_and_list(client):
    r = client.post("/todos", json={"title": "buy milk"})
    assert r.status_code == 201
    assert client.get("/todos").get_json()[0]["title"] == "buy milk"

def test_add_requires_title(client):
    assert client.post("/todos", json={}).status_code == 400

def test_mark_done_unknown_id_is_404(client):
    assert client.patch("/todos/99/done").status_code == 404

def test_delete(client):
    todo_id = client.post("/todos", json={"title": "x"}).get_json()["id"]
    assert client.delete(f"/todos/{todo_id}").status_code == 204
''',
}

REVIEW_ROUND_2 = """APPROVED

All round-1 issues are fixed: title validation returns 400, unknown ids
return 404, and route-level tests cover FR1-FR4. Code is ready for QA.
"""

TEST_REPORT = """pytest -q
....                                                                 [100%]
4 passed in 0.21s

Coverage (route handlers): 100% — FR1-FR4 each covered by at least one test.
Verdict: PASS
"""

DOCUMENTATION = """# To-Do REST API — User Guide

## Setup
```bash
pip install flask pytest
python app.py
```

## Endpoints
- `POST /todos` `{"title": "buy milk"}` -> 201, the created item
- `GET /todos` -> 200, all items
- `PATCH /todos/<id>/done` -> 200, updated item (404 if unknown)
- `DELETE /todos/<id>` -> 204

## Running tests
```bash
pytest -q
```
"""

DEPLOYMENT_FILES = {
    "Dockerfile": '''FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir flask gunicorn
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:create_app()"]
''',
    ".github/workflows/ci.yml": '''name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install flask pytest
      - run: pytest -q
''',
}
