# Resume release implementation plan

> Execute inline with TDD; no paid model calls or git integration.

Spec: `docs/superpowers/specs/2026-09-15-resume-release.md`

1. Add failing HTTP-boundary and CLI tests: DeepSeek preset uses its own key, endpoint/model, disables thinking and caps output; preserve legacy custom configuration. Implement provider composition, validated max-output setting, inspect effective configuration. Run focused tests RED then GREEN.
2. Reproduce sanitizer secret-boundary leak and unbounded deterministic condensation in tests. Redact before truncation; pass runtime secrets to promotion; bound deterministic summaries. Run memory tests RED then GREEN.
3. Add failing evaluation-plan tests: validate discovered manifests, reject empty suite, emit not-run/null metrics and explicit scripted classification. Implement non-mutating plan CLI with fixed cheap future protocol. Run tests RED then GREEN.
4. Document Chinese evaluation protocol, resume-ready claims, low-budget DeepSeek usage and pending hardening. Add Windows offline CI. Do not change active OpenSpec scope into false completion.
5. Run full pytest, Ruff check/format, mypy and OpenSpec if available. Record fresh evidence and remaining limitations; leave changes uncommitted.

## Execution evidence

- Steps 1–3 executed with failing tests first, then focused passing suites. Added 6 tests.
- Steps 4–5 complete for the approved reduced slice: 131 tests passed, Ruff lint/format passed, mypy passed, OpenSpec 5/5 passed, read-only plan CLI passed.
- No live model calls; full design acceptance gaps remain tracked in OpenSpec section 12, not silently marked complete.
- Work remains on existing `feat/memory-engine` branch/worktree, uncommitted and unpushed.
