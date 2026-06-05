# Qwen 3.6 GHCP Interruption Fix Summary

## Scope

This note summarizes the interruption issues we hit while using Qwen 3.6 as a coding agent in VS Code GHCP, what symptoms we observed, and what changes were made to resolve them.

Primary commit reviewed:
- 6674ef2b5e23bb1f17580a92ce50cfb8b316ef5b
- Title: Fix Qwen 3.6 GHCP VS Code agent interruptions

Files changed in that commit:
- common/reasoning-budget.cpp
- common/reasoning-budget.h
- common/sampling.cpp
- scripts/llama_log_fast_parse.py
- tools/server/server-schema.cpp
- tools/server/server-task.cpp
- tools/server/tests/unit/test_chat_completion.py
- tools/server/tests/utils.py

## Interruption Patterns We Faced

### 1. Streaming protocol interruption at end of response

Observed behavior:
- GHCP stream terminated unexpectedly after a completion.
- Server emitted a trailing chat.completion.chunk with an empty choices array and usage payload.

Impact:
- Some OpenAI-compatible clients treat this as end-of-stream incompatibility and stop consuming deltas.

Fix:
- Keep usage on the terminal finish chunk instead of emitting a separate empty-choices chunk.
- File: tools/server/server-task.cpp

### 2. Reasoning-only output parsed as empty assistant message

Observed behavior:
- The model generated reasoning text, but parsed assistant content ended up empty and no tool calls were emitted.
- GHCP treated this as interrupted/useless output.

Fix:
- Enable reasoning_in_content compatibility for streamed deepseek mode, not only deepseek-legacy.
- Files: tools/server/server-schema.cpp, tools/server/server-task.cpp
- A follow-up refinement limited reasoning mirroring to final parse only (avoid partial token-by-token line splitting in the UI).

### 3. One-token immediate EOS interruption

Observed behavior:
- Only two chunks were emitted: assistant role start, then finish stop.
- completion_tokens was 1.
- Parsed message was empty.

Log signature:
- stopped by EOS
- next token was EOG
- parsed message: assistant with empty content

Root cause:
- Reasoning budget and grammar handoff could still allow early EOS while reasoning state was active.

Fixes:
- Replay matched reasoning end sequence into grammar when reasoning transitions to DONE.
- Add an EOS guard in sampler: if EOG is sampled while reasoning is still active, force reasoning budget to FORCING and resample once.
- Files: common/sampling.cpp, common/reasoning-budget.h, common/reasoning-budget.cpp

## Post-Commit Local Adjustment

After commit 6674ef2b5, one local adjustment was added:
- common/reasoning-budget.cpp
- tools/server/server-task.cpp

Change:
- common_reasoning_budget_force now allows forcing from WAITING_UTF8 in addition to COUNTING.
- Visible content now strips common thinking markers when reasoning-only output is mirrored for clients that only render `content`.

Reason:
- The sampler EOS guard can trigger while reasoning state is WAITING_UTF8; forcing must remain possible in that state.
- Some responses were surfacing raw `<think>` / `</think>` style markers in the visible content path, so the fallback mirror now sanitizes them.

## Diagnostics and Verification

Diagnostics helper added:
- scripts/llama_log_fast_parse.py

What it was used for:
- Fast extraction of latest completion IDs from large server.log files.
- Quick classification of interruption signatures:
  - one-token EOS stop
  - reasoning-only stream with empty parsed content
  - finish chunk shape and usage placement

Build and validation notes:
- llama-server builds succeeded after the main fixes.
- Some build attempts failed due to environment/runtime issues (for example locked ggml-base.dll or missing Node/OpenSSL prerequisites), not due to C++ compile errors in the interruption fixes.

## Net Result

The fix set addresses three independent interruption classes:
- stream terminal chunk compatibility,
- reasoning visibility/content fallback behavior,
- early EOS during active reasoning budget.

This combination is intended to make Qwen 3.6 agent turns stable in GHCP while keeping changes narrow and model-safe.
