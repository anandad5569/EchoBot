---
name: echobot-skill-authoring
description: Create, revise, and validate skills for this EchoBot project. Use when the task involves SKILL.md files, skill folders, skill trigger descriptions, adding reusable instructions to this repository, or improving how the agent handles a recurring type of request.
---

# EchoBot Skill Authoring

Follow the same conventions as the upstream skill-creator skill, adapted for this project.

## Authoring rules

- Put project-specific skills under `skills/<skill-name>/`.
- Use lowercase kebab-case for the folder name and the `name` frontmatter field.
- `name` and `description` are the only required frontmatter fields — keep frontmatter minimal.
- Write `description` to cover both what the skill does and all the phrases or contexts that should trigger it. This is the primary routing signal; information in the body is only loaded after activation.
- Keep the body procedural and concise. Move large reference material to `references/` files and link to them from SKILL.md.
- Validate every new or changed skill:

```
python echobot/skills/skill-creator/scripts/quick_validate.py skills/<skill-name>
```

## Skill structure

```
skills/<skill-name>/
├── SKILL.md          (required)
└── references/       (optional — load only when needed)
```

Scripts and assets are also valid; see the upstream skill-creator skill for guidance on when to add them.

## Runtime behavior

Skills are discovered from these folders (earlier wins on duplicate names):

1. `skills/`
2. `.<client>/skills/`
3. `.agents/skills/`
4. `echobot/skills/`
5. User-level mirrors of the above under `~/`

Activation paths:
- Explicit user mention: `/skill-name` or `$skill-name`
- Model-initiated: `activate_skill` tool call
- On activation, the runtime returns the full SKILL.md body and a list of bundled resource files.

Read `references/runtime.md` before modifying the skill runtime or adding many new skills at once.
