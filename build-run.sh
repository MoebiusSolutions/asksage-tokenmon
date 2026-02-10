#!/bin/bash

# Fail on any error or undefined variable
set -e -o pipefail -u

SCRIPT_FILE="$(basename "$0")"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

/bin/bash "${SCRIPT_DIR}/build.sh"

. config.sh

# TODO: Remove old
# Read each file parameter, resolving to the fully qualified path
# AUTH_FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
# shift
# HISTORY_FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
# shift
# EXTRA_ARGS=("$@")
#
# # Create empty history file if it doesn't exist yet.
# # This prevents the file from being created by the mount (root-protected).
# if [[ ! -f "$HISTORY_FILE" ]]; then
#     echo "[]" > "$HISTORY_FILE"
# fi

HISTORY_FILE="${SCRIPT_DIR}/history.sqlite3"
# Create empty history file doesn't exist yet (preventing root-protected when docker does it).
if [[ ! -f "$HISTORY_FILE" ]]; then
    mkdir -p "$( dirname "$HISTORY_FILE" )"
    touch "$HISTORY_FILE"
fi

$CONTAINER_COMMAND run -it --rm \
    --security-opt label=disable \
    -v "${SCRIPT_DIR}/.asksage-auth.json:/.asksage-auth.json:ro" \
    -v "${HISTORY_FILE}:/history.sqlite3:rw" \
    asksage-tokenmon:local-build \
        --auth-file /.asksage-auth.json \
        --history-file /history.sqlite3 \
        "$@"

