#!/usr/bin/env bash
set -e

# Ensure we run from the project root
cd "$(dirname "$0")/.."

# 1. Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: Working directory has uncommitted changes. Please commit or stash them first."
    exit 1
fi

# 2. Extract version from pyproject.toml
VERSION_LINE=$(grep "^version =" pyproject.toml | head -n 1)
if [ -z "$VERSION_LINE" ]; then
    echo "Error: Could not find version in pyproject.toml"
    exit 1
fi

# Strip everything before and including the first double quote, and after the last double quote
VERSION=${VERSION_LINE#*\"}
VERSION=${VERSION%\"}

if [ -z "$VERSION" ]; then
    echo "Error: Extracted version is empty."
    exit 1
fi

TAG="v$VERSION"
echo "Releasing version $TAG..."

# 3. Check if tag already exists
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Error: Git tag $TAG already exists!"
    exit 1
fi

# 4. Tag and push
git tag -a "$TAG" -m "Release $TAG"
echo "Pushing tag $TAG to origin..."
git push origin "$TAG"

echo "Successfully released and pushed $TAG!"
