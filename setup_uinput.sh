#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./setup_uinput.sh" >&2
  exit 1
fi

modprobe uinput || true
getent group input >/dev/null || groupadd input

cat >/etc/udev/rules.d/99-palmglide-uinput.rules <<'RULE'
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
RULE

usermod -aG input "${SUDO_USER:-$USER}"
udevadm control --reload-rules
udevadm trigger

# Some systems expose uinput in sysfs but do not materialize the static node.
if [[ ! -e /dev/uinput ]]; then
  mknod /dev/uinput c 10 223
fi
chgrp input /dev/uinput
chmod 0660 /dev/uinput

echo "PalmGlide uinput access installed. Log out and back in before running palmglide.py."
