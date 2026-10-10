#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 WORK_DIRECTORY" >&2
  exit 2
fi

bundle_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$1"
mkdir -p "$work_dir"
work_dir="$(cd "$work_dir" && pwd)"

for command_name in git tar python3 hf; do
  command -v "$command_name" >/dev/null || {
    echo "missing required command: $command_name" >&2
    exit 1
  }
done

clone_commit() {
  local url="$1"
  local commit="$2"
  local destination="$3"
  if [[ ! -d "$destination/.git" ]]; then
    git init -q "$destination"
    git -C "$destination" remote add origin "$url"
  fi
  git -C "$destination" fetch --depth 1 origin "$commit"
  git -C "$destination" checkout --detach --force "$commit"
  test "$(git -C "$destination" rev-parse HEAD)" = "$commit"
}

if [[ ! -d "$work_dir/atmem-b97d35e" ]]; then
  tar -xzf "$bundle_dir/source/atmem-b97d35e-source.tar.gz" -C "$work_dir"
fi
if [[ ! -d "$work_dir/atmem-fdc63de" ]]; then
  tar -xzf "$bundle_dir/source/atmem-fdc63de-source.tar.gz" -C "$work_dir"
fi

clone_commit \
  https://github.com/xiaowu0162/LongMemEval-V2.git \
  2cc8c540bdb87fe6761629b585e727e1c4704520 \
  "$work_dir/LongMemEval-V2"
clone_commit \
  https://github.com/mem0ai/dolphinbench.git \
  81cb6f8405b40a9e76089cef650806a80af06ea2 \
  "$work_dir/DolphinBench"
clone_commit \
  https://github.com/mem0ai/mem0.git \
  d3891e48baa2c6e769f9cfa4003873bd6a85bc07 \
  "$work_dir/mem0"
clone_commit \
  https://github.com/tech4biz-yasha/agmi.git \
  115493a41a7b41952f92ec07e1ea0932926e194f \
  "$work_dir/agmi"

hf download xiaowu0162/longmemeval-v2 \
  --repo-type dataset \
  --revision f152293e235517d504809563c833d7190b8c713b \
  --local-dir "$work_dir/longmemeval-v2-data"

python3 "$bundle_dir/scripts/verify_bundle.py" \
  --bundle "$bundle_dir" \
  --longmem-data "$work_dir/longmemeval-v2-data" \
  --dolphin-checkout "$work_dir/DolphinBench"

if [[ ! -d "$work_dir/venv" ]]; then
  python3 -m venv "$work_dir/venv"
fi
"$work_dir/venv/bin/python" -m pip install --upgrade pip
"$work_dir/venv/bin/python" -m pip install -r "$bundle_dir/environment/requirements-pinned.txt"
"$work_dir/venv/bin/python" -m pip install -e "$work_dir/atmem-b97d35e[dev,mem0,encrypted]"

cat <<EOF
Reproduction workspace prepared at:
  $work_dir

No paid benchmark call was started.
Read:
  $bundle_dir/REPRODUCING.md
EOF
