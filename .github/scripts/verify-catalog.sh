#!/usr/bin/env bash
# Fails unless FILE is an NXMC v1 model-catalog container signed by the production catalog key,
# the only form the app accepts. Container layout: ModelCatalogCipher.kt in nexus-chat-android.
# Usage: verify-catalog.sh [FILE]   (default: models.json)
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Public half of MODEL_CATALOG_SIGNING_PRIVATE_KEY; rotate it together with the
# MODEL_CATALOG_VERIFY_KEY secret in nexus-chat-android.
verify_key="$repo_root/.github/catalog-verify-key.pem"
file="${1:-models.json}"

fail() {
	echo "verify-catalog: $file: $*" >&2
	exit 1
}

[[ -f $file ]] || fail "no such file"

header_len=20
nonce_end=$header_len
min_tag=16
size=$(wc -c <"$file" | tr -d ' ')
((size >= header_len + min_tag + 2 + 8)) || fail "too short to be an NXMC container ($size bytes)"

read -r -a header <<<"$(head -c 6 "$file" | od -An -tu1)"
[[ "$(head -c 4 "$file")" == "NXMC" ]] || fail "not encrypted: missing NXMC magic (plaintext catalog?)"
((header[4] == 1)) || fail "unsupported format version ${header[4]}"
((header[5] == 1)) || fail "unknown key id ${header[5]}"

read -r -a trailer <<<"$(tail -c 2 "$file" | od -An -tu1)"
sig_len=$((trailer[0] * 256 + trailer[1]))
((sig_len >= 8 && sig_len <= 144)) || fail "implausible signature length $sig_len"
signed_end=$((size - 2 - sig_len))
((signed_end >= nonce_end + min_tag)) || fail "signature overlaps the header"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
head -c "$signed_end" "$file" >"$work/signed"
tail -c "+$((signed_end + 1))" "$file" | head -c "$sig_len" >"$work/sig"

openssl dgst -sha256 -verify "$verify_key" -signature "$work/sig" "$work/signed" >/dev/null 2>&1 ||
	fail "signature does not verify against the production catalog key"

echo "verify-catalog: $file: OK (NXMC v1, signed by production key)"
