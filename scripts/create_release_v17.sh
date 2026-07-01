#!/usr/bin/env bash
# Создаёт GitHub Release v17.0.0 для Theclimateguy/GIM из ветки GIM18.
# Запуск из папки GIM18:
#   GH_TOKEN=твой_токен bash create_release_v17.sh
set -euo pipefail

REPO="Theclimateguy/GIM"
TAG="v17.0.0"
TARGET="GIM18"
NAME="GIM18 v17.0.0"

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "Укажи токен: GH_TOKEN=ghp_xxx bash create_release_v17.sh" >&2
  exit 1
fi

# Извлекаем раздел 17.0.0 из CHANGELOG как тело релиза
awk '/^## \[17.0.0\]/{f=1} /^## \[16/{f=0} f' CHANGELOG.md > /tmp/relnotes_v17.md

python3 - "$NAME" "$TAG" "$TARGET" "$REPO" <<'PY'
import json, os, sys, urllib.request, urllib.error
name, tag, target, repo = sys.argv[1:5]
body = open('/tmp/relnotes_v17.md').read()
payload = {"tag_name": tag, "target_commitish": target, "name": name,
           "body": body, "draft": False, "prerelease": False, "make_latest": "true"}
req = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/releases",
    data=json.dumps(payload).encode(),
    headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
             "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28",
             "User-Agent": "gim-release"})
try:
    r = urllib.request.urlopen(req)
    d = json.load(r)
    print("OK", r.status, "->", d.get("html_url"))
except urllib.error.HTTPError as e:
    print("ERROR", e.code, e.read().decode()); sys.exit(1)
PY
