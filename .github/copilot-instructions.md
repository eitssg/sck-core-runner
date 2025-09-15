# Copilot Instructions (Submodule: sck-core-runner)

- Tech: Python package.
- Precedence: Local first; then root `../../.github/...`.
- Conventions: Follow `../sck-core-ui/docs/backend-code-style.md` for consistency.

## Contradiction Detection
- Validate flows against backend style and root precedence.
- If conflict, warn + options + example.
- Example: "Running unbounded concurrent executions conflicts with resource governance; apply concurrency limits and backoff."

## Standalone clone note
If cloned standalone, see:
- UI/backend conventions: https://github.com/eitssg/simple-cloud-kit/tree/develop/sck-core-ui/docs
- Root Copilot guidance: https://github.com/eitssg/simple-cloud-kit/blob/develop/.github/copilot-instructions.md
 
