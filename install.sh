#!/usr/bin/env bash
# Install skills from this repo into Claude Code.
#   ./install.sh                      all skills -> ~/.claude/skills (every project)
#   ./install.sh --project DIR        all skills -> DIR/.claude/skills (one project)
#   ./install.sh html-report          just the named skill(s)
#   ./install.sh --copy ...           copy instead of symlink (symlinks follow `git pull`)
# Never overwrites: an existing skill of the same name is skipped.
set -euo pipefail
REPO=$(cd "$(dirname "$0")" && pwd)
DEST="$HOME/.claude/skills"; MODE=link; SKILLS=()
while [[ $# -gt 0 ]]; do
  case $1 in
    --project) DEST="$2/.claude/skills"; shift 2 ;;
    --copy) MODE=copy; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) SKILLS+=("$1"); shift ;;
  esac
done
if [[ ${#SKILLS[@]} -eq 0 ]]; then for d in "$REPO"/skills/*/; do SKILLS+=("$(basename "$d")"); done; fi
mkdir -p "$DEST"
for s in "${SKILLS[@]}"; do
  src="$REPO/skills/$s"; dst="$DEST/$s"
  [[ -f "$src/SKILL.md" ]] || { echo "no such skill: $s" >&2; exit 1; }
  if [[ -e "$dst" || -L "$dst" ]]; then echo "skip $s: $dst already exists"; continue; fi
  if [[ $MODE == copy ]]; then cp -r "$src" "$dst"; else ln -s "$src" "$dst"; fi
  echo "installed $s -> $dst ($MODE)"
done
python3 -c "import yaml" 2>/dev/null || echo "note: html-report needs PyYAML (pip install pyyaml)"
