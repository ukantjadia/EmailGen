from app.services.crunchbase_scrape import fetch_crunchbase_data
from app.services.founder_scrape import get_founders_info_and_save
# from app.services.news_scraper_new import scrape_and_save_news
from app.services.hybrid_pipeline import generate_email
from app.utils.config import JSON_FILE, EMBEDDINGS_PATH

def run_pipeline(company_name, json_file=JSON_FILE, embeddings_path=EMBEDDINGS_PATH):
    fetch_crunchbase_data(company_name, json_file)
    get_founders_info_and_save(json_file)
    # scrape_and_save_news(company_name, "Redmond, Washington", json_file, "sk-")
    return generate_email(json_file, embeddings_path)

if __name__ == "__main__":
    run_pipeline()

# import time
# import json
# import csv
# from fastapi import FastAPI
# from pydantic import BaseModel
# from typing import Optional
# from fastapi.responses import JSONResponse
# import uvicorn

# # Modules from your project
# from crunchbase_scrape import fetch_crunchbase_data
# from founder_scrape import get_founders_info_and_save
# from news_scraper_new import scrape_and_save_news
# from hybrid_pipeline import generate_email  # ⬅️ imported here

# # ========== CONFIG ==========

# CSV_FILE = "email_log.csv"
# JSON_FILE = "company_data.json"
# EMBEDDINGS_PATH = "email_embeddings.json"

# # ========== FASTAPI APP ==========

# app = FastAPI()
# latest_email = {"company": "", "subject": "", "email": ""}

# # ========== SCRAPER ==========

# def scrape_company_info(company_name: str) -> dict:
#     crunchbase_url = f"https://www.crunchbase.com/organization/{company_name.lower().replace(' ', '-')}"
#     print(f"🔍 Scraping info for {company_name}")
#     start = time.time()

#     try:
#         data = fetch_crunchbase_data(crunchbase_url)
#         # print(data)
#         with open(JSON_FILE, "w", encoding="utf-8") as f:
#             json.dump(data, f, indent=2, ensure_ascii=False)

#         get_founders_info_and_save(JSON_FILE)

#         try:
#             scrape_and_save_news(company_name, "Redmond, Washington", JSON_FILE, "YOUR_DEEPSEEK_API_KEY")
#         except Exception as e:
#             print(f"⚠️ News scraping failed: {str(e)}")

#         with open(JSON_FILE, "r", encoding="utf-8") as f:
#             return json.load(f)
#     except Exception as e:
#         print(f"❌ Error during scraping: {str(e)}")
#         return {"error": str(e)}
#     finally:
#         print(f"✅ Scraping completed in {time.time() - start:.2f}s")

# # ========== CSV LOGGER ==========

# def append_to_csv(entry: dict):
#     fieldnames = ["company", "subject", "email"]
#     try:
#         with open(CSV_FILE, "a", newline='', encoding="utf-8") as f:
#             writer = csv.DictWriter(f, fieldnames=fieldnames)
#             if f.tell() == 0:
#                 writer.writeheader()
#             writer.writerow(entry)
#     except Exception as e:
#         print(f"❌ Failed to write to CSV: {e}")

# # ========== FASTAPI ENDPOINTS ==========

# class CompanyRequest(BaseModel):
#     company_name: str

# @app.post("/scrape")
# def scrape_and_generate(request: CompanyRequest):
#     global latest_email
#     company_name = request.company_name
#     scrape_company_info(company_name)
#     email = generate_email(JSON_FILE, EMBEDDINGS_PATH)
#     append_to_csv(email)
#     latest_email = email
#     return JSONResponse(content=email)

# @app.get("/email")
# def get_latest_email():
#     return latest_email

# # ========== MAIN RUNNER ==========

# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=8000)
