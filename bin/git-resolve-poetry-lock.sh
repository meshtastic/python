#!/usr/bin/env bash

set -e

# This is a little helper you can use to resolve git merge conflicts in poetry.lock
# with minimal changes vs the requested lib versions
# Based on this article with a good description of best practices:
# https://www.peterbe.com/plog/how-to-resolve-a-git-conflict-in-poetry.lock

echo "Resolving poetry.lock merge conflicts, you'll need to run git commit yourself..."

# Get poetry.lock to look like it does in master
git checkout --theirs poetry.lock
# Rewrite the lock file
poetry lock --no-update
git add poetry.lock

# Update your poetry env to match the new merged lock file
poetry install
