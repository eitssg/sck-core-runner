# Copilot Instructions (Submodule: sck-core-runner)

- Tech: Python package.
- Precedence: Local first; then root `../../.github/...`.
- Conventions: Follow `../sck-core-ui/docs/backend-code-style.md` for consistency.

## RST Documentation Requirements
**MANDATORY**: All docstrings must be RST-compatible for Sphinx documentation generation:
- Use proper RST syntax: `::` for code blocks (not markdown triple backticks)
- Code blocks must be indented 4+ spaces relative to preceding text
- Add blank line after `::` before code content
- Bullet lists must end with blank line before continuing text
- Use RST field lists for parameters: `:param name: description`
- Use RST directives: `.. note::`, `.. warning::`, etc.
- Test docstrings with Sphinx build - code is source of truth, not docstrings

## Contradiction Detection
- Validate flows against backend style and root precedence.
- If conflict, warn + options + example.
- Example: "Running unbounded concurrent executions conflicts with resource governance; apply concurrency limits and backoff."

## Standalone clone note
If cloned standalone, see:
- UI/backend conventions: https://github.com/eitssg/simple-cloud-kit/tree/develop/sck-core-ui/docs
- Root Copilot guidance: https://github.com/eitssg/simple-cloud-kit/blob/develop/.github/copilot-instructions.md
 
