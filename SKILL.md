---
name: find-relevant-skills
description: Scans the current repo's tech stack (languages, frameworks, infra) and finds matching skills on skills.sh (the open agent-skills directory, npx skills CLI), then installs the ones you approve into .claude/skills/. Use this whenever the user asks to "find skills for this repo," "add relevant skills from skills.sh," "set up skills for this project," wants to extend Claude's capabilities to match their stack, or opens a new/unfamiliar repo and asks what skills would help here. Don't use it when the user already names a specific skill or package to install — just run npx skills add for that directly instead of the full scan.
---

# find-relevant-skills

Point this at a repo and it will: figure out what the repo is built with, search
skills.sh for skills that match, show you a shortlist, and install whichever
ones you pick into that repo's `.claude/skills/`.

It exists because "relevant" skills depend on the actual codebase, not a
generic guess — a repo's manifest files (`package.json`, `pom.xml`,
`requirements.txt`, …) are a much better signal than asking the user to name
their stack from memory.

## Why confirm before installing

Skills are instructions (and sometimes scripts) that get loaded into context
and followed. Installing one sight-unseen is not like installing a library —
treat the shortlist step as mandatory, not a formality, even when a match
looks obviously right. The user chose to review before install, so don't
auto-run `skills add` without showing the candidate first and getting a yes.

## Workflow

### 1. Confirm the CLI and see what it actually supports

```
npx skills --help
```

The command surface shown below (`find`, `add`, `update`) reflects the CLI as
documented on skills.sh at the time this skill was written, but CLIs change —
run `--help` (and `--help` on the specific subcommand you're about to use) and
adapt to what's actually there rather than assuming these flags are current.
Flags don't carry over between subcommands — `find` has historically
supported a smaller flag set than `add` (no `--json`, for example) — so check
`--help` for the exact subcommand you're about to call rather than reusing a
flag that worked elsewhere. An unrecognized flag may not even error; it can
get silently absorbed into the free-text query instead, which looks like a
real (empty) search result rather than a mistake.

**Detecting a blocked network vs. a real empty result.** A proxy-restricted
or offline environment often won't give `npx skills find` a clean error — it
can just report "No skills found" for every query, indistinguishable from a
genuinely obscure search term. Don't take one empty result at face value:
sanity-check with a broad, obviously-common term first (`react`, `typescript`,
`docker`). If that also comes back empty, treat it as a network failure, not
a real signal that nothing exists, and move to **Fallback: no CLI network
access** below instead of concluding the repo's stack has no matching
skills.

### 2. Detect the repo's stack

Run the bundled detector against the repo root (defaults to `.` if no path is
given):

```
python3 scripts/detect_stack.py /path/to/repo
```

It walks the repo (skipping `node_modules`, `.git`, build output, etc.),
reads known manifest/config files (`package.json`, `pom.xml`, `go.mod`,
`requirements.txt`/`pyproject.toml`, `Cargo.toml`, `Gemfile`,
`composer.json`, `*.csproj`, `Dockerfile`, `docker-compose.yml`, Terraform,
k8s manifests, GitHub Actions workflows, …) and returns JSON signals like:

```json
{"term": "spring boot", "kind": "framework", "source": "pom.xml"}
```

This is a *signal detector*, not a full dependency audit — it's tuned to
produce good search terms, not an exhaustive bill of materials. If the repo
uses something the script doesn't recognize (a niche framework, an internal
tool), that's fine: skim the manifest files yourself for anything the script
missed and add those terms too. If the repo has no manifest files at all (a
docs repo, a monorepo with an unusual layout), ask the user what the project
is rather than guessing.

### 3. Turn signals into search queries

Don't search once per raw signal — that's noisy (every repo has "docker", not
every search needs it) and wastes calls. Instead:

- **Prioritize `framework` and `language` signals** — "spring boot", "react",
  "django" — these are the ones a skill is actually likely to be written
  about.
- **Combine related signals into one query when it reads naturally** — "java
  spring boot" beats separate "java" and "spring boot" searches, and matches
  how skills.sh's multi-word semantic search works best.
- **Treat `tool`/`infra` signals (docker, postgres, terraform, github
  actions) as secondary** — search for them too, but weight results lower
  than framework/language matches in the shortlist, and skip the truly
  generic ones (plain "docker" on a repo where it's just the deploy target,
  not the point of the project) unless the user's request is specifically
  about that tool.
- **Check what's already installed first.** List `.claude/skills/` in the
  repo (and `~/.claude/skills/` if relevant) before searching, and drop any
  query whose obvious match is already present — don't re-suggest something
  the repo already has.

### 4. Search skills.sh

For each query:

```
npx skills find "<query>"
```

If that subcommand isn't what `--help` showed, use whatever the CLI's actual
search/list command is. If the CLI has no non-interactive search output at
all, fall back to the web (see below).

Collect candidates across all queries before moving on — don't present
results query-by-query, the user wants one shortlist.

### 5. Filter and rank before showing anyone anything

This is the judgment step — don't just forward raw search results. For each
candidate, weigh:

- **Install count** — treat 1K+ installs as a reasonable trust signal, and
  treat anything under ~100 installs with real skepticism (new and
  unproven, not necessarily bad).
