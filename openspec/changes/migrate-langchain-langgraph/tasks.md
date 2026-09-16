## 1. Graph Migration

- [x] 1.1 Add lifecycle regression tests and observe startup/memory-finish failures before migration.
- [x] 1.2 Implement distinct graph nodes and routes, preserve tools/observations/limits/correlation.
- [x] 1.3 Verify long loops, recovery and compiled-node execution offline.

## 2. LangChain Integration

- [x] 2.1 Add failing provider HTTP tests before model adapter implementation.
- [x] 2.2 Implement messages/schema binding, single-action parsing, usage mapping and CLI default composition.
- [x] 2.3 Verify provider selection and CLI integration with mock transport only.

## 3. Acceptance

- [x] 3.1 Synchronize documentation, dependency versions and honest resume description.
- [x] 3.2 Run full offline pytest, Ruff, strict mypy and OpenSpec validation; record fresh evidence.
- [x] 3.3 Review against approved design; stop before commit/push/archive.

Evidence 2026-09-15: final implementation full suite 148 passed in 75.73s; subsequently added malformed-function characterization passed separately (no implementation change), resulting in 149 collected tests. Ruff lint/format, strict mypy on 57 source files and OpenSpec 6/6 passed. Scripted smoke 3/3 is runtime regression, not model quality. Read-only focused review found no Critical/Important issues; its effective-thinking metadata Minor was fixed with RED/GREEN regression. Zero paid/live model calls.
