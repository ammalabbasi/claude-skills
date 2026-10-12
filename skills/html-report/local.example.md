# html-report — local add-on (example)

Copy to `<your project>/.claude/html-report.local.md` and edit. Claude reads it before the generic
SKILL.md, and it wins where they disagree. Do not commit it to a public repo.

## Who reads these reports
- Main reader: <name / role>. Address them as "you"; their item IDs are <format, e.g. F01, L1–L10>.
- Others: <committee, collaborators> → usually the `brief` type.

## Reports to copy (read before writing)
- status: `<path to your best past status report>`
- findings: `<path>`
- update: `<path>`

## Where files go
- `<dir>/YYYY-MM-DD_status.yaml` + `.html`, next to the email draft if there is one.

## Data rules
- <e.g. "All cohort data is controlled-access: aggregate counts only; never sample IDs.">
- Identifier patterns: `export HTML_REPORT_PATTERNS=<path to your patterns.txt>`
  (format: `FAIL<TAB>name<TAB>regex`, one per line).

## Voice
- <e.g. "Plain declarative sentences; name the mechanism; lead with what is still open.">
