
publish:
    rsync -arv ../cctv_summarizer \
        igor@drakosha:~/drakosha-config/ \
        --exclude "venv" --exclude ".git" --exclude "__pycache__" --exclude "tests"

upload:
    rsync -arv  igor@drakosha:~/drakosha-config/ha-config/www/cctv_summaries ../ha-config/www/


test_motion:
    venv/bin/python3 cctv_summarizer.py --test-changes 2>&1 | grep -E "(Testing motion detection for camera|Summary for|Would keep|Would discard|Total frames:)"
