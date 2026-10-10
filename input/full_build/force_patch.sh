#!/bin/sh
# BSD patch otherwise auto-ignores -R during upstream's reverse dry-run probe,
# reporting an unapplied patch as already applied. Force the requested direction.
exec "${TERMUX_OMARCHY_PATCH:?original patch executable required}" --force "$@"
