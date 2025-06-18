import json
import wikipedia
from GoogleNews import GoogleNews
from bs4 import BeautifulSoup
from seleniumbase import SB
import re
from app.utils.config import JSON_FILE

def get_wikipedia_summary(name):
    try:
        summary = wikipedia.summary(name, sentences=3)
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            page = wikipedia.page(e.options[0])
            return page.summary[:1000]
        except Exception:
            return None
    except wikipedia.exceptions.PageError:
        search_results = wikipedia.search(name)
        if search_results:
            try:
                return wikipedia.summary(search_results[0], sentences=3)
            except Exception:
                return None
        return None
    except Exception as e:
        print(f"Wikipedia error for {name}: {e}")
        return None

def get_google_news(query, max_results=3):
    googlenews = GoogleNews(lang='en')
    googlenews.search(query)
    results = googlenews.results()
    top_articles = results[:max_results]
    return [
        {
            "title": article["title"],
            "date": article["date"],
            "desc": article["desc"],
        }
        for article in top_articles
    ]

def slugify_name(name):
    return re.sub(r"[^a-z0-9\-]", "", name.lower().replace(" ", "-"))

def clean_founder_entries(education, jobs):
    # Remove filler/label lines and strip whitespace
    ignore_phrases = {
        "organization name", "title at company", "start date", "end date",
        "number of current jobs", "number of past jobs", "current job",
        "past jobs", "education", "degree name", "field of study"
    }

    # Pattern to match dates in various formats
    date_pattern = re.compile(
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|'
        r'\d{1,2}/\d{1,2}/\d{2,4}|'
        r'\d{4}-\d{2}-\d{2}|'
        r'\b\d{4}\b'
    )

    def clean_list(entries):
        cleaned = []
        for entry in entries:
            # Skip if entry contains any ignore phrases
            if any(phrase in entry.lower() for phrase in ignore_phrases):
                continue

            # Remove dates from the entry
            entry = date_pattern.sub('', entry)

            # Clean up the entry
            entry = re.sub(r"\s+", " ", entry).strip()
            entry = re.sub(r"^[–\-]\s*", "", entry)
            entry = re.sub(r"\s*[–\-]\s*$", "", entry)

            if entry and len(entry) > 5 and not any(phrase in entry.lower() for phrase in ignore_phrases):
                cleaned.append(entry)
        return list(set(cleaned))

    return {
        "education": clean_list(education),
        "jobs": clean_list(jobs),
    }

def scrape_crunchbase_founder_info(name):
    url = f"https://www.crunchbase.com/person/{slugify_name(name)}"
    education, jobs = [], []

    try:
        with SB(uc=True, headless=True) as browser:
            browser.open(url)
            browser.wait_for_ready_state_complete()
            browser.click_if_visible("#onetrust-accept-btn-handler", timeout=5)
            browser.sleep(3)

            page = browser.get_page_source()
            soup = BeautifulSoup(page, "lxml")

            sections = soup.select("section-card h2.section-title")
            for h2 in sections:
                title = h2.get_text(strip=True).lower()
                parent_card = h2.find_parent("section-card")
                content_wrapper = parent_card.select_one(".section-content-wrapper") if parent_card else None

                if content_wrapper:
                    content_items = [
                        " ".join(div.stripped_strings)
                        for div in content_wrapper.select("div")
                        if div.get_text(strip=True)
                    ]

                    if "education" in title:
                        education.extend(content_items)
                    elif "job" in title or "experience" in title:
                        jobs.extend(content_items)

        # Clean the scraped data before returning
        cleaned_data = clean_founder_entries(education, jobs)
        return cleaned_data

    except Exception as e:
        print(f"Crunchbase scraping failed for {name}: {e}")
        return {"education": [], "jobs": []}

def get_founders_info_and_save(json_path=JSON_FILE):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    founders = data.get("founder_names", [])
    data["founder_info"] = {}

    for founder in founders:
        print(f"\n\n==== Info for Founder: {founder} ====\n")

        info = {}

        # Wikipedia
        wiki_summary = get_wikipedia_summary(founder)
        print(f"Wikipedia Summary:\n{wiki_summary if wiki_summary else 'No Wikipedia summary available.'}\n")
        info["wikipedia_summary"] = wiki_summary

        # Google News
        news = get_google_news(founder)
        if news:
            print("Latest News:")
            for i, article in enumerate(news, 1):
                print(f"{i}. {article.get('date', '')} | {article.get('title', '')}\n   {article.get('desc', '')}\n")
        else:
            print("No news found.")
        info["latest_news"] = news

        # Crunchbase (now returns cleaned data)
        crunchbase_info = scrape_crunchbase_founder_info(founder)
        print(f"Crunchbase Education: {crunchbase_info['education']}")
        print(f"Crunchbase Jobs: {crunchbase_info['jobs']}")
        info.update(crunchbase_info)  # Directly add education and jobs to info

        data["founder_info"][founder] = info

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nAll founder info saved back to {json_path}")


if __name__ == "__main__":
    get_founders_info_and_save()