import json
import torch
from newspaper import Article
from transformers import pipeline
from app.utils.config import JSON_FILE

# Use GPU if available
device = 0 if torch.cuda.is_available() else -1
summarizer = pipeline('summarization', model='facebook/bart-large-cnn', device=device)

def extract_article_text(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        print(f"[Error] Failed to extract from {url}: {e}")
        return ""

def summarize_articles(news_entries, max_input_length=1024):
    all_text = []

    for entry in news_entries:
        article_text = extract_article_text(entry.get('url') or entry.get('link', ''))
        if article_text:
            all_text.append(article_text)

    full_text = " ".join(all_text)
    chunks = [full_text[i:i+max_input_length] for i in range(0, len(full_text), max_input_length)]

    summaries = [summarizer(chunk)[0]['summary_text'] for chunk in chunks if chunk.strip()]
    return " ".join(summaries)

def update_json_with_summaries(json_path=JSON_FILE):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    news_entries = data.get('news', [])
    if not news_entries:
        print('[Info] No news entries found.')
        return

    summary = summarize_articles(news_entries)
    data['news_summary'] = summary  # store in a new field

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print('[✅ Success] Company news summary added.')
