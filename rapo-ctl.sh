#!/usr/bin/env bash
#
# rapo-ctl.sh - start, stop, restart and inspect the rapo web server.
#
# The server is uvicorn running rapo.web.api.app:app (API + UI + scheduler),
# started through the venv's rapo-server console script, which also keeps the
# rapo_web_api record. This wrapper adds what an unattended start needs: an
# absolute environment, waiting for the database to come up, waiting for the
# port to answer, and a log of what it did.
#
# Usage:
#   ./rapo-ctl.sh start [dev] [--wait SECONDS]
#   ./rapo-ctl.sh stop [--timeout SECONDS]
#   ./rapo-ctl.sh restart [--wait SECONDS] [--timeout SECONDS]
#   ./rapo-ctl.sh status
#
# Crontab (start on reboot, giving the database up to 10 minutes to appear):
#   @reboot /home/kosta/applications/rapo_dev/rapo-ctl.sh start --wait 600
#
# Environment overrides: RAPO_HOME, RAPO_VENV, RAPO_CONFIG, RAPO_CTL_LOG.

set -uo pipefail

SCRIPT=$(readlink -f "$0")
RAPO_HOME=${RAPO_HOME:-$(dirname "$SCRIPT")}
RAPO_VENV=${RAPO_VENV:-$RAPO_HOME/.venv}
export RAPO_CONFIG=${RAPO_CONFIG:-$RAPO_HOME/rapo.ini}

PYTHON=$RAPO_VENV/bin/python
SERVER=$RAPO_VENV/bin/rapo-server
APP='rapo.web.api.app:app'

WAIT=0          # how long to keep retrying a start (database not up yet)
TIMEOUT=30      # how long to wait for the process to go away on stop
READY=60        # how long to wait for the port to answer after a start

log() {
    local line
    line="$(date '+%Y-%m-%d %H:%M:%S') rapo-ctl: $*"
    echo "$line"
    if [[ -n ${LOG_FILE:-} ]]; then
        echo "$line" >>"$LOG_FILE" 2>/dev/null
    fi
}

die() {
    log "ERROR: $*"
    exit 1
}

usage() {
    awk 'NR > 2 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "$SCRIPT"
    exit 2
}

# Read one option of the ini file without importing rapo (which would connect
# to the database), falling back to the value the application defaults to.
ini_get() {
    "$PYTHON" - "$RAPO_CONFIG" "$1" "$2" "$3" <<'PY' 2>/dev/null
import configparser
import sys

path, section, option, default = sys.argv[1:5]
parser = configparser.ConfigParser(allow_no_value=True)
parser.read(path, encoding='utf-8')
value = parser.get(section, option, fallback='') or ''
print(value.strip() or default)
PY
}

# PIDs of this instance's uvicorn servers on this host. The venv and the
# address come from the command line rapo-server builds, so a second rapo
# instance on the same host is not mistaken for this one.
server_pids() {
    # sys.executable is whatever python the venv links, hence the suffix.
    pgrep -f -- "^$RAPO_VENV/bin/python[0-9.]* -m uvicorn $APP --host $HOST --port $PORT" 2>/dev/null
}

# The running PIDs on one line, for a message.
server_pids_line() {
    echo $(server_pids)
}

# The most telling line of a failed start, for a one-line message.
brief() {
    echo "$1" | grep -m1 -E '^[A-Za-z_.]+(Error|Exception):' || echo "$1" | tail -n 1
}

port_open() {
    (exec 3<>"/dev/tcp/$PROBE_HOST/$PORT") 2>/dev/null && exec 3<&- 3>&-
}

do_start() {
    local dev=$1 deadline attempt=0
    if [[ -n $(server_pids) ]]; then
        log "already running at PID $(server_pids_line)"
        return 0
    fi
    deadline=$(( $(date +%s) + WAIT ))
    while true; do
        attempt=$((attempt + 1))
        local output status
        if [[ $dev == dev ]]; then
            # Foreground, reloading, scheduler off: hands the terminal over.
            exec "$SERVER" start dev
        fi
        output=$("$SERVER" start 2>&1)
        status=$?
        if [[ $status -eq 0 ]]; then
            [[ -n $output ]] && log "$output"
            break
        fi
        # Anything before uvicorn is spawned fails here, most often because
        # the database is not listening yet after a reboot.
        if [[ $(date +%s) -ge $deadline ]]; then
            log "${output:-start failed}"
            die "could not start after $attempt attempt(s)"
        fi
        if [[ $attempt -eq 1 ]]; then
            log "start failed, retrying for up to ${WAIT}s: $(brief "$output")"
        fi
        sleep 10
    done
    wait_ready
}

