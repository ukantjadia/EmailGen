# app/utils/config.py

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSV_FILE = os.path.join(BASE_DIR, 'data', 'email_log.csv')
JSON_FILE = os.path.join(BASE_DIR, 'data', 'company_data.json')
EMBEDDINGS_PATH = os.path.join(BASE_DIR, 'data', 'email_embeddings.json')
