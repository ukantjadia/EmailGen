import sys
import pandas as pd
import os
import asyncio
import re
from playwright.async_api import async_playwright
import os
from openai import OpenAI
from urllib.parse import quote_plus
import random
import json

from app.services.browser_config import PlaywrightManager

class AsyncCompanyScraper:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.df = pd.DataFrame(columns=[
            'Recent News'
        ])
        self.sources = ["Name", "Recent News"]
        self.google_search = "https://www.bing.com/search?q="
        self.manager = PlaywrightManager(headless=True)
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async def fetch_page_text(self, page, url):
        try:
            await asyncio.sleep(random.uniform(1, 3))
            await page.goto(url)
            await page.wait_for_timeout(10000)
            await page.evaluate("""
            const contentDiv = document.querySelector('#b_content');
            if (contentDiv && contentDiv.style.visibility === 'hidden') {
                contentDiv.style.visibility = 'visible';
            }
            """)

            await page.mouse.move(random.randint(100, 300), random.randint(100, 300))
            await page.mouse.wheel(0, random.randint(100, 300))

            results = []
            result_elements = page.locator("li.b_algo")
            for element in await result_elements.all():
                texts = await element.locator("p").inner_text()
                results.append(texts)

            return "\n".join(results)
        except Exception as e:
            return f"Error loading page: {e}"

    async def fetch_with_retries(self, page, url, retries=3, base_delay=2):
        for attempt in range(retries):
            try:
                return await self.fetch_page_text(page, url)
            except Exception as e:
                wait_time = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                print(f"Error on attempt {attempt+1} for {url}: {e}. Retrying in {wait_time:.1f} seconds...")
                await asyncio.sleep(wait_time)
        return f"Failed to load {url} after {retries} attempts."

    async def get_chat_response(self, prompt):
        def sync_chat_request():
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an intelligent extraction agent. Your job is to analyze raw text "
                            "(scraped from search engines) and extract recent news about companies, "
                            "**based only on what's actually in the text**. If the required info is missing or uncertain, "
                            "return only the text: Not Found."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            return response.choices[0].message.content
        return await asyncio.to_thread(sync_chat_request)

    async def process_company(self, company_name: str, location: str):
        query = quote_plus(f"{company_name} {location}")

        query_variants = [
            [  # Simple News Queries
                f'{query} news',
                f'{query} latest news',
                f'{query} recent news',
                f'{query} management change',
                f'{query} board member change',
                f'{query} new product',
                f'{query} new important person',
                f'{query} investment',
            ],
            [  # Simple Past Year News Queries
                f'{query} news 2023',
                f'{query} news 2024',
            ],
        ]

        urls = [f'https://www.bing.com/search?q={random.choice(group)}' for group in query_variants]

        await self.manager.start_browser(stealth_on=True)
        context = await self.manager.browser.new_context()

        tasks = []
        for url in urls:
            page = await context.new_page()
            tasks.append(self.fetch_with_retries(page, url))

        texts = await asyncio.gather(*tasks)

        await context.close()
        await self.manager.stop_browser()

        print(f"Total texts extracted: {len(texts)}")

        news_text = texts[0]+texts[1] if len(texts) > 0 else "No news data"

        prompt = f"""
You are an intelligent extraction agent. Your job is to analyze raw text scraped from search engines about the company '{company_name}' in '{location}'.

Extract the following information, using ONLY what is actually present in the text:
- A concise company description or overview
- Headquarters location (city, region, country if possible)
- List of founders (names)
- Industry categories
- 2-3 recent news items (each as a one-sentence summary, with date/source if possible)

If any field is missing or uncertain, return only the text: Not Found for that field.

Format your answer as clear, labeled sections. The extracted information will be used to write a personalized, engaging investor outreach email to the company.

# Here is the text to analyze:
# {texts[0]+texts[1] if len(texts) > 0 else 'No news data'}
"""

        news_summary = await self.get_chat_response(prompt)

        return {
            "Company": company_name,
            "Recent News": news_summary if news_summary else "Not Found",
        }

    # async def save(self, df, folder='../data'):
    #     os.makedirs(folder, exist_ok=True)
    #     df = pd.DataFrame([df])

    #     # Set file paths
    #     csv_path = os.path.join(folder, 'company_news.csv')
    #     excel_path = os.path.join(folder, 'company_news.xlsx')

    #     if os.path.exists(csv_path):
    #         data = pd.read_csv(csv_path)
    #         data = pd.concat([data, df], axis=0).reset_index(drop=True)
    #         data.to_csv(csv_path, index=False)
    #         data.to_excel(excel_path, index=False)
    #     else:
    #         df.to_csv(csv_path, index=False)
    #         df.to_excel(excel_path, index=False)

    # async def combine_leads(self, df, leads, folder='../data'):
    #     os.makedirs(folder, exist_ok=True)
    #     df = pd.read_csv(folder + '/' + df)
    #     leads = pd.read_csv(folder + '/' + leads)

    #     combined_leads = pd.merge(leads, df, on='Name', how='left')

    #     # Set file paths
    #     csv_path = os.path.join(folder, 'new_leads.csv')
    #     excel_path = os.path.join(folder, 'new_leads.xlsx')

    #     combined_leads.to_csv(csv_path, index=False)
    #     combined_leads.to_excel(excel_path, index=False)

    # async def process_all_companies(self, companies: list[dict], location: str) -> list[dict]:
    #     semaphore = asyncio.Semaphore(3)
    #     processed_companies = []

    #     user_agents = [
    #         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    #         'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    #         'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_16) AppleWebKit/537.36 (KHTML, like Gecko) Version/14.0 Safari/537.36',
    #         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36 Edg/90.0.818.62',
    #         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 OPR/45.0.2552.888',
    #         'Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36',
    #         'Mozilla/5.0 (Android 10; Mobile; rv:89.0) Gecko/89.0 Firefox/89.0',
    #         'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4_2 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/537.36',
    #         'Mozilla/5.0 (Android 10; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0 Edge/91.0.864.48',
    #         'Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Mobile Safari/537.36 OPR/58.0.2875.157',
    #         'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:41.0) Gecko/20100101 Firefox/41.0',
    #         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
    #         'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0'
    #     ]

    #     await self.manager.start_browser(stealth_on=True)
    #     contexts = []
    #     for i in range(3):
    #         user_agent = random.choice(user_agents)
    #         context = await self.manager.browser.new_context(user_agent=user_agent)
    #         contexts.append(context)

    #     async def process_with_semaphore(company, context):
    #         async with semaphore:
    #             name = company.get("Company", "NA")
    #             result = await self.process_company(name, location)
    #             return {**company, **result}

    #     tasks = []
    #     for i, company in enumerate(companies):
    #         context = contexts[i % 3]  # round-robin assignment
    #         tasks.append(asyncio.create_task(process_with_semaphore(company, context)))

    #     processed_companies = await asyncio.gather(*tasks)

    #     for context in contexts:
    #         await context.close()
    #     await self.manager.stop_browser()

    #     return processed_companies


# This is the function you will call from your pipeline
def scrape_and_save_news(company_name, location, json_path, api_key):
    scraper = AsyncCompanyScraper(api_key=api_key)
    print("ino the scrap func... ")
    result = asyncio.run(scraper.process_company(company_name, location))

    # Save or merge with existing JSON
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    # Append or update the news data under the company name
    data[company_name] = result["Recent News"]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[✅ Success] News summary for {company_name} saved to {json_path}")
    return result["Recent News"]