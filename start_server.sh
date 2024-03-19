arch -arm64 uvicorn server:app --host 0.0.0.0 --port 10000 --workers 4 --log-level debug &
