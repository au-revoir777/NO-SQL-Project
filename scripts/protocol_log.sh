#!/bin/sh
# Regenerates docs/research/PROTOCOL_LOG.md table rows from git history.
for f in docs/research/*protocol*.md; do
  a=$(git log --diff-filter=A --format="%h (%ad)" --date=short -- "$f" | tail -1)
  l=$(git log -1 --format="%h (%ad)" --date=short -- "$f")
  echo "| \`$(basename "$f")\` | $a | $l |"
done
