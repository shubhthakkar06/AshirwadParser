#!/bin/bash
set -e

echo "=== Starting BAPS Ashirwad Background Indexer Worker ==="
python indexer.py &

echo "=== Starting Streamlit Dashboard on port ${PORT:-8501} ==="
streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true
