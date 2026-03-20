# Skill Runtime

Read this before changing `echobot/skill_support/` or designing a skill that relies on resource files.

## Discovery order

`SkillRegistry.discover(...)` searches these roots in order:

1. `skills/`
2. `.<client>/skills/`
3. `.agents/skills/`
4. `echobot/skills/`
5. `~/.<client>/skills/`
6. `~/.agents/skills/`

Earlier roots win. Duplicate names are ignored after the first match and recorded as warnings.

## Parsing rules

- `SKILL.md` must start with YAML frontmatter delimited by `---`.
- Files are read as UTF-8 with optional BOM.
- EchoBot currently routes only on top-level `name` and `description`.
- `name` must be present and should stay a single-line kebab-case string.
- `description` must be present. It may be a single line or a YAML block scalar such as `>` or `|`.
- The parser normalizes multiline `description` values to plain text.
- Body text is stored as the activation payload.
- The explicit activation token parser accepts `/name` and `$name` with lowercase letters, digits, underscores, or hyphens, but project skills should still use kebab-case so validation and routing stay consistent.

## Activation model

- The agent sees a catalog prompt containing each skill `name` and `description`.
- If the user explicitly writes `/skill-name` or `$skill-name`, EchoBot injects that skill immediately unless it is already active.
- Otherwise the model can call `activate_skill`.
- Activation returns the skill name, description, directory, body text wrapped in `<active_skill ...>`, and a resource summary.

Bundled files are not loaded during activation.

## Resource tools

`SkillRegistry.create_tools(...)` adds three tools:

1. `activate_skill`
2. `list_skill_resources`
3. `read_skill_resource`

Runtime rules:

- `list_skill_resources` and `read_skill_resource` require the skill to be active first.
- Allowed resource folders are `scripts`, `references`, `assets`, and `agents`.
- `list_skill_resources` returns up to 50 paths by default unless a different `limit` is passed.
- `read_skill_resource` reads one file at a time, defaults to `max_chars=4000`, and only supports UTF-8 text files.
- Binary or non-text assets can exist in `assets/`, but the skill tools will not decode them into context.

## Authoring consequences

- Put essential instructions in `SKILL.md` or small UTF-8 files under `references/`.
- Split large documentation into topic-sized files so the agent can load only the needed one.
- Put deterministic helper code in `scripts/`.
- Put templates or binary output inputs in `assets/`.
- Do not hide critical instructions only inside binary assets or external docs.
- `agents/openai.yaml` is not required for EchoBot skill discovery. Only add agent files when some explicit workflow will read them.

## Tests to run when runtime behavior changes

- `python -m unittest tests.test_skill_support tests.test_chat_agent -v`
- Add broader tests if skill behavior affects coordinator, API, or command surfaces.
