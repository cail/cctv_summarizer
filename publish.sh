
rsync -arv ../cctv_summarizer \
    igor@drakosha:~/drakosha-config/ \
    --exclude ".venv" --exclude ".git" --exclude "__pycache__" --exclude "tests"
