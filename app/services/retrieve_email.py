from sentence_transformers import SentenceTransformer, util
import numpy as np
import json

model = SentenceTransformer("all-MiniLM-L6-v2")

def extract_company_text(data: dict) -> str:
    description = data.get("description", "")
    overview = data.get("company_overview", "")
    news = data.get("news", "")
    industries = ", ".join(data.get("industry_categories", []))
    return f"{description}\n\n{overview}\n\nIndustries: {industries}\n\nRecent News: {news[:300]}"

def retrieve_similar_email(company_text: str, embeddings_file: str) -> str:
    query_emb = model.encode(company_text)
    with open(embeddings_file, "r", encoding="utf-8") as f:
        embedded = json.load(f)

    best_score, best_email = -1, None
    for e in embedded:
        emb = np.array(e["embedding"], dtype=np.float32)
        score = util.cos_sim(query_emb, emb).item()
        if score > best_score:
            best_score, best_email = score, e["email"]

    return best_email
