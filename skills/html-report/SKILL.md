---
name: html-report
description: Build single-file, light-only HTML reports for a PI, reviewer or collaborator from a YAML spec — four types - status ("did you do what I asked?" — one table per document the reviewer sent, in their numbering), findings (one experiment or validation written up end to end), update (narrative across topics, ending in asks), brief (one screen for people outside the project). Use when asked for a status/fix report, an email attachment summarising progress, a write-up of a validation, a project update, or a one-page brief.
---

# html-report

Reports are written as a **YAML spec** and rendered by `scripts/report.py` into one self-contained HTML
file (CSS inline, figures embedded, no JavaScript, light theme only). They are meant to be attached to
an email, opened offline and printed.

**First:** if the project has `.claude/html-report.local.md`, read it before anything else. It holds
the local add-on: who the reports go to, exemplar reports, voice notes, data rules, and extra
identifier patterns (`$HTML_REPORT_PATTERNS`). Local rules override this file where they conflict.

## Pick the type

| Type | Answers | Use when |
|---|---|---|
| `status` | "Did you do what I asked?" | After a round of fixes, back to the person who gave you the list. One table per document they sent, in their numbering. |
| `findings` | "What did this one experiment show?" | When a single result needs more than a line in a status table; link it from that row. |
| `update` | "What changed, and what do you need from me?" | Several topics, a reader who has not read the tables, or a decision needed. |
| `brief` | "Where are we, in one screen?" | Readers outside the project: a committee, a funder, a PI's collaborator. ≤4 tiles, ~450 words. |

Do not mix them: an analysis bolted onto a status report is a `findings` report waiting to be split out.

## Workflow

```bash
S=<this skill dir>/scripts
python3 $S/report.py init --type status -o 2026-10-12_status.yaml   # skeleton with REPLACE markers
#   fill it in
python3 $S/report.py build 2026-10-12_status.yaml                   # -> 2026-10-12_status.html
python3 $S/check_report.py 2026-10-12_status.html                   # must exit 0 before handing over
```

Hand over the **path**. Never send, upload or publish the report yourself; the user attaches it.
Name files date-first: `YYYY-MM-DD_status.yaml`, `YYYY-MM-DD_<topic>_findings.yaml`, `…_update`, `…_brief`.
Keep the YAML next to the HTML: the next round's status uses it as `previous:`.

## Rules

1. **Numbers come from somewhere real.** Every count, rate or result comes from a command run in this
   session or a summary the user handed over. If you do not have it, leave `REPLACE` (the checker fails on
   it) and say what is missing. Status tiles are computed from the items, so never type a count.
2. **No patient data, no sample identifiers, no file contents.** Pooled aggregates, code, commits and
   test results only. Refer to "the pilot sample", "3 of 40". The footer says so by default
   (`privacy: false` only for reports with no human data at all).
3. **Their numbering, their words.** Status rows keep the reader's IDs and order. Paraphrase the ask
   tightly; do not re-grade their priorities.
4. **Light only, self-contained.** Do not add dark-mode CSS or external fonts/scripts/images.
   `check_report.py` enforces this. Tabs are fine: they are CSS-only, and print or a no-CSS viewer shows every panel.
5. **Be as specific about what is open, reversed or broken as about what is fixed.** Use `open`,
   `notfound` (reported done, not found in the code) and `discrepancies` honestly.

## Spec reference

Common keys: `type`, `title` (2–6 words, the browser tab), `heading` (the `<h1>`), `project`, `date`,
`meta` (one line: what it answers, branch + commit, supersedes what), `tiles` (`{n, label, kind}`),
`summary` (`{headline, body, kind}`: the sentence they need if they read nothing else), `blocks`,
`methods` (`{summary, code}`, rendered folded), `footer`, `privacy`, `demo`.

Text fields take `**bold**`, `*italic*`, `` `code` ``, `[text](url)`; everything else is escaped.

**status** — kept deliberately small: `context` (one line: which review, which commit), `bottom_line`,
`previous` (last round's file → ● on rows that changed), and `sources`, one per document they sent:
`{name, items: [{id, asked, done, status, commit}]}`. Statuses: `fixed`, `progress`, `open`, `wontdo`.
Count boxes are computed from the items. Nothing else; if a result needs more than a line, write a
`findings` report and link it from `done`.

**findings** — five parts, always in this order: `question` (the page heading), `answer` (one or two
sentences with direction and size), `tested` (`[{test, data, n}]`; say which data are simulated, public or
real-pooled), `found` (`[{heading, text, table | bars | figure}]`, one per test), `limits` and `next`.
Optional `reproduce` (commands, folded at the bottom; strip it before sharing outside the lab).

**update:** `summary` as a plain string becomes the "In one paragraph" box; `h2` blocks are lettered
A., B., …; `open`, `asks` (`{ask, detail}`). **brief:** `changed`, `next`, `asks`.

**Tabs — the multi-area email update.** When one update covers unrelated areas (a project, costs,
infrastructure, hiring), make the body a single `tabs` block: one tab per area, each self-contained,
with its own `heading`, one-line `summary`, `blocks` and `asks` at its foot. Labels are numbered
("1 · Cloud costs"); put "each tab is self-contained; decisions are at the foot of each" in `meta`.
Tabs also nest, e.g. `Approach / Results / Conclusion` per experiment inside a findings report
(`numbered: false`). Not for briefs. Example: `examples/2026-09-19_lab_update.yaml`.

**Blocks:** `h2` (+`sub`), `h3`, `p`, `note` (+`headline`, `kind`), `list` (+`ordered`), `tiles`,
`table` (`{columns, rows, num, caption}`), `tabs` (list of `{label, heading, summary, blocks, asks}`,
optional `numbered`), `bars` (`{data: [{label, value, kind}], unit, caption}` →
inline SVG), `figure` (`{png, alt, caption}`, embedded), `details` (`{summary, code | items}`), `html` (raw).
Kinds: `ok info chg bad park dec nf`.

Worked examples of every type are in the repo's `examples/` directory.