# uvicorn is spawned detached, so a start that returns says nothing about the
# server itself. Wait for the port to answer, and report a process that died.
wait_ready() {
    local deadline=$(( $(date +%s) + READY ))
    while [[ $(date +%s) -lt $deadline ]]; do
        if port_open; then
            log "started at PID $(server_pids_line), listening on $HOST:$PORT"
            return 0
        fi
        if [[ -z $(server_pids) ]]; then
            die "server exited right after start, see $LOG_DIR"
        fi
        sleep 1
    done
    die "server did not start listening on $HOST:$PORT within ${READY}s"
}

do_stop() {
    local pids deadline
    pids=$(server_pids)
    # Runs SIGTERM on the recorded PID and clears the rapo_web_api record,
    # which matters even when nothing is running any more.
    local output
    output=$("$SERVER" stop 2>&1)
    [[ -n $output ]] && log "$output"
    if [[ -z $pids ]]; then
        log "not running"
        return 0
    fi
    log "stopping PID $(echo $pids)"
    deadline=$(( $(date +%s) + TIMEOUT ))
    while [[ -n $(server_pids) ]]; do
        if [[ $(date +%s) -ge $deadline ]]; then
            log "still alive after ${TIMEOUT}s, sending SIGKILL"
            # shellcheck disable=SC2046
            kill -9 $(server_pids) 2>/dev/null
            sleep 2
            break
        fi
        sleep 1
    done
    [[ -n $(server_pids) ]] && die "could not stop $(server_pids_line)"
    log "stopped"
}

do_status() {
    local pids
    pids=$(server_pids)
    echo "home:     $RAPO_HOME"
    echo "config:   $RAPO_CONFIG"
    echo "instance: $(ini_get SCHEDULER instance_name '(unnamed)')"
    echo "url:      http://$HOST:$PORT"
    if [[ -n $pids ]]; then
        echo "process:  running at PID $(echo $pids)"
    else
        echo "process:  not running"
    fi
    if port_open; then
        echo "port:     answering on $PROBE_HOST:$PORT"
    else
        echo "port:     no answer on $PROBE_HOST:$PORT"
    fi
    "$PYTHON" - <<'PY' 2>&1 | sed 's/^/record:   /'
try:
    from rapo.reader import reader
    from rapo.web import is_running
except Exception as error:
    print(f'database unavailable ({error.__class__.__name__})')
else:
    record = reader.read_web_api_record()
    if not record:
        print('no rapo_web_api row')
    else:
        state = 'running' if is_running(record) else 'stale'
        print(f'{state}, status={record["status"]} pid={record["pid"]} '
              f'server={record["server"]} url={record["url"]} '
              f'started={record["start_date"]} stopped={record["stop_date"]}')
PY
    [[ -n $pids ]]
}

[[ -x $PYTHON ]] || die "no python at $PYTHON (set RAPO_VENV)"
[[ -x $SERVER ]] || die "no rapo-server at $SERVER (pip install -e . in the venv)"
[[ -f $RAPO_CONFIG ]] || die "no configuration file at $RAPO_CONFIG"

ACTION=${1:-}
[[ -n $ACTION ]] || usage
shift
DEV=
while [[ $# -gt 0 ]]; do
    case $1 in
        dev) DEV=dev; shift ;;
        --wait) WAIT=${2:-0}; shift 2 ;;
        --timeout) TIMEOUT=${2:-30}; shift 2 ;;
        --ready) READY=${2:-60}; shift 2 ;;
        -h|--help) usage ;;
        *) die "unknown argument: $1" ;;
    esac
done

HOST=$(ini_get API host 127.0.0.1)
PORT=$(ini_get API port 8080)
# 0.0.0.0 is not an address to connect to.
PROBE_HOST=$HOST
[[ $PROBE_HOST == 0.0.0.0 || $PROBE_HOST == '::' ]] && PROBE_HOST=127.0.0.1

LOG_DIR=$(ini_get LOGGING directory "$RAPO_HOME/logs")
[[ $LOG_DIR != /* ]] && LOG_DIR=$RAPO_HOME/$LOG_DIR
LOG_FILE=${RAPO_CTL_LOG:-$LOG_DIR/rapo-ctl.log}
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null

case $ACTION in
    start) do_start "$DEV" ;;
    stop) do_stop ;;
    restart) do_stop && do_start "$DEV" ;;
    status) do_status ;;
    *) usage ;;
esac