- **Source reputation** — a skill from the org that makes the actual
  technology (`vercel-labs` for Next.js tooling, `prisma` for Prisma,
  `anthropics` for Claude-specific skills) or another well-known org
  outweighs an installs tie-break against an unknown personal account.
- **`isDuplicate`** — if the search result flags a skill as a duplicate/fork
  of another, drop it in favor of the original.
- **Security audit, if you can reach it** — skills.sh publishes audit
  results (Socket, Snyk, Gen Agent Trust Hub, etc.) at
  `https://skills.sh/<owner>/<repo>/<skill>/security`. Check this for
  anything you're about to put in front of the user as a serious candidate,
  and if an audit shows a `warn`/`fail` verdict or `HIGH`/`CRITICAL` risk,
  say so plainly in the shortlist rather than silently dropping or silently
  including it — that's the user's call, not yours. No audit on file yet
  (common for newer or less-installed skills) just means "unaudited," not
  "unsafe" — note it as unaudited and let install count/source reputation
  carry more weight for that one.

Narrow each query's results to 1-3 real candidates. If nothing clears a
reasonable bar for a given signal, leave that signal off the shortlist
instead of padding it with a weak match.

### 6. Show the shortlist and wait for a decision

Group by the stack signal it matches, not by raw query. For each candidate
give: name, source (`owner/repo`), install count, one-line description, the
skills.sh link, and the audit flag if one exists. Then ask which ones to
install — if a question tool is available, use it (multi-select, since
several can be chosen at once); otherwise ask in plain text and wait for the
reply. Do not install anything before this point, including skills that
looked like slam-dunks.

### 7. Install what's approved

For each approved skill, install it project-scoped so it lands in this
repo's `.claude/skills/` and shows up in version control for review:

```
npx skills add <owner/repo> --skill <slug> --agent claude-code
```

(Again, confirm the actual flag names via `--help` if they differ from this.)
After installing, verify the files actually landed (`ls .claude/skills/`)
rather than trusting the command's exit code alone, and if the repo is a git
repo, mention that the new skill shows up in `git status` so the user can
review and commit it like any other change.

Report back concisely: what got installed, where, and a one-line next step
(e.g., "commit `.claude/skills/<name>/` to share it with the rest of the
team").

## Fallback: no CLI network access

If `npx skills ...` can't reach the registry (sandboxed environment, proxy
blocking the npm/skills.sh hosts), don't keep retrying the same call. Skip the
API URL (`https://www.skills.sh/api/v1/skills/search?q=<query>`) entirely —
it needs a Vercel OIDC bearer token you won't have, and in a sandboxed
fetch tool it can get refused outright (e.g. by robots.txt) before any auth
error even comes back, so it's not worth a turn to find out. Instead, in
this order:

1. **`https://www.skills.sh/trending`** — renders server-side, lists
   individual skills with owner and install counts. The most reliable of
   these pages.
2. **A specific owner's page**, if a stack signal points at one you already
   suspect makes relevant skills (`https://www.skills.sh/<owner>/<repo>`) —
   works well when you have a specific guess.
3. **`https://www.skills.sh/official`** — despite the name, this lists
   *owners/creators* (e.g. `anthropics`, `microsoft`) with their skill
   counts, not individual skills with install counts — use it to find an org
   worth then checking via #2, not as a direct skill shortlist.
4. **`https://www.skills.sh/topic/<topic>`** — only if you already know a
   valid topic slug (there's no documented list to check one against in a
   sandboxed session); don't burn a turn guessing one.
5. **A plain web search** for `site:skills.sh <stack term>` when the above
   don't surface anything stack-specific — trending/official only cover the
   most-installed skills overall, so a specific, lower-install but still
   credible match (a few hundred installs, from a plausible source) often
   only turns up this way. This is frequently the step that actually finds
   something relevant.

Tell the user plainly that you're working from scraped web pages rather than
live search or the CLI, so they know install counts and security-audit
status weren't freshly verified and the install command wasn't tested live.
Give them the `npx skills add <owner/repo> --skill <slug> --agent claude-code`
command to run themselves once they're in an environment with normal network
access, rather than running it yourself against unverified data.

## Example

> User: "This is a new repo for me, can you see what skills from skills.sh
> would help here?"

1. `npx skills --help` to confirm the CLI surface.
2. `python3 scripts/detect_stack.py .` → finds `spring boot`, `java`,
   `postgres`, `docker`, `junit` from `pom.xml` / `docker-compose.yml`.
3. Check `.claude/skills/` — empty, nothing to exclude.
4. Search `"java spring boot"`, `"postgres"`, `"junit"` (skip bare `"docker"`
   as too generic here).
5. Rank results; say spring-boot and testing skills clear the bar, drop a
   5-install personal-fork Postgres skill in favor of none.
6. Present: "Found 2 good matches: `spring-boot-best-practices`
   (official-ish, 40K installs) and `junit5-patterns` (12K installs, from a
   well-known Java tooling org). Want me to install either?"
7. On "yes, both" → `npx skills add ... --agent claude-code` for each,
   confirm the files landed in `.claude/skills/`, mention they're now in
   `git status`.
