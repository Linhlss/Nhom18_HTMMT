#!/usr/bin/env bash
# Run inside the Ubuntu VM: sudo bash scripts/setup-ubuntu.sh
set -Eeuo pipefail
export LC_ALL=C

if [[ $(uname -s) != Linux || ! -r /etc/os-release ]]; then
  echo 'ERROR: run this script inside the Ubuntu 24.04 VM.' >&2
  exit 2
fi
source /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then
  echo 'ERROR: Ubuntu 24.04 LTS is required.' >&2
  exit 2
fi
if [[ $EUID -ne 0 ]]; then
  echo 'ERROR: use sudo bash scripts/setup-ubuntu.sh' >&2
  exit 2
fi
case $(dpkg --print-architecture) in
  arm64|amd64) ;;
  *) echo 'ERROR: supported guest architectures are arm64 and amd64.' >&2; exit 2 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
if ! apt-cache show mininet >/dev/null 2>&1; then
  apt-get install -y software-properties-common
  add-apt-repository -y universe
  apt-get update
fi
echo 'iperf3 iperf3/start_daemon boolean false' | debconf-set-selections
apt-get install -y --no-install-recommends \
  mininet openvswitch-switch python3 python3-venv python3-pip \
  iproute2 iputils-ping iperf3 tcpdump net-tools ethtool \
  git curl ca-certificates openssh-server

systemctl enable --now openvswitch-switch.service ssh.service
systemctl is-active --quiet openvswitch-switch.service
ovs-vsctl --timeout=10 show
/usr/bin/python3 -c 'from mininet.net import Mininet; from mininet.node import OVSBridge; print("Mininet Python import: OK")'
case $(mn --version 2>&1) in
  2.3.*) ;;
  *) echo 'ERROR: expected Mininet 2.3.x; record and investigate package drift.' >&2; exit 1 ;;
esac
case $(ovs-vsctl --version | head -n 1) in
  *' 3.3.'*) ;;
  *) echo 'ERROR: expected Open vSwitch 3.3.x; investigate package drift.' >&2; exit 1 ;;
esac
case $(/usr/bin/python3 --version) in
  'Python 3.12.'*) ;;
  *) echo 'ERROR: expected system Python 3.12.x.' >&2; exit 1 ;;
esac
echo 'SETUP PASS. Next: sudo bash scripts/verify-week1.sh'
