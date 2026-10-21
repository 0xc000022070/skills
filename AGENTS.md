# Repository Guide

A personal collection of agent skills, packaged for multiple runtimes. Skills are grouped by domain into Claude Code plugins under `plugins/`, all published by the single marketplace in `.claude-plugin/marketplace.json`.

## Layout

```
.claude-plugin/
  marketplace.json          # one entry per plugin
plugins/
  <plugin-name>/
    .claude-plugin/
      plugin.json           # name, description, version, keywords
    skills/
      <skill-name>/
        SKILL.md            # required: content + frontmatter
        agents/
          openai.yaml       # OpenAI runtime handler
        references/         # optional: docs loaded on demand
          <topic>.md
        scripts/            # optional: helpers the skill runs
```

Plugins:

- `agent-workflows` — git, agent supervision and orchestration, decision review.
- `mobile-apps` — Android and React Native app development and QA.
- `device-bringup` — Android firmware, Mobile NixOS ports, Jetson.
- `nixos-infra` — NixOS hosts on cloud infrastructure.
- `zen-browser` — Zen Browser internals and its flake.

Claude Code discovers every directory under a plugin's `skills/` automatically. No manifest lists individual skills.

## Adding a Skill

1. Pick the plugin whose domain fits. Create a new plugin only when none does (see [Adding a Plugin](#adding-a-plugin)).
2. Choose a kebab-case `<skill-name>` (`[a-z0-9-]`, no leading/trailing hyphen, no `--`). The directory name and the SKILL.md `name` must be identical and unique across all plugins.
3. Create `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` with the frontmatter below and imperative, scannable content.
4. Add `agents/openai.yaml` describing how the skill surfaces in the OpenAI runtime.
5. Put bulky or on-demand material under `references/<topic>.md` and link it from `SKILL.md` with a relative path.
6. If the skill adds new domain terms, append them to `keywords` in that plugin's `plugin.json`.
7. Run `claude plugin validate .` and `claude plugin validate plugins/<plugin-name>`.

## Adding a Plugin

1. Create `plugins/<plugin-name>/.claude-plugin/plugin.json` with `name`, `description`, `version`, `author`, `homepage`, `repository`, and `keywords`, copying the shape of an existing plugin.
2. Append `{ "name", "source": "./plugins/<plugin-name>", "description", "category" }` to `plugins` in `.claude-plugin/marketplace.json`. Keep the entry's `description` identical to the plugin's.
3. Update the marketplace's top-level `description` and the plugin list above.

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

The `$<skill-name>` token is OpenAI-runtime invocation syntax, not Claude Code's. Claude Code invokes the same skill as `/<plugin-name>:<skill-name>` and has no per-skill binding file; its handler is the SKILL.md plus its plugin's manifest.

## Claude Code Packaging

Install a plugin as `<plugin-name>@0xc000022070-skills`; its skills are invoked as `/<plugin-name>:<skill-name>`. Each plugin's `version` lives only in its own `plugin.json` and overrides the marketplace entry. Bump it only on release; descriptive edits are not a release.

## Keeping Metadata Current

- `plugins/<plugin-name>/.claude-plugin/plugin.json` → `keywords` and `description` — describe that plugin's domain only.
- `.claude-plugin/marketplace.json` — changes only when a plugin is added, removed, or its description changes.
- `<skill-name>/SKILL.md` → `metadata.category` and `description` — keep accurate to that skill.
