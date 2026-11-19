#!/usr/bin/env bash
# SPDX-License-Identifier: MIT OR Apache-2.0
# Runs a corpus inside the image: no network, CPU and memory capped, the data read-only and only the
# results directory writable. A kernel's code can neither reach out nor starve the host.
#
#     corpus/docker/run-in-docker.sh DATA_DIR MANIFEST.tsv RESULTS_DIR [run.py options, e.g. --jobs 3]
#
# CPUS (default 3) and MEMORY (default 16g) set the caps.
set -euo pipefail
data=$(cd "$1" && pwd); manifest=$(cd "$(dirname "$2")" && pwd)/$(basename "$2"); results=$3; shift 3
mkdir -p "$results"; results=$(cd "$results" && pwd)
for k in occt cadrs; do
  docker run --rm --network none --cpus "${CPUS:-3}" --memory "${MEMORY:-16g}" --pids-limit 1024 \
    --read-only --tmpfs /tmp:size=2g --security-opt no-new-privileges --cap-drop ALL \
    -v "$data":/data:ro -v "$manifest":/manifest.tsv:ro -v "$results":/results \
    ${IMAGE:-ckb-corpus} python corpus/run.py --kernel $k --manifest /manifest.tsv --data /data \
    --out /results/$k.jsonl.gz "$@"
done
docker run --rm --network none --read-only -v "$results":/results:ro ${IMAGE:-ckb-corpus} \
  python corpus/summarize.py /results
