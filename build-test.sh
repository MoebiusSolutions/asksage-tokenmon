#!/bin/bash

# Fail on any error or undefined variable
set -e -o pipefail -u

SCRIPT_FILE="$(basename "$0")"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

/bin/bash "${SCRIPT_DIR}/build.sh"

. config.sh

$CONTAINER_COMMAND run -it --rm \
    --entrypoint python \
    asksage-tokenmon:local-build \
    -m pytest

