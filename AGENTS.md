# AGENTS.md

## Project
This repository is a local GUI application generator for CHI in-situ EIS scripts.

## Rules
- Prefer Python 3.11+, PySide6/Fluent-Widgets for UI, pydantic for models, pytest for tests.
- Ensure strict separation of concerns: UI logic MUST NOT mix with domain/calculation logic.
- Prefer Python 3.11+, pydantic for models, pytest for tests.
- Never emit formulas in final CHI scripts; output pure commands.
- Final generated scripts must be directly copyable into CHI Macro Command.
- The UI must display Warnings (e.g., dense EIS points with fl=0.01, interrupted discharge) prominently before allowing script generation.
- Implement a clear layout: Input parameters intuitively grouped, with dedicated areas for script preview and validation logs.

## Workflow
- Use subagents for architecture, domain logic, rendering, validation, GUI building, tests, and docs.