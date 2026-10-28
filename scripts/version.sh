#!/bin/bash
set -euo pipefail

if [ "$#" -gt 1 ]; then
    printf 'Usage: %s [commit-or-tag]\n' "$0" >&2
    exit 2
fi

repo_dir=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
source_commit=$(git -C "$repo_dir" rev-parse --verify "${1:-HEAD}^{commit}")
source_epoch=$(git -C "$repo_dir" show -s --format=%ct "$source_commit")
source_date=$(date -u -d "@$source_epoch" +%Y.%m.%d.%H%M%S)
printf '%s+git%s\n' "$source_date" "${source_commit:0:12}"
