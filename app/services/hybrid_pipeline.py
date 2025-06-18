import json
from groq import Groq  # Requires `pip install groq`
from app.services.prompt_template import get_template
from app.services.retrieve_email import extract_company_text, retrieve_similar_email
import os
from dotenv import load_dotenv
from app.utils.config import JSON_FILE, EMBEDDINGS_PATH

load_dotenv()

client = Groq(api_key="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")

def generate_email(company_data_path=JSON_FILE, embeddings_path=EMBEDDINGS_PATH):
    with open(company_data_path, "r", encoding="utf-8") as f:
        company_data = json.load(f)

    template = get_template()
    source_text = extract_company_text(company_data)
    similar_email = retrieve_similar_email(source_text, embeddings_path)

    company_name = company_data.get("company_name", "Unknown")

    system_prompt = """You are an expert email writer. Your task is to adapt the PROVIDED TEMPLATE EMAIL to fit a new company while maintaining the EXACT SAME structure, tone, and format.

CRITICAL INSTRUCTIONS:
1. Use the retrieved email as your PRIMARY TEMPLATE - keep the same structure, paragraph breaks, and flow
2. Only replace company-specific details with information about the target company
3. Maintain the same conversational tone and personal touch
4. Keep the same email length and format
5. Do NOT add new sections or significantly change the structure
6. Make minimal enhancements - only improve clarity or fix obvious errors
7. Generate an appropriate email subject line
8. CRITICAL: End with a compelling, personal call-to-action that follows these patterns:
   - "I'd love to [connect/hear more/discuss] [specific topic] when you have a moment"
   - "Would you be up for a conversation next week?"
   - "I'd love to connect more and discuss [topic]. Would you be free next week?"
   - "I'd love to hear more about [company/topic] if you are available for a quick chat"
9. Do NOT include "Best regards" or formal signatures
10. Output ONLY the subject line and email content - no explanations or notes"""

    user_prompt = f"""COMPANY TO TARGET: {company_name}

COMPANY INFORMATION:
{source_text}

TEMPLATE EMAIL TO ADAPT:
{similar_email}

TASK: Adapt the template email above to target {company_name}.
- Keep the EXACT same structure and format
- Replace company-specific details with relevant information about {company_name}
- Maintain the same tone and personal style
- Keep the same paragraph structure and flow
- Generate an engaging subject line for the email
- END with a personal, enthusiastic call-to-action using patterns like:
  * "I'd love to connect and swap stories about [topic] when you have a moment"
  * "I'd love to hear more about [specific company aspect]. Would you be up for a conversation next week?"
  * "Would you be free for a quick chat next week to discuss [topic]?"
- Focus on different aspects of the company information each time for variety
- Only make minimal improvements for clarity

Output format:
Subject: [your subject line]

[email content only - no explanations]"""

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.4,
        top_p=0.9
    )

    result = response.choices[0].message.content.strip()

    with open("final_email.txt", "w", encoding="utf-8") as f:
        f.write(result)

    print("✅ Generated email saved to final_email.txt")

    return {
        "company": company_name,
        "subject": result.splitlines()[0].replace("Subject: ", "").strip(),
        "email": "\n".join(result.splitlines()[1:]).strip()
    }

if __name__ == "__main__":
    generate_email()
