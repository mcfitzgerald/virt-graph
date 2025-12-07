#!/bin/bash
# Archive current benchmark results with version tag

set -e

# Get version from pyproject.toml
VERSION=$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
DATE=$(date +%Y-%m-%d)
ARCHIVE_NAME="v${DATE}_${VERSION}"
ARCHIVE_DIR="benchmark/archive/${ARCHIVE_NAME}"

# Check if results exist
if [ ! -f "benchmark/results/benchmark_results.md" ]; then
    echo "No benchmark results to archive"
    exit 0
fi

# Check if already archived
if [ -d "${ARCHIVE_DIR}" ]; then
    echo "Archive ${ARCHIVE_NAME} already exists"
    exit 1
fi

# Create archive directory
mkdir -p "${ARCHIVE_DIR}"

# Copy results
cp benchmark/results/benchmark_results.md "${ARCHIVE_DIR}/"
cp benchmark/results/benchmark_results.json "${ARCHIVE_DIR}/"

# Get git commit if available
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Create metadata
cat > "${ARCHIVE_DIR}/metadata.yaml" << EOF
version: "${ARCHIVE_NAME}"
date: "${DATE}"
virt_graph_version: "${VERSION}"
git_commit: "${GIT_COMMIT}"
notes: |
  Archived benchmark results.
EOF

echo "Archived to ${ARCHIVE_DIR}"
echo "You can now run fresh benchmarks"
