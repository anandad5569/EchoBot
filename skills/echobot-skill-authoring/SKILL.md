---
name: echobot-skill-authoring
description: Use when creating, revising, or validating a skill in this EchoBot repository, including SKILL.md frontmatter, trigger descriptions, skill folders under skills/, bundled references or scripts or assets or agents, or changes to EchoBot skill discovery and activation behavior.
---

# EchoBot Skill Authoring

Create or revise repository-local skills that EchoBot can discover and activate.

## Authoring rules

- Put project-specific skills under `skills/<skill-name>/`.
- Use lowercase kebab-case for the folder name and the `name` frontmatter field.
- Keep frontmatter minimal. EchoBot routing reads `name` and `description` from `SKILL.md`.
- Keep `name` as a single-line value. `description` may be a single line or a YAML block scalar.
- Write `description` as the trigger surface: what the skill does, when to use it, and what kinds of user requests or contexts should activate it.
- Keep the main body procedural and concise. Move deeper material into small files under `references/` or `scripts/`.
- Design for lazy loading. After activation, EchoBot exposes the body plus a resource summary. It does not auto-load bundled files.
- Only put text resources that an agent may need to read into `references/`, `scripts/`, or `agents/`. `read_skill_resource` only reads UTF-8 text files.
- Use `assets/` for templates or binary output artifacts, not for essential instructions.
- Do not treat `agents/openai.yaml` as required. Current EchoBot discovery ignores it.
- Avoid extra docs like `README.md` or changelog files inside a skill unless the runtime truly needs them.

## Resource layout

```text
skills/<skill-name>/
|-- SKILL.md
|-- references/   # short, focused UTF-8 docs loaded on demand
|-- scripts/      # executable helpers or deterministic workflows
|-- assets/       # templates or binary resources not meant for context loading
`-- agents/       # optional helper prompts or agent-specific text resources
```

You do not need every folder. Create only what the skill actually uses.

## Practical workflow

1. Draft or refine the trigger description in `SKILL.md`.
2. Keep the main body short and procedural.
3. Split long or variant-specific details into focused resource files.
4. If the skill changes runtime expectations, update tests.
5. Validate the skill with `python -X utf8 echobot/skills/skill-creator/scripts/quick_validate.py skills/<skill-name>`.

## EchoBot-specific notes

- Project skills override built-in skills with the same `name`.
- Explicit `/skill-name` or `$skill-name` activates the skill immediately.
- Otherwise the model may call `activate_skill`.
- After activation, the agent must call `list_skill_resources` and `read_skill_resource` to inspect bundled files.
- If you change discovery, parsing, or activation behavior in `echobot/skill_support/`, run `python -m unittest tests.test_skill_support tests.test_chat_agent -v`.

Read `references/runtime.md` before changing the skill runtime or designing a skill with many bundled files.
