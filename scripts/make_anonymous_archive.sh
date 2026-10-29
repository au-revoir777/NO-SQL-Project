#!/bin/sh
# Build an anonymised archive of the current commit for double-blind review:
# code, configs, protocols, results, models and the paper sources, with author names,
# e-mail addresses and the repository owner removed from text files, and no git history.
#
#   sh scripts/make_anonymous_archive.sh [output.zip]
set -eu
OUT="${1:-anonymous_submission.zip}"
TMP="$(mktemp -d)"
git archive --format=tar HEAD | tar -x -C "$TMP"
# paths that identify the authors or are not needed for review
rm -f "$TMP/docs/paper/paper.pdf"  # compiled with author names; reviewers rebuild it from the anonymised sources
rm -rf "$TMP/.github" "$TMP/docs/paper/refine2" "$TMP/docs/paper/refine3" "$TMP/docs/paper/refine4"
# identifying strings (add more with ANON_EXTRA="a|b")
PATTERN="au-revoir777|vitstudent\.ac\.in|Roshan Parveen|Sanjay Kumar S|Vellore Institute of Technology${ANON_EXTRA:+|$ANON_EXTRA}"
grep -rlIE "$PATTERN" "$TMP" | while read -r f; do
  sed -i -E "s/$PATTERN/ANONYMOUS/g" "$f"
done
if grep -rIE "$PATTERN" "$TMP" >/dev/null; then echo "identifying strings remain" >&2; exit 1; fi
(cd "$TMP" && zip -qr - .) > "$OUT"
rm -rf "$TMP"
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
