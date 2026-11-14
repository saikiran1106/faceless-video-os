---
name: premiere-agent-mcp-feasibility
description: Research on AutoEdit-like agent-controlled Premiere Pro plugin, UXP/MCP architecture, API limits, and phased build plan
metadata:
  type: reference
  updated: 2026-10-08T19:56:11
---

2026-10-08 research: reports/premiere-agent-mcp-feasibility-2026-10-08.md is the authoritative feasibility study. Local Mac has Premiere Pro 2026 v26.5.2 and UXP Developer Tools. User asked whether an AutoEdit-like custom MCP/polished plugin can connect Claude/Codex/any MCP harness and cover Premiere editing. Conclusion: AutoEdit-level transcript-driven editable first-pass is feasible; universal any-edit guarantee is not. Recommended UXP-first panel + local MCP Node broker, structured plans, cloned-sequence checkpoints, readback and rendered frame/audio verification. Existing references: Adobe UXP official samples, quadlzzz/premiere-mcp, leancoderkavy/premiere-pro-mcp. No plugin installed/tested yet; next step is technical spike on disposable Premiere project.
