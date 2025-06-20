import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json
import os
from openai import OpenAI
import re

def merge_company_data(existing, new):
    # Merge string fields: if both exist and are different, concatenate
    for key in ["description", "company_overview", "headquarters_location", "news_summary", "website_summary"]:
        old = existing.get(key, "")
        new_val = new.get(key, "")
        if old and new_val and old != new_val:
            existing[key] = f"{old}\n---\n{new_val}"
        elif new_val:
            existing[key] = new_val
    # Merge lists: founders, news, industries
    for key in ["founder_names", "industry_categories"]:
        old = set(existing.get(key, []))
        new_items = set(new.get(key, []))
        merged = list(old.union(new_items))
        existing[key] = merged
    # For news, merge by unique (title, url)
    if "news" in new:
        old_news = existing.get("news", [])
        old_set = {(n.get("title"), n.get("url")) for n in old_news}
        for n in new["news"]:
            if (n.get("title"), n.get("url")) not in old_set:
                old_news.append(n)
        existing["news"] = old_news
    # For all other fields, update if not present
    for key, value in new.items():
        if key not in existing or not existing[key]:
            existing[key] = value
    return existing

class WebsiteScraper:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    async def fetch_page_html(self, url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url)
            await page.wait_for_timeout(5000)
            html = await page.content()
            await browser.close()
            # Only extract <body> content to reduce size
            soup = BeautifulSoup(html, "lxml")
            body = soup.body
            if body:
                html = str(body)
            print(f"total len of html body is {len(html)}")
            # Further limit to first 30,000 characters
            html = html[:30000]
            print(f"[WebsiteScraper] Sending {len(html)} characters of HTML to LLM.")
            return html

    async def extract_main_info(self, company_name, website_url, html):
        prompt = f"""
You are an intelligent extraction agent. Analyze the following HTML content from the official website of '{company_name}'.
Extract and return ONLY a JSON object with these fields:
- name
- description
- overview
- headquarters
- industries (as a list)
- about_url (URL to About page, if found)
- news_url (URL to News/Blog/Updates page, if found)
- staff_url (URL to Staff/Leaders/Team page, if found)
If a field is missing, use 'Not Found'.
Return ONLY the JSON object, with no extra text, markdown, or explanation.

HTML to analyze:
{html}
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
        summary = summary.strip()
        if summary.startswith("```"):
            summary = re.sub(r"^```[a-zA-Z]*\n?", "", summary)
            summary = summary.rstrip("`").strip()
        try:
            summary_json = json.loads(summary)
        except Exception as e:
            print(f"[WebsiteScraper] LLM output not valid JSON: {e}")
            print(f"[WebsiteScraper] Raw LLM output: {summary}")
            summary_json = {}
        return summary_json

    async def extract_from_url(self, url, company_name, field):
        html = await self.fetch_page_html(url)
        prompt = f"""
You are an intelligent extraction agent. Analyze the following HTML content from the {field} page of '{company_name}'.
Extract and return ONLY a JSON object with these fields:
- founders (as a list, if staff/leaders page)
- news (as a list of objects with date, title, url, if news/blog page)
If a field is missing, use 'Not Found'.
Return ONLY the JSON object, with no extra text, markdown, or explanation.

HTML to analyze:
{html}
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
        summary = summary.strip()
        if summary.startswith("```"):
            summary = re.sub(r"^```[a-zA-Z]*\n?", "", summary)
            summary = summary.rstrip("`").strip()
        try:
            summary_json = json.loads(summary)
        except Exception as e:
            print(f"[WebsiteScraper] LLM output not valid JSON: {e}")
            print(f"[WebsiteScraper] Raw LLM output: {summary}")
            summary_json = {}
        return summary_json

    async def summarize_website(self, company_name, website_url):
        print(f"[WebsiteScraper] Fetching main page: {website_url}")
        main_html = await self.fetch_page_html(website_url)
        main_info = await self.extract_main_info(company_name, website_url, main_html)
        # Prepare result dict
        result = {
            "company_name": main_info.get("name", company_name),
            "description": main_info.get("description", "Not Found"),
            "company_overview": main_info.get("overview", "Not Found"),
            "headquarters_location": main_info.get("headquarters", "Not Found"),
            "industry_categories": main_info.get("industries", []),
            "founder_names": [],
            "news": [],
            "news_summary": "Not Found",
            "website_summary": "Not Found"
        }
        # Try to extract URLs for about, news, staff
        about_url = main_info.get("about_url")
        news_url = main_info.get("news_url")
        staff_url = main_info.get("staff_url")
        # Extract founders from staff/leaders page
        if staff_url and staff_url != 'Not Found':
            print(f"[WebsiteScraper] Fetching staff/leaders page: {staff_url}")
            staff_info = await self.extract_from_url(staff_url, company_name, "staff/leaders")
            if staff_info.get("founders") and staff_info["founders"] != 'Not Found':
                result["founder_names"] = staff_info["founders"]
        # Extract news from news/blog page
        if news_url and news_url != 'Not Found':
            print(f"[WebsiteScraper] Fetching news/blog page: {news_url}")
            news_info = await self.extract_from_url(news_url, company_name, "news/blog")
            if news_info.get("news") and news_info["news"] != 'Not Found':
                result["news"] = news_info["news"]
        # Optionally, extract more from about page if needed
        # Save the main_info as website_summary
        result["website_summary"] = main_info
        return result

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
        # Merge new data with existing data for the company
        all_data[company_name] = merge_company_data(all_data[company_name], result)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print(f"[✅ Success] Website summary for {company_name} saved to {json_path}")
        return result
    else:
        print(f"[❌ Error] No website data found for {company_name}. Not saving.")
        return None