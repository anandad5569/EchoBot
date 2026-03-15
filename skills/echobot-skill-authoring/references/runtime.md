# Runtime Notes

## Discovery order

The local runtime searches skill folders in this order:

1. `skills/`
2. `.<client>/skills/`
3. `.agents/skills/`
4. `echobot/skills/`
5. `~/.<client>/skills/`
6. `~/.agents/skills/`

Earlier folders win when duplicate skill names exist.

## Parsing

- `SKILL.md` must start with YAML frontmatter.
- The runtime reads only the top-level `name` and `description` fields for routing.
- `name` must stay a single-line text value.
- `description` can be a single-line value or a YAML block scalar such as `>` or `|`. The runtime normalizes it to plain text.
- Extra frontmatter fields are allowed, but routing currently depends only on `name` and `description`.

## Activation model

- The agent adds a catalog of available skills to the system context.
- Explicit user mentions activate matching skills immediately.
- Otherwise the model can call `activate_skill`.
- Activated skill content is returned together with the skill directory and bundled resource file list.
