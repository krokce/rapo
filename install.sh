#!/usr/bin/env bash
#
# install.sh - install rapo into its virtual environment, ready to start.
#
# Creates the venv (Python 3.10 or newer, chosen from the ones installed),
# installs the requirements and rapo itself (editable, so a git checkout of a
# new version is picked up), creates rapo.ini from rapo.ini.example when there
# is none, and checks that the Oracle Instant Client can be loaded.
# Run again on an existing venv, it updates the packages in place, which is
# also the upgrade step after checking out a new version.
#
# Usage:
#   ./install.sh [--python PYTHON] [--force] [--allow-root]
#
#   --python PYTHON  the Python to build the venv with, e.g. python3.12 or a
#                    path; without it, the installed ones are offered
#   --force          delete the venv and create it anew (refused while rapo
#                    runs from it)
#   --allow-root     install as root, for a rapo that runs as root
#
# Environment overrides: RAPO_HOME, RAPO_VENV, RAPO_CONFIG, RAPO_PYTHON.

set -uo pipefail

SCRIPT=$(readlink -f "$0")
RAPO_HOME=${RAPO_HOME:-$(dirname "$SCRIPT")}
RAPO_VENV=${RAPO_VENV:-$RAPO_HOME/.venv}
RAPO_CONFIG=${RAPO_CONFIG:-$RAPO_HOME/rapo.ini}

VPY=$RAPO_VENV/bin/python
MIN_MINOR=10    # Python 3.10 or newer
MAX_MINOR=14    # highest python3.N looked for on PATH

PYTHON=${RAPO_PYTHON:-}
FORCE=
ALLOW_ROOT=

step() {
    echo
    echo "==> $*"
}

warn() {
    echo "install.sh: WARNING: $*" >&2
}

die() {
    echo "install.sh: ERROR: $*" >&2
    exit 1
}

usage() {
    awk 'NR > 2 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "$SCRIPT"
    exit 2
}

# Version of a Python as major.minor.micro, empty when it does not run.
py_version() {
    "$1" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null
}

py_supported() {
    local major minor
    IFS=. read -r major minor _ <<<"$1"
    [[ $major -eq 3 && $minor -ge $MIN_MINOR ]]
}

# Processes running from the venv: the server, its runs and rapo-server
# itself all start with the venv's python.
venv_pids() {
    pgrep -f -- "^$RAPO_VENV/bin/python" 2>/dev/null | paste -sd ' '
}

