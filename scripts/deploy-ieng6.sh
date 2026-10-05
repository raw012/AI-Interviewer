#!/usr/bin/env bash
# Build a committed release locally, then upload it to the existing ieng6 app.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_host="raw012@ieng6.ucsd.edu"
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

# Deployment is always made from exactly what was pushed to GitHub.
if [[ "$commit" != "$(git -C "$repo_root" rev-parse origin/main)" ]]; then
  echo "Push the current commit to origin/main before deploying." >&2
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

# Export committed backend files; local uncommitted data and secrets stay behind.
git -C "$repo_root" archive HEAD \
  backend/main.py backend/storage.py backend/evaluator.py \
  backend/providers.py backend/speech.py backend/test_providers.py \
  | tar -xf - -C "$staging_dir"

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
echo "Deployed $commit to https://interview.buildbyray.dev/"
