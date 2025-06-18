#email_generator.py
import os
import re
import requests
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/your-repo",
    "X-Title": "Cold Email Generator"
}

MODEL = "meta-llama/llama-3-70b-instruct"

VARIANT_MODES = [
    {"focus": "Product Insight", "tone": "direct", "style": "Crisp and pragmatic, focused on product innovation."},
    {"focus": "Team & Talent Fit", "tone": "warm", "style": "Founder-to-founder tone, thoughtful and people-centric."},
    {"focus": "Market Perspective", "tone": "analyst", "style": "Inquisitive, data-driven, and strategic."},
    {"focus": "Founder Commonality", "tone": "relational", "style": "Shared values and background with personalization."},
    {"focus": "Strategic Fit", "tone": "investor", "style": "Decisive and ROI-focused, highlighting synergy."},
    {"focus": "Curious Analyst", "tone": "curious", "style": "Open-ended questions from a junior analyst."},
    {"focus": "Relational & Friendly", "tone": "warm", "style": "Human and empathetic tone with a collaborative spirit."}
]

def build_email_prompt(company_name: str, full_context: str, tone: str, style_desc: str,
                       focus_desc: str, commonality_hint: str = "", extra_context: str = "") -> str:
    return f"""
You are a strategic writing assistant for Caprae, a private investment firm conducting cold outreach.

Tone: {style_desc}
Persona: {tone.capitalize()}
Focus: {focus_desc}

Instructions:
- Write a 3-sentence cold outreach email.
- Start with a reference to the company, its product, or a leadership idea.
- Ask a thoughtful question based on the focus.
- End with an invitation to discuss or connect.
- Avoid salesy or generic language (no “excited”, “admire”, “impressed”).
- No greetings or sign-offs.

Company: {company_name}

Background context:
{full_context}

{commonality_hint}

{extra_context}

Respond in this format:

Email: [3-sentence body]

Title: Discussion on [main theme 1] and [main theme 2]
"""

def generate_email_variants(company_name: str, context_per_variant: Dict[str, str],
                            commonality_hint: str = "", extra_context: str = "") -> List[Dict]:
    variants = []
    for config in VARIANT_MODES:
        focus = config["focus"]
        prompt_context = context_per_variant.get(focus, "")

        prompt = build_email_prompt(
            company_name=company_name,
            full_context=prompt_context,
            focus_desc=focus,
            tone=config["tone"],
            style_desc=config["style"],
            commonality_hint=commonality_hint,
            extra_context=extra_context
        )

        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=HEADERS,
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8
                },
                timeout=30
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

            title_match = re.search(r"(?:Title|Subject):\s*(Discussion.+)", content)
            email_match = re.search(r"(?:Email:|^Email)?\s*(.+?)(?:Title:|$)", content, re.DOTALL)

            if email_match:
                raw_email = email_match.group(1).strip()
                cleaned_email = re.sub(r"(Best regards.*|Thanks.*|Sincerely.*)", "", raw_email, flags=re.IGNORECASE)
                cleaned_email = re.sub(r"^(Subject|Title):.*", "", cleaned_email, flags=re.IGNORECASE).strip()

                if title_match:
                    title = title_match.group(1).strip()
                else:
                    first_line = cleaned_email.splitlines()[0] if cleaned_email else ""
                    keywords = re.findall(r"\b\w+\b", first_line)
                    title = "Discussion on " + " ".join(keywords[:2]) if keywords else f"Discussion on {focus}"

                variants.append({
                    "email": cleaned_email,
                    "title": title,
                    "tone": config["tone"],
                    "focus": config["focus"],
                    "style": config["style"]
                })
            else:
                print("⚠️ Could not extract email body. Raw output:\n", content)
                variants.append({"error": "Could not extract email body", "tone": config["tone"]})
        except Exception as e:
            variants.append({"error": f"Error: {str(e)}", "tone": config["tone"]})
    return variants

def grade_email(email_text: str) -> Dict:
    if not email_text:
        return {
            "grade": 0,
            "uniqueness": 0,
            "flow": 0,
            "style": 0,
            "diagnostics": "Empty email"
        }

    penalties = {
        "generic_phrases": [
            r"connect\b", r"opportunity\b", r"excited\b",
            r"reach out\b", r"following up\b", r"touch base\b"
        ],
        "positive_markers": [
            r"specific\b.*\bmention", r"research\b",
            r"\?\s*$", r"your\b.*\b(work|approach|product)"
        ]
    }

    uniqueness = 10 - sum(bool(re.search(p, email_text, re.I)) for p in penalties["generic_phrases"])
    flow = 10 if len(re.split(r'[.!?]', email_text.strip())) in [3, 4] else 5
    style = sum(bool(re.search(p, email_text, re.I)) for p in penalties["positive_markers"]) * 2

    overall = max(0, min(10, (uniqueness + flow + style) // 3))
    diagnostics = "Too generic" if uniqueness < 5 else "Good structure" if flow >= 7 else "Needs more specifics"

    return {
        "grade": overall,
        "uniqueness": max(1, uniqueness),
        "flow": max(1, flow),
        "style": max(1, style),
        "diagnostics": diagnostics
    }

def merge_variants_with_llm(variants: List[Dict], tone: str) -> str:
    input_blocks = "\n\n".join(
        f"[Variant {i+1} - Focus: {v['focus']}] {v['email']}"
        for i, v in enumerate(variants)
    )

    prompt = f"""
        You're a cold outreach email assistant.
        
        Merge the following email snippets into a single, clean, 3-4 sentence cold email.
        
        - Maintain a {tone} tone.
        - Preserve the strongest insights or questions from each variant.
        - Focus on clarity and cohesion.
        - Avoid duplication.
        - Do NOT include greetings or sign-offs.
        
        Snippets:
        {input_blocks}
        
        Final Email:
        """

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=HEADERS,
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=30
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        return f"⚠️ Error generating final draft: {e}"
    
def tweak_email_with_feedback(email_text: str, user_feedback: str) -> str:
    if not email_text or not user_feedback:
        return email_text  # fallback to original if missing

    prompt = f"""
You are a cold email writing assistant.

Here is a draft email:
\"\"\"{email_text}\"\"\"

User's feedback:
\"\"\"{user_feedback}\"\"\"

Please revise the email to address the feedback while keeping it professional, 3–4 sentences max, and without greetings or sign-offs. Keep the tone consistent and avoid making it too generic or verbose.

Respond with only the revised email.
"""

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=HEADERS,
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=30
        )
        response.raise_for_status()
        revised = response.json()["choices"][0]["message"]["content"]
        return revised.strip()
    except Exception as e:
        return f"⚠️ Error updating email: {e}"


