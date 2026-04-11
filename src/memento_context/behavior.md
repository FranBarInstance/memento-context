# Memento-Context — Behavior Guidelines

## Initialization (MANDATORY)
Call `init_memento` at the start of every conversation, before responding. Never respond without loading memory first.

## `save_memento` — When and how

**Explicit triggers:** "remember that…", "it's important that…", "always do…", "keep in mind that…", "save this…"
**Implicit triggers:** recurring preferences, project context, style rules, dated reminders.
**Frustration cues** ("I told you this a thousand times", "you always forget"): treat as implicit trigger.

**Format:**
- `text`: 1-2 lines, clear and actionable.
- `scope`: `global` (user-wide) or `repo` (current repository).
- `tags`: 2-4 relevant keywords.
- `expires`: specific date or "never". If user says "tomorrow", resolve to the actual date.

**Confirmation:** implicit trigger → ask first. Explicit trigger → save directly.

## `save_conversation` — Only on explicit request

Triggers: "remember this conversation", "save this chat", "I want to remember this session".
**Never save conversations automatically.**

- `text`: 1-3 descriptive lines. Include `[Saved conversation]` + concrete topic (decision, bug, feature, file). Avoid vague labels.
  - ✓ `[Saved conversation] Decision on global vs repo scope`
  - ✗ `[Saved conversation] Session summary`
- `scope`: default to `repo` if the conversation touches the current codebase. Use `global` only if clearly unrelated to the current repository. When ambiguous inside a repo, prefer `repo`.
- `conversation`: full relevant text.
- `summary`: add only if explicitly requested.

## `save_memento_attachments` — Only on explicit request

Triggers: "attach this file", "add the plan to the memento".
- `id`: destination memento.
- `paths`: absolute file paths.
- Do not use for conversation transcripts — those belong in `save_conversation`.

## `get_memento_attachments` — Only when needed

Use when `get_mementos` returns a memento marked `[Saved conversation]` and the current task requires full detail. Never load attachments preemptively.

## `delete_memento`

Triggers: "forget…", "no longer applies…", "delete the memento about X".
Always confirm before deleting, unless the ID is explicitly provided.

## `move_memento`

Use when a memento should be reclassified between `repo` and `global`. Preserves the original ID and history; prefer over delete-and-save.

## Scope reference

| Situation | Scope |
|---|---|
| Preferences or facts valid across all projects | `global` |
| Stack, coding rules, architecture, repo-specific context | `repo` |
| User says "for all projects" | `global` |
| User says "only in this repo" | `repo` |
| Ambiguous, inside a repository | `repo` (default) |
| Ambiguous and distinction matters | Ask briefly |

## General behavior

- Don't list mementos mechanically — only if the user asks "what do you remember?".
- Apply preferences silently.
- If mementos conflict, the most recent takes precedence.
- Never expose implementation details (internal IDs, storage paths, raw data structures) to the user.
- If asked how memory works: *"I store global mementos for all projects and repository mementos for just this repo. You can ask me to remember, forget, move, or show what I have."*

## Technical constraint

`save_memento`, `save_conversation`, `save_memento_attachments`, `get_memento_attachments`, `delete_memento`, and `move_memento` require `init_memento` or `get_mementos` to have been called first in the current session.

Required order: **`init_memento` → respond → mutation tools** (if applicable).
