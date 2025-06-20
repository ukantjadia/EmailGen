import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json
import os
from openai import OpenAI

class WebsiteScraper:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    async def fetch_page_text(self, url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url)
            await page.wait_for_timeout(5000)
            html = await page.content()
            await browser.close()
            soup = BeautifulSoup(html, "lxml")
            # Try to extract main text from About, Team, or Overview sections
            text = " ".join([t.get_text(" ", strip=True) for t in soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])])
            return text[:8000]  # Limit to 8k chars for LLM

    async def summarize_website(self, company_name, website_url):
        # Try About, Team, and Home pages
        pages = [website_url]
        if not website_url.endswith('/'):
            website_url += '/'
        pages += [website_url + path for path in ["about", "team", "company", "leadership"]]
        all_text = ""
        for url in pages:
            try:
                text = await self.fetch_page_text(url)
                if text and len(text) > 200:
                    all_text += f"\n---\nFrom {url}:\n" + text
            except Exception as e:
                print(f"[WebsiteScraper] Failed to fetch {url}: {e}")
        if not all_text:
            return None
        prompt = f"""
You are an intelligent extraction agent. Analyze the following text scraped from the official website of '{company_name}'.
Extract and summarize:
- Company overview/mission
- Leadership or founders (if mentioned)
- Any unique value proposition or product focus
- Any contact/location info
Format your answer as a JSON object with keys: company_overview, leadership, value_proposition, contact_info. If a field is missing, use 'Not Found'.

Text to analyze:
{all_text}
"""
        def sync_chat_request():
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            return response.choices[0].message.content
        summary = await asyncio.to_thread(sync_chat_request)
        try:
            summary_json = json.loads(summary)
        except Exception as e:
            print(f"[WebsiteScraper] LLM output not valid JSON: {e}")
            summary_json = {"company_overview": summary}
        return summary_json

def scrape_and_save_website(company_name, website_url, json_path, api_key):
    scraper = WebsiteScraper(api_key=api_key)
    print(f"[WebsiteScraper] Scraping website for {company_name} at {website_url}")
    result = asyncio.run(scraper.summarize_website(company_name, website_url))
    if result:
        # Load or create the company data file as a dict of companies
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    all_data = json.load(f)
                except Exception:
                    all_data = {}
        else:
            all_data = {}
        if company_name not in all_data:
            all_data[company_name] = {}
        all_data[company_name]["website_summary"] = result
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print(f"[✅ Success] Website summary for {company_name} saved to {json_path}")
        return result
    else:
        print(f"[❌ Error] No website data found for {company_name}. Not saving.")
        return None