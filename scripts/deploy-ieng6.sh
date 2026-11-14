#!/usr/bin/env bash
# Build a committed release locally, then upload it to the existing ieng6 app.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# ieng6.ucsd.edu is an alias for several machines that share one home directory.
# The app must run on exactly one of them, so deploy to that machine by name.
deploy_host="${DEPLOY_HOST:-raw012@ieng6-203.ucsd.edu}"
commit="$(git -C "$repo_root" rev-parse HEAD)"
release_id="$(date -u +%Y%m%d%H%M%S)-${commit:0:12}"
staging_dir="$(mktemp -d /private/tmp/ai-interviewer-release.XXXXXX)"

# Remove only the temporary directory created above, never an arbitrary path.
cleanup() {
  case "$staging_dir" in
    /private/tmp/ai-interviewer-release.*) rm -rf -- "$staging_dir" ;;
  esac
}
trap cleanup EXIT

# Deployment is always made from exactly what was pushed to GitHub. main is the
# default; set DEPLOY_BRANCH=<branch> to preview a pushed feature branch.
deploy_branch="${DEPLOY_BRANCH:-main}"
git -C "$repo_root" fetch --quiet origin "$deploy_branch"
if [[ "$commit" != "$(git -C "$repo_root" rev-parse "origin/$deploy_branch")" ]]; then
  echo "Push the current commit to origin/$deploy_branch before deploying." >&2
  exit 1
fi
if ! git -C "$repo_root" -c core.filemode=false diff --quiet HEAD -- \
    frontend/src frontend/public frontend/package.json frontend/package-lock.json; then
  echo "Commit frontend changes before deploying." >&2
  exit 1
fi
if [[ -n "$(git -C "$repo_root" ls-files --others --exclude-standard -- frontend/src frontend/public)" ]]; then
  echo "Untracked frontend source files must be reviewed before deploying." >&2
  exit 1
fi

# Export every committed backend module; local data, uploads and secrets stay behind.
backend_files=()
while IFS= read -r path; do backend_files+=("$path"); done \
  < <(git -C "$repo_root" ls-files 'backend/*.py')
git -C "$repo_root" archive HEAD "${backend_files[@]}" | tar -xf - -C "$staging_dir"

# CRA serves API and UI from the same origin in production.
(cd "$repo_root/frontend" && CI=true BUILD_PATH="$staging_dir/frontend/build" npm run build)
COPYFILE_DISABLE=1 tar -czf "$staging_dir/release.tar.gz" -C "$staging_dir" backend frontend

ssh -o BatchMode=yes "$deploy_host" 'mkdir -p "$HOME/ai-interviewer/releases"'
scp -o BatchMode=yes "$staging_dir/release.tar.gz" \
  "$deploy_host:ai-interviewer/releases/$release_id.tar.gz"
ssh -o BatchMode=yes "$deploy_host" bash -s -- "$release_id" \
  < "$repo_root/scripts/ieng6-activate-release.sh"

# Check the public tunnel as well as the server-local health check.
curl --fail --silent --show-error --max-time 20 \
  https://interview.buildbyray.dev/health > /dev/null
echo "Deployed $commit ($deploy_branch) to https://interview.buildbyray.dev/"
