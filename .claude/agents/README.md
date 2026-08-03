# Subagents

Delegate broad or token-heavy codebase search here instead of burning main-context tool calls. Each `.md` file defines one subagent (Claude Code agent definition format: YAML frontmatter + instructions body).

## When to delegate
- Searching across many files/apps for a symbol, pattern, or "where is X handled" when you're not confident of the first 2-3 guesses.
- Auditing a cross-cutting concern (e.g. "find every place that reads user.profile without a null check") across backend or frontend.
- Anything explicitly "very thorough" in scope that would otherwise flood main context with intermediate file reads.

Don't delegate a lookup you already know the answer's location for — just Read/Grep directly.

## Agents in this folder
- `codebase-search.md` — read-only search agent for locating code/config across `backend/` and `frontend/` (mirrors the built-in Explore agent, scoped with this project's folder map so it doesn't waste turns rediscovering the app/feature layout).
