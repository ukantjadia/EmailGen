from seleniumbase import SB
from bs4 import BeautifulSoup
import json
import re
import html.entities
from urllib.parse import urlparse
from app.utils.config import JSON_FILE
import httpx
from parsel import Selector


def extract_crunchbase_info(html_content, company_name="Unknown"):
    """
    Extracts structured company data from Crunchbase HTML content.

    Args:
        html_content (str): Raw HTML from Crunchbase page
        company_name (str): Name of the company, derived from URL

    Returns:
        dict: Structured company information with cleaned values
    """
    result = {
        "company_name": company_name,
        "description": None,
        "company_overview": None,
        "headquarters_location": None,
        "founder_names": [],
        "industry_categories": [],
        "news": []
    }

    soup = BeautifulSoup(html_content, "lxml")
    json_script = soup.find("script", {"id": "ng-state", "type": "application/json"})
    json_text = json_script.string if json_script else html_content

    def extract_data(pattern, text=json_text, default=None):
        """Helper to extract first regex match from text"""
        match = re.search(pattern, text)
        return match.group(1) if match else default

    # Core company information
    result.update(
        {
            "description": extract_data(r'"target_short_description"\s*:\s*"([^"]+)"'),
            "company_overview": extract_data(r'"description"\s*:\s*"([^"]+)"')
        }
    )

    # Location information
    if location_data := extract_data(
        r'"location_identifiers"\s*:\s*\[(.*?)\]', json_text
    ):
        location_parts = {}
        for match in re.finditer(
            r'"location_type"\s*:\s*"([^"]+)".*?"value"\s*:\s*"([^"]+)"', location_data
        ):
            location_parts[match.group(1)] = match.group(2)
        result["headquarters_location"] = ", ".join(
            location_parts.get(key, "") for key in ("city", "region", "country")
        )

    # Founders information
    if founders := extract_data(r'"founder_identifiers"\s*:\s*\[(.*?)\]', json_text):
        result["founder_names"] = re.findall(r'"value"\s*:\s*"([^"]+)"', founders)

    # Industry categories (fallback to HTML if JSON not found)
    if categories := extract_data(r'"categories"\s*:\s*\[(.*?)\]', json_text):
        result["industry_categories"] = re.findall(
            r'"value"\s*:\s*"([^"]+)"', categories
        )
    else:
        result["industry_categories"] = [
            div.text.strip() for div in soup.select("div.chip-text")
        ]

    # News Section
    news_items = []
    news_divs = soup.select("section-card h2.section-title")
    for h2 in news_divs:
        if "Recent News" in h2.get_text():
            activity_rows = h2.find_parent("section-card").select(".activity-row")
            for row in activity_rows:
                date_tag = row.select_one(".activity-title .field-type-date")
                date = date_tag.get("title", "").strip() if date_tag else None

                link_tag = row.select_one("a")
                title = link_tag.get_text(strip=True) if link_tag else None
                url = link_tag["href"] if link_tag else None

                source_tag = row.select_one("press-reference span")
                source = source_tag.get_text(strip=True).replace("—", "").strip() if source_tag else None

                if title and url:
                    news_items.append({
                        "date": date,
                        "source": source,
                        "title": title,
                        "url": url
                    })
            break

    result["news"] = news_items
    return clean_string_values(result)


def clean_string_values(data):
    """Cleans string values recursively"""
    if isinstance(data, dict):
        return {k: clean_string_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [clean_string_values(v) for v in data]
    if isinstance(data, str):
        cleaned = data.replace("\\n", "\n").replace("\\r", "\r")
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


def fetch_crunchbase_data(company_name, json_file=JSON_FILE):
    """
    Hybrid Crunchbase scraper: Try httpx/parsel for Angular cache. If blocked (403 or ng-state missing),
    use SeleniumBase as fallback. To reduce bot detection, first open a non-protected page, then the company page.
    """
    # url = f"https://www.crunchbase.com/"
    url = f"https://www.crunchbase.com/organization/{company_name.lower().replace(' ', '-')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    # # 1. Try httpx/parsel first
    # try:
    #     with httpx.Client(follow_redirects=True, timeout=30) as client:
    #         resp = client.get(url, headers=headers)
    #         if resp.status_code == 200:
    #             sel = Selector(text=resp.text)
    #             ng_state = sel.css('script#ng-state::text').get()
    #             if ng_state:
    #                 app_state_data = json.loads(ng_state)
    #                 cache_keys = list(app_state_data.get("HttpState", {}))
    #                 dataset_key = next((key for key in cache_keys if "data/entities" in key), None)
    #                 if dataset_key:
    #                     dataset = app_state_data["HttpState"][dataset_key]["data"]
    #                     result = {
    #                         "company_name": dataset['properties'].get('title'),
    #                         "description": dataset['properties'].get('short_description'),
    #                         "company_overview": dataset['properties'].get('description'),
    #                         "headquarters_location": dataset['properties'].get('location_identifiers'),
    #                         "founder_names": [f['value'] for f in dataset.get('cards', {}).get('founders_image_list', [])],
    #                         "industry_categories": [c['value'] for c in dataset.get('cards', {}).get('categories', [])],
    #                         "news": dataset.get('cards', {}).get('news', []),
    #                     }
    #                     with open(json_file, "w", encoding="utf-8") as f:
    #                         json.dump(result, f, indent=2, ensure_ascii=False)
    #                     print(f"✅ Data saved to {json_file} for {company_name}")
    #                     return result
    #             print("ng-state not found, possible bot block or page structure changed. Falling back to SeleniumBase.")
    #         else:
    #             print(f"Failed to fetch page: {resp.status_code}. Falling back to SeleniumBase.")
    # except Exception as e:
    #     print(f"Error fetching Crunchbase data with httpx: {e}. Falling back to SeleniumBase.")
    # 2. Fallback: SeleniumBase with anti-bot evasion
    try:
        with SB(uc=True, headless=True) as browser:
            # Open a non-protected page first (e.g., Crunchbase home)
            browser.open("https://www.crunchbase.com/")
            browser.sleep(2)
            browser.close_window()
            # Now open the company page
            browser.open(url)
            browser.wait_for_ready_state_complete()
            browser.sleep(2)
            # Accept cookies if present
            browser.click_if_visible("#onetrust-accept-btn-handler", timeout=5)
            browser.sleep(2)
            html = browser.get_page_source()
            result = extract_crunchbase_info(html, company_name)
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"✅ [SeleniumBase] Data saved to {json_file} for {company_name}")
            return result
    except Exception as e:
        print(f"❌ SeleniumBase fallback also failed: {e}")
        return None


def main():
    """Entry point"""
    target_company = "airbnb"
    try:
        print(f"🔄 Fetching data for: {target_company}")
        company_data = fetch_crunchbase_data(target_company)
        print(f"✅ Data saved to company_data.json with name: {company_data.get('company_name') if company_data else 'N/A'}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
