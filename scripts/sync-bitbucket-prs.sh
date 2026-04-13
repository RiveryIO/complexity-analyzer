#!/bin/bash
# Sync Bitbucket PRs for all known repositories
# This script fetches merged PRs from the last 180 days

set -e

DAYS=180
CSV_FILE="complexity-report.csv"
REPOS=(
    "boomii/kh-commons"
    "boomii/kh-kubernetes"
    "boomii/kh-retrieve-api"
    "boomii/kh-terraform"
    "boomii/kh-worker"
    "boomii/knowledge-hub-api"
    "boomii/knowledge-hub-frontend"
    "boomii/rivery-api-service"
    "boomii/rivery-dev-agent"
    "boomii/rivery-fire-service"
)

echo "🔄 Fetching Bitbucket PRs from ${#REPOS[@]} repositories (last $DAYS days)..."
echo ""

for repo in "${REPOS[@]}"; do
    echo "📦 Processing $repo..."

    # Extract workspace and repo name
    workspace=$(echo "$repo" | cut -d'/' -f1)
    repo_name=$(echo "$repo" | cut -d'/' -f2)

    # Run batch-analyze for this Bitbucket repo
    complexity-cli batch-analyze \
        --bitbucket "$workspace/$repo_name" \
        --days $DAYS \
        -o "$CSV_FILE" \
        --provider anthropic \
        || echo "⚠️  Warning: Failed to fetch from $repo"

    echo ""
done

echo "✅ Bitbucket sync complete!"
echo ""
echo "📊 Summary:"
grep ",bitbucket," "$CSV_FILE" | wc -l | xargs -I {} echo "   Total Bitbucket PRs: {}"
grep ",bitbucket," "$CSV_FILE" | cut -d',' -f3 | sort -u | wc -l | xargs -I {} echo "   Unique developers: {}"
echo ""
echo "🔍 Recent Bitbucket PRs by orhss:"
grep ",orhss," "$CSV_FILE" | grep ",bitbucket," | tail -5 | cut -d',' -f1,4,6 | column -t -s','
