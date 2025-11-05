#!/usr/bin/env bash
pip install -r requirements.txt
python -m uvicorn ai_analyzer_server:app --host 0.0.0.0 --port 10000
