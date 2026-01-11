<!-- .github/copilot-instructions.md - Guidance for AI coding agents working on this repo -->
# Project snapshot
- **Purpose:** Small Flask web app. Single entrypoint: `app.py`.
- **Key files:** `app.py` (routes + app startup), `requirements.txt` (dependency pinning).

# Quick local run (Windows PowerShell)
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

# What to expect in the codebase
- `app.py` is a minimal Flask application. It defines routes with `@app.route(...)` and starts the server with `app.run(debug=True)` inside the `if __name__ == '__main__'` guard.
- Example route from `app.py`:
```
@app.route('/')
def home():
    return "Hallo, dit is mijn Flask-app!"
```

# Agent-focused guidance (actionable, project-specific)
- **Entrypoint:** Make changes in `app.py` for small tweaks; new endpoints are defined with `@app.route` decorators.
- **Adding dependencies:** Update `requirements.txt` when adding packages. Prefer explicit pinned versions (the project uses `flask==2.3.0`).
- **Run mode:** The app currently uses `app.run(debug=True)` for local development. When adding production configuration, do not remove the `if __name__ == '__main__'` guard without a reason.
- **Project expansion:** This repo is single-file now. If you add modules or blueprints, ensure `app.py` imports them so the server registers routes on startup.

# Patterns & conventions discovered
- Minimal, synchronous Flask handlers returning simple strings (no templates or JSON by default).
- No tests or CI found in repository root — avoid introducing heavy infra changes without asking the maintainer.
- A Python virtual environment may exist under `venv/` (seen in local workspace). Keep `.venv` or `venv` out of commits; follow repo gitignore if present.

# Safety and non-goals
- Do not assume additional services (databases, message queues) exist — none are declared in `requirements.txt` or `app.py`.
- Avoid adding large frameworks or complex scaffolding without prior approval from the repo owner.

# Suggested first tasks for an AI contributor
- Add a second route (e.g., `/health`) implemented in `app.py` and provide a short test script/invocation example.
- Add a basic README.md if requested (this file documents immediate technical details; README should describe project goal and run instructions for humans).

# Questions for the maintainer (if unclear)
- Should the app be runnable via `flask run` or kept using `python app.py`?
- Are there preferred branching/PR conventions or CI checks to follow when adding dependencies?

If anything here is missing or incorrect, tell me which files or workflows to inspect and I will update this guidance.