# Offer the supported Pythons on PATH and set PYTHON to the chosen one.
choose_python() {
    local name path real version
    local -A seen=()
    local -a found=() old=()
    # Versioned names first, so python3.12 is listed rather than a python3
    # that links to it.
    for name in $(seq -f "python3.%g" "$MAX_MINOR" -1 "$MIN_MINOR") python3; do
        path=$(command -v "$name" 2>/dev/null) || continue
        real=$(readlink -f "$path")
        [[ -n ${seen[$real]:-} ]] && continue
        seen[$real]=1
        version=$(py_version "$path") || continue
        [[ -n $version ]] || continue
        if py_supported "$version"; then
            found+=("$version $name $path")
        else
            old+=("$name $version")
        fi
    done
    # Newest first; it is the default.
    mapfile -t found < <(printf '%s\n' "${found[@]}" | grep . | sort -r -V)
    if [[ ${#found[@]} -eq 0 ]]; then
        [[ ${#old[@]} -gt 0 ]] && echo "Found, but older than 3.$MIN_MINOR: ${old[*]}" >&2
        die "no Python 3.$MIN_MINOR or newer found on PATH; install one or name it with --python"
    fi
    if [[ ${#found[@]} -eq 1 ]]; then
        PYTHON=$(awk '{ print $3 }' <<<"${found[0]}")
        echo "Using $(awk '{ print $2 " " $1 " (" $3 ")" }' <<<"${found[0]}"), the only Python 3.$MIN_MINOR+ found."
        return
    fi
    if [[ ! -t 0 ]]; then
        die "several Pythons found ($(printf '%s\n' "${found[@]}" | awk '{ print $2 }' | paste -sd ' ')); choose one with --python"
    fi
    echo "Pythons found:"
    local i
    for i in "${!found[@]}"; do
        read -r version name path <<<"${found[$i]}"
        printf '  %d) %-11s %-8s %s\n' $((i + 1)) "$name" "$version" "$path"
    done
    [[ ${#old[@]} -gt 0 ]] && echo "  (too old: ${old[*]})"
    local answer
    while true; do
        read -rp "Python for the venv [1-${#found[@]}, Enter = 1]: " answer
        answer=${answer:-1}
        if [[ $answer =~ ^[0-9]+$ ]] && ((answer >= 1 && answer <= ${#found[@]})); then
            break
        fi
    done
    PYTHON=$(awk '{ print $3 }' <<<"${found[$((answer - 1))]}")
}

# Load the Oracle Client the way rapo does (thick mode: client_path, else the
# library path). Prints the client version, or the error.
client_check() {
    "$VPY" - "$RAPO_CONFIG" <<'PY'
import configparser
import sys

import oracledb

parser = configparser.ConfigParser(allow_no_value=True)
parser.read(sys.argv[1], encoding='utf-8')
client_path = (parser.get('DATABASE', 'client_path', fallback='') or '').strip()
try:
    oracledb.init_oracle_client(lib_dir=client_path or None)
except Exception as error:
    print(str(error).splitlines()[0])
    sys.exit(1)
version = '.'.join(map(str, oracledb.clientversion()))
print(f'{version} from {client_path}' if client_path else version)
sys.exit(3 if not client_path else 0)
PY
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --python) [[ $# -ge 2 ]] || die "--python needs a value"; PYTHON=$2; shift 2 ;;
        --force) FORCE=1; shift ;;
        --allow-root) ALLOW_ROOT=1; shift ;;
        -h|--help) usage ;;
        *) die "unknown argument: $1 (see --help)" ;;
    esac
done

if [[ $EUID -eq 0 && -z $ALLOW_ROOT ]]; then
    die "run install.sh as the user that runs rapo, not as root (or pass --allow-root)"
fi
[[ -f $RAPO_HOME/setup.py ]] || die "no setup.py in $RAPO_HOME (set RAPO_HOME)"

if [[ -n $PYTHON ]]; then
    resolved=$(command -v "$PYTHON" 2>/dev/null) || die "no Python named $PYTHON"
    PYTHON=$resolved
    version=$(py_version "$PYTHON")
    [[ -n $version ]] || die "$PYTHON does not run"
    py_supported "$version" || die "$PYTHON is Python $version; rapo needs 3.$MIN_MINOR or newer"
fi

# The venv: update in place, recreate (--force) or create.
if [[ -e $RAPO_VENV && -z $FORCE ]]; then
    [[ -x $VPY ]] || die "$RAPO_VENV exists but has no bin/python; recreate it with --force"
    venv_version=$(py_version "$VPY")
    [[ -n $venv_version ]] || die "the python of $RAPO_VENV does not run; recreate it with --force"
    py_supported "$venv_version" ||
        die "$RAPO_VENV is Python $venv_version; recreate it with --force and a Python 3.$MIN_MINOR+"
    if [[ -n $PYTHON && ${version%.*} != "${venv_version%.*}" ]]; then
        die "$RAPO_VENV is Python $venv_version, not ${version%.*}; recreate it with --force"
    fi
    MODE=updated
    step "Updating $RAPO_VENV (Python $venv_version)"
else
    if [[ -e $RAPO_VENV ]]; then
        pids=$(venv_pids)
        [[ -z $pids ]] || die "rapo is running from $RAPO_VENV (PID $pids); stop it first: $RAPO_HOME/rapoctl.sh stop"
        [[ -f $RAPO_VENV/pyvenv.cfg ]] || die "$RAPO_VENV is not a virtual environment (no pyvenv.cfg); not deleting it"
    fi
    [[ -n $PYTHON ]] || choose_python
    version=$(py_version "$PYTHON")
    if [[ -e $RAPO_VENV ]]; then
        step "Deleting $RAPO_VENV"
        rm -rf -- "$RAPO_VENV" || die "cannot delete $RAPO_VENV"
        MODE=recreated
    else
        MODE=created
    fi
    step "Creating $RAPO_VENV with $PYTHON (Python $version)"
    if ! "$PYTHON" -m venv "$RAPO_VENV"; then
        rm -rf -- "$RAPO_VENV"
        die "cannot create the venv; the venv module may be missing (e.g. dnf install python${version%.*}, apt install python${version%.*}-venv)"
    fi
fi

# setup.py reads requirements.txt from the current folder.
cd "$RAPO_HOME" || die "cannot enter $RAPO_HOME"

step "Upgrading pip"
"$VPY" -m pip install --upgrade pip || die "upgrading pip failed"

step "Installing the requirements"
"$VPY" -m pip install -r requirements.txt || die "installing the requirements failed"

step "Installing rapo (editable)"
# setup.py imports rapo, which connects to the database when it finds a
# rapo.ini; a configuration that does not exist keeps the install offline.
RAPO_CONFIG=$RAPO_VENV/no-rapo.ini "$VPY" -m pip install --no-build-isolation -e . ||
    die "installing rapo failed"

# rapo.ini
if [[ -f $RAPO_CONFIG ]]; then
    if cmp -s "$RAPO_CONFIG" "$RAPO_HOME/rapo.ini.example"; then
        CONFIG_STATE="$RAPO_CONFIG (still the example: fill in [DATABASE] and [API] token)"
    else
        CONFIG_STATE="$RAPO_CONFIG (kept)"
    fi
else
    step "Creating $RAPO_CONFIG from rapo.ini.example"
    (umask 077 && cp "$RAPO_HOME/rapo.ini.example" "$RAPO_CONFIG") || die "cannot create $RAPO_CONFIG"
    chmod 600 "$RAPO_CONFIG"
    CONFIG_STATE="$RAPO_CONFIG (new: fill in [DATABASE] and [API] token)"
fi

step "Checking the Oracle Instant Client"
client=$(client_check)
status=$?
if [[ $status -eq 1 ]]; then
    warn "the Oracle Instant Client cannot be loaded: $client"
    warn "install it and set [DATABASE] client_path in $RAPO_CONFIG to its folder"
    CLIENT_STATE="not found"
elif [[ $status -eq 3 && -n ${LD_LIBRARY_PATH:-} ]] &&
     ! LD_LIBRARY_PATH= client_check >/dev/null; then
    warn "the Oracle Instant Client $client is found only through LD_LIBRARY_PATH,"
    warn "which a start from cron (@reboot) does not have; set [DATABASE] client_path in $RAPO_CONFIG"
    CLIENT_STATE="$client (LD_LIBRARY_PATH only)"
elif [[ $status -eq 0 || $status -eq 3 ]]; then
    CLIENT_STATE=$client
else
    warn "the Oracle Instant Client check failed: $client"
    CLIENT_STATE="check failed"
fi
echo "$CLIENT_STATE"

rapo_version=$("$VPY" -c 'import importlib.metadata as m; print(m.version("rapo"))' 2>/dev/null)
pids=$(venv_pids)

step "Done"
echo "venv:           $RAPO_VENV ($MODE, Python $(py_version "$VPY"))"
echo "rapo:           ${rapo_version:-unknown}"
echo "config:         $CONFIG_STATE"
echo "Oracle Client:  $CLIENT_STATE"
echo
if [[ -n $pids ]]; then
    echo "rapo is running (PID $pids): restart it to use the updated packages: $RAPO_HOME/rapoctl.sh restart"
elif [[ $MODE == updated ]]; then
    echo "Start rapo:  $RAPO_HOME/rapoctl.sh start"
else
    echo "Next: deploy schema/oracle.sql into a new database, fill in $RAPO_CONFIG,"
    echo "      then start rapo: $RAPO_HOME/rapoctl.sh start"
fi
