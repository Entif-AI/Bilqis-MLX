#!/bin/sh
# Explicit-source, external-volume, no-deletion transfer utility.
set -eu
exec python3 -m bilqis_mlx.backup "$@"
