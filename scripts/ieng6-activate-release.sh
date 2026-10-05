#!/usr/bin/env bash
# Activate one uploaded release while keeping data, uploads, and a rollback copy.
set -euo pipefail

release_id="$1"
app_root="$HOME/ai-interviewer"
release_dir="$app_root/releases/$release_id"
backup_dir="$release_dir/backup"
files=(main.py storage.py evaluator.py providers.py speech.py)

# Restore previous code and static files if validation or restart fails.
rollback() {
  trap - ERR
  echo "Deployment failed; restoring the previous release." >&2
  if [[ -d "$backup_dir/frontend-build" ]]; then
    if [[ -d "$app_root/frontend/build" ]]; then
      mv "$app_root/frontend/build" "$release_dir/failed-build"
    fi
    mv "$backup_dir/frontend-build" "$app_root/frontend/build"
  fi
  for file in "${files[@]}"; do
    if [[ -f "$backup_dir/backend/$file" ]]; then
      cp -p "$backup_dir/backend/$file" "$app_root/backend/$file"
    fi
  done
  if [[ -f "$app_root/app.pid" ]]; then
    pid="$(cat "$app_root/app.pid")"
    if kill -0 "$pid" 2>/dev/null; then kill "$pid"; fi
  fi
  sleep 1
  "$app_root/start-production.sh"
}
trap rollback ERR

# Validate the uploaded package before changing the running app.
mkdir -p "$release_dir/new" "$backup_dir/backend"
tar -xzf "$app_root/releases/$release_id.tar.gz" -C "$release_dir/new"
for file in "${files[@]}"; do
  test -f "$release_dir/new/backend/$file"
  cp -p "$app_root/backend/$file" "$backup_dir/backend/$file"
done
test -f "$release_dir/new/frontend/build/index.html"
PYTHONPYCACHEPREFIX="$release_dir/pycache" \
  "$app_root/.venv/bin/python" -m py_compile \
  "$release_dir/new/backend/main.py" \
  "$release_dir/new/backend/storage.py" \
  "$release_dir/new/backend/evaluator.py" \
  "$release_dir/new/backend/providers.py" \
  "$release_dir/new/backend/speech.py"

# Swap only application code; backend/data and backend/videos stay in place.
for file in "${files[@]}"; do
  cp -p "$release_dir/new/backend/$file" "$app_root/backend/$file"
done
mv "$app_root/frontend/build" "$backup_dir/frontend-build"
mv "$release_dir/new/frontend/build" "$app_root/frontend/build"

# Restart Uvicorn to load new Python modules; cloudflared stays running.
if [[ -f "$app_root/app.pid" ]]; then
  old_pid="$(cat "$app_root/app.pid")"
  if kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid"
    for attempt in {1..20}; do
      if ! kill -0 "$old_pid" 2>/dev/null; then break; fi
      sleep 0.5
    done
    if kill -0 "$old_pid" 2>/dev/null; then
      echo "Previous backend did not stop cleanly." >&2
      false
    fi
  fi
fi
"$app_root/start-production.sh"
test -f "$app_root/app.pid"
if [[ "$(cat "$app_root/app.pid")" == "${old_pid:-}" ]]; then
  echo "Backend did not start with a new process." >&2
  false
fi
for attempt in {1..20}; do
  if curl --fail --silent --show-error --max-time 2 \
      http://127.0.0.1:18000/health > /dev/null 2>&1; then
    trap - ERR
    echo "Activated $release_id; previous code is backed up at $backup_dir"
    exit 0
  fi
  sleep 0.5
done
false
