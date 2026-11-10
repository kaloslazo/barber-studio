#!/usr/bin/env bash
set -euo pipefail

sha="${SSH_ORIGINAL_COMMAND:-}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "expected a 40-character commit sha" >&2
  exit 2
fi

cd /opt/fresh
exec 9>/tmp/fresh-deploy.lock
flock -w 900 9

branch="$(git rev-parse --abbrev-ref HEAD)"
git fetch --quiet origin "$branch"
if ! git merge-base --is-ancestor "$sha" "origin/$branch"; then
  echo "$sha is not on origin/$branch" >&2
  exit 3
fi
git merge --quiet --ff-only "origin/$branch"
echo "deploying $(git rev-parse --short HEAD) from $branch"

docker compose --profile prod up -d --build --remove-orphans

status=starting
for _ in $(seq 1 40); do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app)")"
  [[ "$status" == healthy ]] && break
  sleep 3
done
docker compose --profile prod ps
docker image prune -f >/dev/null

if [[ "$status" != healthy ]]; then
  echo "app is $status" >&2
  docker compose logs --tail 50 app >&2
  exit 1
fi
