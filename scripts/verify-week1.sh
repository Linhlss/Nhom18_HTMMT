#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C
label=smoke
negative=()
while [[ $# -gt 0 ]]; do
  case $1 in
    --label) [[ $# -ge 2 ]] || exit 2; label=$2; shift 2 ;;
    --negative-control) negative=(--negative-control); shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ $label =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Invalid label' >&2; exit 2; }
if [[ $(uname -s) != Linux || $EUID -ne 0 ]]; then
  echo 'ERROR: run inside the Ubuntu VM with sudo bash scripts/verify-week1.sh' >&2
  exit 2
fi
source /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] || { echo 'Ubuntu 24.04 is required.' >&2; exit 2; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec 9>/run/lock/nhom18-week1.lock
flock -n 9 || { echo 'Another week-1 check is running.' >&2; exit 2; }
out="$root/evidence/week1/$(date -u +%Y%m%dT%H%M%S%NZ)-$label"
mkdir -p "$out"
finish() {
  code=$?
  trap - EXIT
  printf '%s\n' "$code" > "$out/exit-code.txt"
  if [[ -n ${SUDO_UID:-} && -n ${SUDO_GID:-} ]]; then
    chown -R "$SUDO_UID:$SUDO_GID" "$out"
  fi
  echo "Evidence: $out (exit $code)"
  exit "$code"
}
trap finish EXIT
exec > >(tee "$out/run.log") 2>&1
echo "Week 1 check: $label"
date -u --iso-8601=seconds
systemctl is-active --quiet openvswitch-switch.service
systemctl is-active ssh.service
ovs-vsctl --timeout=10 show
mn --version
ovs-vsctl --version
/usr/bin/python3 --version
/usr/bin/python3 -c 'from mininet.net import Mininet; print("Mininet system-Python import: OK")'
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' \
  mininet openvswitch-switch python3 iperf3 tcpdump iproute2 iputils-ping > "$out/packages.tsv"
cat "$out/packages.tsv"
/usr/bin/python3 - "$out/environment.json" <<'PY'
import datetime, json, os, platform, sys
from pathlib import Path
os_release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
data = {'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'os': {k: v.strip('"') for k, v in os_release.items()},
        'architecture': platform.machine(), 'kernel': platform.release(),
        'python': platform.python_version(), 'cpu_count': os.cpu_count(),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
Path(sys.argv[1]).write_text(json.dumps(data, indent=2) + '\n')
PY
timeout 90s /usr/bin/python3 "$root/scripts/smoke_mininet.py" --output "$out/result.json" "${negative[@]}"
echo 'PASS: two hosts, one OVS bridge, bidirectional zero-loss ping, and cleanup.'
