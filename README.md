# find-relevant-skills

An agent skill that scans a repo's tech stack and finds matching skills on [skills.sh](https://skills.sh).

Point it at a repo and it will:

1. Detect what the repo is built with, using manifest files such as `package.json`, `pom.xml` and `requirements.txt`.
2. Search skills.sh for skills that match.
3. Show you a shortlist.
4. Install only the ones you approve into the repo's `.claude/skills/`.

Nothing is installed without your confirmation. Skills are instructions that get loaded into the agent's context, so you should review them first.

## Install

```bash
npx skills add shershen08/frs
```

## Usage

Ask your agent something like:

- "Find skills for this repo"
- "Add relevant skills from skills.sh"
- "What skills would help in this project?"

If you already know which skill you want, run `npx skills add <owner/repo>` directly instead.

## Slash command

Once installed, the skill is available as `/find-relevant-skills`. For the shorter `/frs`, add an alias command to your project (or to `~/.claude/commands/` to have it everywhere):

```bash
mkdir -p .claude/commands && cp /path/to/frs/.claude/commands/frs.md .claude/commands/
```

The skills CLI installs only skills, so this file has to be copied by hand.

## Layout

```
SKILL.md                 skill definition and workflow
.claude/commands/frs.md  optional /frs alias
scripts/detect_stack.py  stack detector, prints JSON search terms
```

You can run the detector on its own:

```bash
python3 scripts/detect_stack.py /path/to/repo
```

## Requirements

- Node.js, for `npx skills`
- Python 3, for the stack detector
- Network access to skills.sh

## Alternatives

- `npx skills find <query>` searches skills.sh straight from the CLI, for example `npx skills find react`. You pick the query yourself, and nothing scans your repo.
- Browse [skills.sh](https://skills.sh) by hand and install with `npx skills add <owner/repo>`.
- The `find-skills` skill from [vercel-labs/skills](https://github.com/vercel-labs/skills) helps your agent discover skills for a task you describe. It doesn't read your repo's manifests.
