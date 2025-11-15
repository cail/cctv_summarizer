#!/bin/bash
# Simple runner script for CCTV Summarizer
# Can be used with cron or manually

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the summarizer
python3 cctv_summarizer.py "$@"
