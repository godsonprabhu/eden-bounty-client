#!/usr/bin/env bash
# Encrypted backup of the investor_documents volume (security remediation, finding 7).
#
# The archive is streamed straight into `age` and written only in encrypted form: no plaintext
# copy of any investor document touches the disk. Decryption needs the matching private key,
# which must NOT be stored on this server (keep it in the company password manager / offline).
#
# Usage:
#   COMPOSE_PROJECT_NAME=edenbounty-staging \
#   AGE_RECIPIENTS_FILE=/etc/edenbounty/backup-recipients.txt \
#     deploy/backup-documents.sh [output-dir]          # default output-dir: ./backups
#
#   backup-recipients.txt holds one or more age public keys (lines starting "age1..."), e.g. the
#   output of `age-keygen -y key.txt` run on the administrator's own machine.
#
# Restore (on a trusted machine that has the private key):
#   age -d -i key.txt investor-documents-YYYY-MM-DD.tar.gz.age | \
#     docker run --rm -i -v <project>_investor_documents:/data alpine tar xzf - -C /data
set -euo pipefail

PROJECT="${COMPOSE_PROJECT_NAME:-edenbounty}"
VOLUME="${PROJECT}_investor_documents"
OUT_DIR="${1:-backups}"
RECIPIENTS="${AGE_RECIPIENTS_FILE:-}"

command -v age >/dev/null || { echo "age is not installed (apt install age)" >&2; exit 2; }
[ -n "$RECIPIENTS" ] && [ -s "$RECIPIENTS" ] || { echo "Set AGE_RECIPIENTS_FILE to a file of age public keys; refusing to write an unencrypted backup." >&2; exit 2; }
grep -q '^age1' "$RECIPIENTS" || { echo "$RECIPIENTS contains no age public key (age1...)." >&2; exit 2; }
docker volume inspect "$VOLUME" >/dev/null 2>&1 || { echo "Volume $VOLUME not found (set COMPOSE_PROJECT_NAME?)." >&2; exit 2; }

umask 077
mkdir -p "$OUT_DIR"
TARGET="$OUT_DIR/investor-documents-$(date +%F-%H%M%S).tar.gz.age"
[ ! -e "$TARGET" ] || { echo "Refusing to overwrite existing backup: $TARGET" >&2; exit 2; }
# Create a unique temporary file so a stale partial archive is never truncated or removed.
TMP="$(mktemp "$OUT_DIR/.investor-documents-$(date +%F-%H%M%S).XXXXXX.partial")"
trap 'rm -f "$TMP"' EXIT

docker run --rm -v "$VOLUME":/data:ro alpine:3.20 tar czf - -C /data . | age -R "$RECIPIENTS" > "$TMP"
[ -s "$TMP" ] || { echo "Backup is empty; aborting." >&2; exit 1; }
# Hard-link creation is atomic and fails if another backup already created TARGET.
ln "$TMP" "$TARGET" || { echo "Could not publish backup without overwriting: $TARGET" >&2; exit 1; }
rm "$TMP"
trap - EXIT
echo "Encrypted backup written: $TARGET"
sha256sum "$TARGET"
echo "Copy it off this server (with the database dump of the same time) and test a restore regularly."
