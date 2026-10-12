# claude-skills

Skills for [Claude Code](https://claude.com/claude-code) that I use for research software and
lab reporting. Each skill is a folder under `skills/` with a `SKILL.md` that Claude reads when the task
matches, plus whatever scripts it needs.

| Skill | What it does |
|---|---|
| [`html-report`](skills/html-report/SKILL.md) | Status, findings, update and brief reports for a PI, reviewer or collaborator. Each report is a YAML spec rendered to one self-contained, light-only HTML file that you can attach to an email, open offline or print. |

## Install

```bash
git clone https://github.com/ammalabbasi/claude-skills.git
cd claude-skills
pip install -r requirements.txt     # PyYAML
./install.sh                        # all skills, every project   (~/.claude/skills)
./install.sh --project ~/my-repo    # or just one project          (~/my-repo/.claude/skills)
```

`install.sh` symlinks, so a later `git pull` updates the installed skills. Pass `--copy` to pin a
snapshot instead. It never overwrites a skill you already have.

## html-report

### Using it with Claude Code

You don't run anything yourself. Ask in plain words, and Claude picks the type, writes the spec, renders
it and runs the checks:

> Make a status report for my PI from the review comments in `review_2026-10-01.md`. These are fixed so far: …

> Write up the benchmark in `results/summary.tsv` as a findings report, and link it from row E1 of last week's status report.

> One-page brief for the committee on where the project stands.

Claude hands back the path to the HTML file. Read it, then attach it yourself.

### The four types

| Type | For | Example |
|---|---|---|
| `status` | **"Did you do what I asked?"** Sent after a round of fixes. One table per document the reviewer sent, in their numbering; Fixed / In progress / Open / Won't do; ● marks what changed since last time. | [real report, cleaned](examples/2026-10-05_status.html) |
| `findings` | **"What did this one experiment show?"** The question, the answer, what I tested, what I found, then limits and next steps. | [real report, cleaned](examples/2026-09-30_aligner_findings.html) |
| `update` | A narrative across topics, ending in "What I need from you". With a `tabs` block it becomes the **multi-area email update**: one tab per area, each self-contained, with its asks at the foot. | [v1.1 update](examples/2026-09-16_update.html) · [tabbed weekly update](examples/2026-09-19_lab_update.html) |
| `brief` | One screen for people outside the project | [committee brief](examples/2026-09-17_brief.html) |

The examples use an invented "Example project"; every number in them is made up. GitHub shows
HTML as source code, so to see them rendered, either clone the repo and open `examples/index.html`, or
turn on GitHub Pages for the repo (Settings → Pages → deploy from `main`, root folder) and go to
`https://ammalabbasi.github.io/claude-skills/examples/`.

### By hand

```bash
S=skills/html-report/scripts
python3 $S/report.py init --type findings -o 2026-10-12_benchmark_findings.yaml
$EDITOR 2026-10-12_benchmark_findings.yaml          # fill every REPLACE
python3 $S/report.py build 2026-10-12_benchmark_findings.yaml
python3 $S/check_report.py 2026-10-12_benchmark_findings.html
```

The YAML is short. Here is a whole status item:

```yaml
- {id: R3, asked: "Paired reads lose their mate.", done: "Fixed; confirmed by the pilot rerun.", status: fixed, commit: e5f6a7b}
```

The full spec reference is in [`SKILL.md`](skills/html-report/SKILL.md).

### What `check_report.py` checks

It **fails** on any of these:
- dark-mode CSS, or external scripts, fonts or images
- leftover `REPLACE` placeholders
- a tile count that doesn't match the table
- a missing privacy footer
- DNA sequences, or anything else listed in `patterns/identifiers.txt`

It **warns** on tables not wrapped for scrolling, broken local links, oversized files, and briefs
that run past one screen. It never prints the text that matched, only the pattern name and a count.

### Make it yours: the local add-on

The skill is generic. Anything specific to your work goes in your project and stays out of this repo:

- `.claude/html-report.local.md`: who you report to, which of your past reports to copy, voice,
  data-handling rules. Claude reads it first. Start from
  [`local.example.md`](skills/html-report/local.example.md).
- An identifier patterns file for IDs that must never leave your site (cohort sample IDs, accession
  formats). Point to it with `export HTML_REPORT_PATTERNS=/path/to/patterns.txt` or `--patterns`.

`*.local.md` is git-ignored here, so a local add-on can't be committed to this repo by accident.

## Tests

```bash
pip install pyyaml pytest && pytest -q tests
```

CI runs the tests and also checks that the committed example HTML matches its YAML.

## License

MIT
