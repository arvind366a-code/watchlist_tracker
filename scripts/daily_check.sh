#!/bin/bash
# Watchlist daily check and auto-push script

set -e

# Set PATH for cron
export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

PROJECT_DIR="/home/claw/projects/watchlist_tracker"
LOG_DIR="/home/claw/.watchlist_logs"

cd "$PROJECT_DIR"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Run watchlist summary and save to log
echo "=== $(date) ===" >> "$LOG_DIR/watchlist.log"
uv run watchlist summary >> "$LOG_DIR/watchlist.log" 2>&1
echo "" >> "$LOG_DIR/watchlist.log"

# Push any changes to GitHub
git add -A 2>/dev/null || true
git commit -m "Auto-update: $(date +%Y-%m-%d)" 2>/dev/null || true
git push origin master 2>/dev/null || true

# Clean logs older than 30 days
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null || true