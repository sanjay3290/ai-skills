#!/usr/bin/env bash
# Managed venv for pywhats. Run standalone (do not source — ends with exit):
#   PY=$(bash skills/whatsapp/scripts/_bootstrap.sh)
# Final stdout line is the absolute path to the venv's python interpreter.
# Idempotent: skips venv/pip work when pywhats is already importable.
set -euo pipefail

PYWHATS_HOME="${PYWHATS_HOME:-$HOME/.pywhats}"
VENV_DIR="${PYWHATS_HOME}/venv"
PYTHON=""

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

# pywhats needs Python >= 3.11. The platform default `python3` is often older
# (macOS ships 3.9), so pick a suitable interpreter to build the venv from.
_is_py311() {
  "$1" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null
}

find_base_py() {
  cand=""
  for cand in python3.13 python3.12 python3.11 python3.14 python3 python; do
    command -v "${cand}" >/dev/null 2>&1 || continue
    if _is_py311 "${cand}"; then
      command -v "${cand}"
      return 0
    fi
  done
  return 1
}

# Prefer an existing venv interpreter.
if [ -x "${VENV_DIR}/bin/python" ]; then
  PYTHON="${VENV_DIR}/bin/python"
elif [ -x "${VENV_DIR}/bin/python3" ]; then
  PYTHON="${VENV_DIR}/bin/python3"
fi

# A pre-existing venv on the wrong Python is unusable for pywhats — say so clearly
# rather than failing later with a cryptic pip "no matching version" error.
if [ -n "${PYTHON}" ] && ! _is_py311 "${PYTHON}"; then
  die "error: venv at ${VENV_DIR} uses $("${PYTHON}" -V 2>&1), but pywhats needs Python >= 3.11. Remove that directory and re-run."
fi

if [ -z "${PYTHON}" ]; then
  BASE_PY="$(find_base_py)" || die "error: need Python >= 3.11 for pywhats, but none found on PATH (looked for python3.13/3.12/3.11/python3). Install Python 3.11+ and retry."
  mkdir -p "${PYWHATS_HOME}"
  "${BASE_PY}" -m venv "${VENV_DIR}" || die "error: failed to create venv at ${VENV_DIR}"
  if [ -x "${VENV_DIR}/bin/python" ]; then
    PYTHON="${VENV_DIR}/bin/python"
  else
    PYTHON="${VENV_DIR}/bin/python3"
  fi
  [ -x "${PYTHON}" ] || die "error: venv python missing after create: ${VENV_DIR}"
fi

# Ensure pywhats >= 0.1.1 (oldest version with the logout events the CLI
# relies on) and qrcode are importable; install/upgrade only when the probe fails.
PROBE='import sys, pywhats, qrcode; v=tuple(int(x) for x in pywhats.__version__.split(".")[:3]); sys.exit(0 if v >= (0, 1, 1) else 1)'
if ! "${PYTHON}" -c "${PROBE}" >/dev/null 2>&1; then
  "${PYTHON}" -m pip install --upgrade pip >/dev/null 2>&1 \
    || die "error: pip upgrade failed in ${VENV_DIR}"
  # Progress → stderr so stdout stays pure (final line must be the interpreter path).
  "${PYTHON}" -m pip install --upgrade "pywhats>=0.1.1,<0.2" "qrcode[pil]>=7.4" >&2 \
    || die "error: failed to install pywhats into ${VENV_DIR}"
  "${PYTHON}" -c "${PROBE}" >/dev/null 2>&1 \
    || die "error: pywhats>=0.1.1/qrcode still not importable after install"
fi

# Absolute path WITHOUT resolving the binary symlink. Venv `bin/python` is
# often a symlink to the system interpreter; following it would re-exec outside
# the venv and lose site-packages (and loop with wa.py's bootstrap).
case "${PYTHON}" in
  /*) ;;
  *)
    _dir="$(cd "$(dirname "${PYTHON}")" && pwd)"
    PYTHON="${_dir}/$(basename "${PYTHON}")"
    ;;
esac

printf '%s\n' "${PYTHON}"
# Always exit when executed as a script. (Do not `source` this file.)
exit 0
