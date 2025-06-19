import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json
import os

def clean_string_values(data):
    import re, html.entities
    if isinstance(data, dict):
        return {k: clean_string_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [clean_string_values(v) for v in data]
    if isinstance(data, str):
        cleaned = data.replace("\n", " ").replace("\r", " ")
        try:
            cleaned = cleaned.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            pass
        cleaned = re.sub(
            r"&([a-z]+|#[0-9]+);",
            lambda m: chr(html.entities.name2codepoint.get(m.group(1), 0)),
            cleaned,
        )
        return re.sub(r"\s+", " ", cleaned).strip()
    return data

async def scrape_and_save_crunchbase(company_url, json_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(company_url)
        await page.wait_for_timeout(6000)  # Wait for JS to load
        html = await page.content()
        await browser.close()

        soup = BeautifulSoup(html, "lxml")
        # Extract fields (selectors may need adjustment)
        name = soup.find("h1", {"data-test": "profile-name"})
        name = name.get_text(strip=True) if name else None
        description = soup.find("span", {"data-test": "profile-description"})
        description = description.get_text(strip=True) if description else None

        # Headquarters location
        hq = soup.find("span", string="Headquarters")
        headquarters_location = None
        if hq:
            hq_parent = hq.find_parent("li")
            if hq_parent:
                loc_span = hq_parent.find("span", {"data-test": "location"})
                headquarters_location = loc_span.get_text(strip=True) if loc_span else None

        # Founders
        founders = []
        founders_section = soup.find("section", {"id": "founders"})
        if founders_section:
            founders = [a.get_text(strip=True) for a in founders_section.find_all("a")]
        else:
            # Try fallback: look for 'Founders' label
            founders_label = soup.find("span", string="Founders")
            if founders_label:
                parent = founders_label.find_parent("li")
                if parent:
                    founders = [a.get_text(strip=True) for a in parent.find_all("a")]

        # Industry categories
        industry_categories = []
        industry_label = soup.find("span", string="Industries")
        if industry_label:
            parent = industry_label.find_parent("li")
            if parent:
                industry_categories = [span.get_text(strip=True) for span in parent.find_all("span") if span != industry_label]

        # News (not implemented here, but could be added)
        news = []

        result = {
            "company_name": name,
            "description": description,
            "company_overview": description,  # For compatibility
            "headquarters_location": headquarters_location,
            "founder_names": founders,
            "industry_categories": industry_categories,
            "news": news
        }
        result = clean_string_values(result)
        # Save to JSON
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[✅ Success] Company data for {name} saved to {json_path}")
        return result

def scrape_and_save_crunchbase_sync(company_url, json_path):
    return asyncio.run(scrape_and_save_crunchbase(company_url, json_path))

# Usage example:
# scrape_and_save_crunchbase_sync("https://www.crunchbase.com/organization/airbnb", "data/airbnb.json")