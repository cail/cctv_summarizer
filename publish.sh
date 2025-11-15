
rsync -arv ../cctv_summarizer \
    igor@drakosha:~/drakosha-config/ \
    --exclude "venv" --exclude ".git" --exclude "__pycache__" --exclude "tests"

# rsync -arv  igor@drakosha:~/drakosha-config/ha-config/www/cctv_summaries ../ha-config/www/
