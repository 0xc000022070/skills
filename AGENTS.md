# Repository Guide

A personal collection of agent skills, packaged for multiple runtimes. Each skill is a self-contained top-level directory. The repository root packages every skill for Claude Code through `.claude-plugin/`.

## Skill Layout

Create a new skill as a top-level directory whose name matches the skill `name` (kebab-case: `[a-z0-9-]`, no leading/trailing hyphen, no `--`).

```
<skill-name>/
  SKILL.md              # required: content + frontmatter
  agents/
    openai.yaml         # OpenAI runtime handler
  references/           # optional: docs loaded on demand
    <topic>.md
```

Root packaging (edit once per new skill):

```
.claude-plugin/
  plugin.json           # add "./<skill-name>" to the "skills" array
  marketplace.json      # no change; the single plugin bundles all skills
```

## Adding a Skill

1. Choose a kebab-case `<skill-name>`. The directory name and the SKILL.md `name` must be identical.
2. Write `SKILL.md` with the frontmatter below and imperative, scannable content.
3. Add `agents/openai.yaml` describing how the skill surfaces in the OpenAI runtime.
4. Put bulky or on-demand material under `references/<topic>.md` and link it from `SKILL.md` with a relative path.
5. Append `"./<skill-name>"` to the `skills` array in `.claude-plugin/plugin.json`.
6. Refresh discovery metadata in `.claude-plugin/marketplace.json` (see [Keeping Manifest Metadata Current](#keeping-manifest-metadata-current)).
7. Run `claude plugin validate .` from the repo root.

## SKILL.md Frontmatter

```yaml
---
name: <skill-name>
description: <what it does + when to use, one paragraph, <=1024 chars>
allowed-tools: Read Grep Glob Edit Write
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: <area>
---
```

- `name` — required, kebab-case, matches the directory.
- `description` — required, <=1024 chars. Lead with what the skill does, then the concrete triggers ("Use when ..."); this text drives auto-invocation.
- `allowed-tools` — optional, space-separated tools pre-approved without a prompt. Grant only what the skill needs. Omit `Bash` unless the skill must run shell unprompted; scope it (`Bash(npm:*)`) when you do.
- `disable-model-invocation` — `false` lets Claude auto-invoke on matching work; `true` for run-only-when-asked skills.
- `metadata` — string→string map. Keep `version` quoted.

## OpenAI Handler (`agents/openai.yaml`)

```yaml
interface:
  display_name: "<Title Case Name>"
  short_description: "<imperative one-liner>"
  default_prompt: "Use $<skill-name> to <primary action>."
```

The `$<skill-name>` token is OpenAI-runtime invocation syntax, not Claude Code's. Claude Code invokes the same skill as `/skills:<skill-name>` and has no per-skill binding file; its handler is the SKILL.md plus the root `.claude-plugin/` manifests.

## Claude Code Packaging

The repo is a marketplace (`.claude-plugin/marketplace.json`) exposing one plugin, `skills`, sourced at `./`. The plugin's `skills` array (`.claude-plugin/plugin.json`) lists each skill directory. Adding a skill means appending one path. Set `version` only in `plugin.json` — it overrides the marketplace entry.

## Keeping Manifest Metadata Current

One plugin bundles every skill, so its descriptive fields describe the whole collection, not a single skill. When you add or materially change a skill, refresh the fields it affects:

- `marketplace.json` → `plugins[0].keywords` — add terms for the new skill's domain so the plugin stays discoverable.
- `marketplace.json` → top-level `description`, `plugins[0].description`, and `category` — update only if the collection's scope actually shifted.
- `<skill-name>/SKILL.md` → `metadata.category` and `description` — keep accurate to that skill.

Leave `version` out of this. It is pinned in `plugin.json` and bumped only on release; editing descriptive metadata is not a release.
