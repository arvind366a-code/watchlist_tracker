#!/bin/bash
# Watchlist daily check and auto-push script

cd /home/claw/projects/watchlist_tracker

# Run watchlist summary and save to log
echo "=== $(date) ===" >>/home/claw/.watchlist_logs/watchlist.log
uv run watchlist summary >>/home/claw/.watchlist_logs/watchlist.log 2>&1
echo "" >>/home/claw/.watchlist_logs/watchlist.log

# Push any changes to GitHub
git add -A
git commit -m "Auto-update: $(date +%Y-%m-%d)" 2>/dev/null
git push origin master 2>/dev/null

# Clean logs older than 30 days
find /home/claw/.watchlist_logs -name "*.log" -mtime +30 -delete 2>/dev/null