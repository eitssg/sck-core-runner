# Copilot Instructions (Submodule: sck-core-runner)

## Plan → Approval → Execute (Mandatory)
Adhere to root workflow: propose plan before any code/test/lint modifications; execute only after approval.

- Tech: Python package.
- Precedence: Local first; then root `../../.github/...`.
- Conventions: Follow `../sck-core-ui/docs/backend-code-style.md` for consistency.

## Google Docstring Requirements
**MANDATORY**: All docstrings must use Google-style format for Sphinx documentation generation:
- Use Google-style docstrings with proper Args/Returns/Example sections
- Napoleon extension will convert Google format to RST for Sphinx processing
- Avoid direct RST syntax (`::`, `:param:`, etc.) in docstrings - use Google format instead
- Example sections should use `>>>` for doctests or simple code examples
- This ensures proper IDE interpretation while maintaining clean Sphinx documentation

## Contradiction Detection
- Validate flows against backend style and root precedence.
- If conflict, warn + options + example.
- Example: "Running unbounded concurrent executions conflicts with resource governance; apply concurrency limits and backoff."

## Standalone clone note
If cloned standalone, see:
- UI/backend conventions: https://github.com/eitssg/simple-cloud-kit/tree/develop/sck-core-ui/docs
- Root Copilot guidance: https://github.com/eitssg/simple-cloud-kit/blob/develop/.github/copilot-instructions.md
 
