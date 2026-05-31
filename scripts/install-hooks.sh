#!/usr/bin/env bash
# Run once after cloning: bash scripts/install-hooks.sh
git config core.hooksPath .githooks
echo "Git hooks installed. Pre-commit .env scan is active."
