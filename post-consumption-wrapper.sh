#!/usr/bin/env bash

# paperless-ngx post-consumption script
#
# https://docs.paperless-ngx.com/advanced_usage/#post-consume-script
#

set -euo pipefail

SCRIPT_PATH=$(readlink -f "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")

DOCUMENT_ID="$1"
ORIGINAL_FILENAME="$2"
DOCUMENT_PATH="$3"
THUMBNAIL_PATH="$4"
DOWNLOAD_URL="$5"
THUMBNAIL_URL="$6"
OWNER="$7"
DIFF="$8"

# make it available to child processes
export DOCUMENT_ID
export ORIGINAL_FILENAME
export DOCUMENT_PATH
export THUMBNAIL_PATH
export DOWNLOAD_URL
export THUMBNAIL_URL
export OWNER
export DIFF

# Have something written into Paperless-ngx logs
echo "Hello. Post-consumption script here."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Start Post-Consumption für $ORIGINAL_FILENAME"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] DOCUMENT_PATH $DOCUMENT_PATH"


# start axsreference
python ${SCRIPT_DIR}/axsreference/post_process.py

echo 0
