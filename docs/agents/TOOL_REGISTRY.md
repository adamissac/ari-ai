# Tool registry

Status: **specified**. Package: `security-agents/` (`tool_registry`).
Enforcement flow: [architecture/sandbox-and-authorization](../architecture/sandbox-and-authorization.md).

## Tool definition

```
ToolDef {
  name, version, description (shown to model),
  args_model, result_model,          # Pydantic, extra="forbid"
  side_effects: none|sandbox_exec|worktree_write|network_target_only,
  requires_scope: bool,
  timeout_s, max_output_bytes
}
```

## Catalog (MVP)

| Tool | Side effects | Scope? | Scout | Probe | Trace | Diagnose | Patch | Fortify | Verify |
|---|---|---|---|---|---|---|---|---|---|
| `code.read_span` | none | no | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `code.search` (lexical) | none | no | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `graph.neighbors` / `graph.paths_to` | none | no | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `expectations.for_subject` | none | no | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `findings.history` | none | no | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| `static.analyze` (pinned OSS analyzer, read-only) | none | no | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| `checks.list_templates` | none | no | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `checks.run_template` | sandbox_exec + network_target_only | **yes** | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `worktree.write_file` / `worktree.diff` | worktree_write | no | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `tests.run` (test-runner, network none) | sandbox_exec | no | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| `patch.apply_fresh` (apply diff to clean checkout) | sandbox_exec | no | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

There is no generic shell, HTTP client, or file-system tool. Adding a tool or
granting one to an agent is a safety-critical change ([24](../24_DEVELOPMENT_STANDARDS.md)).

## Argument constraints

- Targets are referenced by `target_id` from the scope, never by host/URL/IP.
- File paths are relative to the snapshot root and normalized; `..` rejected.
- `checks.run_template` takes `template_id@version` + typed parameters declared
  by the template; free-form strings are length-limited and never interpolated
  into shell commands.
