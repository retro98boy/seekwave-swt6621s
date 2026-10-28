#!/bin/bash
set -euo pipefail

repo_dir=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$repo_dir"

if [ "$#" -gt 1 ]; then
    printf 'Usage: %s [output-directory]\n' "$0" >&2
    exit 2
fi

if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
    printf 'Commit or stash changes before building a Git snapshot.\n' >&2
    exit 1
fi

source_commit=$(git rev-parse HEAD)
source_epoch=$(git show -s --format=%ct "$source_commit")
version=$(bash "$repo_dir/scripts/version.sh" "$source_commit")
changelog_date=$(LC_ALL=C date -u -R -d "@$source_epoch")
output_dir=$(realpath -m "${1:-$repo_dir/dist}")
build_dir=$(mktemp -d -t swt6621s-deb.XXXXXX)
trap 'rm -rf -- "$build_dir"' EXIT

mkdir "$build_dir/source"
git archive "$source_commit" | tar -xf - -C "$build_dir/source"

# Generate package metadata in the exported tree, leaving the checkout intact.
{
    printf 'swt6621s (%s) unstable; urgency=medium\n\n' "$version"
    printf '  * Build source snapshot %s.\n\n' "$source_commit"
    printf ' -- retro98boy <retro98boy@qq.com>  %s\n\n' "$changelog_date"
    cat "$build_dir/source/debian/changelog"
} > "$build_dir/changelog"
mv "$build_dir/changelog" "$build_dir/source/debian/changelog"

export SOURCE_DATE_EPOCH="$source_epoch"
(
    cd "$build_dir/source"
    dpkg-buildpackage -us -uc -b
)

mkdir -p "$output_dir"
cp "$build_dir"/*.deb "$build_dir"/*.buildinfo "$build_dir"/*.changes "$output_dir/"
(
    cd "$output_dir"
    sha256sum "swt6621s-dkms_${version}_all.deb" > SHA256SUMS
)
printf 'Built %s/swt6621s-dkms_%s_all.deb\n' "$output_dir" "$version"
