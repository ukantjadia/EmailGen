from flask import Blueprint, jsonify, request
from app.full_pipeline import run_pipeline
from app.utils.config import JSON_FILE, EMBEDDINGS_PATH

main_bp = Blueprint("main", __name__)

@main_bp.route("/", methods=["GET"])
def index():
    return jsonify({"message": "EmailGen API is live!"})

@main_bp.route("/generate", methods=["POST"])
def generate():
    """
    Expects JSON payload:
    {
        "company_name": "...",           # required
        "website_url": "...",            # optional
        "api_key": "sk-..."              # optional, for DeepSeek
    }
    """
    try:
        data = request.get_json()
        company_name = data.get("company_name")
        website_url = data.get("website_url")
        api_key = data.get("api_key", "sk-")
        if not company_name:
            return jsonify({"status": "error", "message": "company_name is required"}), 400
        result = run_pipeline(company_name, JSON_FILE, EMBEDDINGS_PATH, website_url=website_url, api_key=api_key)
        return jsonify({"status": "success", "email": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
