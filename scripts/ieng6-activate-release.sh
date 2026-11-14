#!/usr/bin/env bash
# Activate one uploaded release while keeping data, uploads, and a rollback copy.
set -euo pipefail

release_id="$1"
app_root="$HOME/ai-interviewer"
release_dir="$app_root/releases/$release_id"
backup_dir="$release_dir/backup"
files=()  # filled from the uploaded release: every backend module it contains

# Identify the process that actually owns the API port; app.pid can be stale.
backend_listener_pid() {
  local listener pid command
  listener="$(ss -ltnp '( sport = :18000 )' | sed -n '2p')"
  if [[ -z "$listener" ]]; then return 0; fi
  pid="$(sed -nE 's/.*pid=([0-9]+).*/\1/p' <<< "$listener")"
  if [[ -z "$pid" || ! -r "/proc/$pid/cmdline" ]]; then
    echo "Port 18000 is occupied by an unidentified process; refusing to stop it." >&2
    return 1
  fi
  command="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
  if [[ "$command" != "$app_root/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 18000 " ]]; then
    echo "Port 18000 is not owned by this application's backend; refusing to stop it." >&2
    return 1
  fi
  printf '%s' "$pid"
}

# Launch outside the SSH session; ieng6 terminates SSH-owned background jobs.
start_backend_detached() {
  printf '%s\n' "$app_root/start-production.sh" | at now
}

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
    else
      rm -f "$app_root/backend/$file"  # module introduced by the failed release
    fi
  done
  pid="$(backend_listener_pid)"
  if [[ -n "$pid" ]]; then kill "$pid"; fi
  rm -f "$app_root/app.pid"
  sleep 1
  start_backend_detached
}
trap rollback ERR

# Validate the uploaded package before changing the running app.
mkdir -p "$release_dir/new" "$backup_dir/backend"
tar -xzf "$app_root/releases/$release_id.tar.gz" -C "$release_dir/new"
for path in "$release_dir"/new/backend/*.py; do
  files+=("$(basename "$path")")
done
test -f "$release_dir/new/backend/main.py"
for file in "${files[@]}"; do
  if [[ -f "$app_root/backend/$file" ]]; then
    cp -p "$app_root/backend/$file" "$backup_dir/backend/$file"
  fi
done
test -f "$release_dir/new/frontend/build/index.html"
PYTHONPYCACHEPREFIX="$release_dir/pycache" \
  "$app_root/.venv/bin/python" -m py_compile "$release_dir"/new/backend/*.py

# Keep a copy of the database before new code migrates it. Schema changes are
# additive, so a rollback keeps the live database and this copy is a safety net.
if [[ -f "$app_root/backend/data/interviewer.db" ]]; then
  cp -p "$app_root/backend/data/interviewer.db" "$backup_dir/interviewer.db"
fi

# Swap only application code; backend/data and backend/videos stay in place.
for file in "${files[@]}"; do
  cp -p "$release_dir/new/backend/$file" "$app_root/backend/$file"
done
mv "$app_root/frontend/build" "$backup_dir/frontend-build"
mv "$release_dir/new/frontend/build" "$app_root/frontend/build"

# Restart the actual listener, not an unreliable pid-file entry; keep cloudflared.
old_pid="$(backend_listener_pid)"
if [[ -n "$old_pid" ]]; then
  kill "$old_pid"
  for attempt in {1..20}; do
    if [[ "$(backend_listener_pid)" != "$old_pid" ]]; then break; fi
    sleep 0.5
  done
  if [[ "$(backend_listener_pid)" == "$old_pid" ]]; then
    echo "Previous backend did not release port 18000." >&2
    false
  fi
fi
rm -f "$app_root/app.pid"
start_backend_detached
for attempt in {1..90}; do
  new_pid=""
  if [[ -f "$app_root/app.pid" ]]; then
    new_pid="$(cat "$app_root/app.pid")"
  fi
  if [[ -n "$new_pid" && "$(backend_listener_pid)" == "$new_pid" ]] && \
    curl --fail --silent --show-error --max-time 2 \
      http://127.0.0.1:18000/health > /dev/null 2>&1; then
    trap - ERR
    echo "Activated $release_id; previous code is backed up at $backup_dir"
    exit 0
  fi
  sleep 1
done
echo "The queued backend did not become healthy on port 18000." >&2
false
