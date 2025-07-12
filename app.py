from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pinecone import Pinecone
from openai import OpenAI, APIError
import os
import re
import json
import logging
from logging.handlers import RotatingFileHandler
from bs4 import BeautifulSoup
import tiktoken
import random

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://addictiontube.com", "http://addictiontube.com"]}})

# Configure logging
logger = logging.getLogger('addictiontube')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('unified_search.log', maxBytes=10485760, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
logger.addHandler(handler)

# Initialize Flask-Limiter with in-memory storage
limiter = Limiter(
    app=app,
    key_func=get_remote_address,  # Rate limit by client IP
    default_limits=["200 per day", "50 per hour"],  # Global limits
    storage_uri="memory://",  # In-memory storage for simplicity
    headers_enabled=True,  # Include rate limit headers in responses
)

# Initialize clients
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("addictiontube-unified")

# Load metadata for RAG context
with open('songs_revised_with_songs-july06.json', 'r', encoding='utf-8') as f:
    song_dict = {item['video_id']: item['song'] for item in json.load(f)}
with open('videos_revised_with_poems-july04.json', 'r', encoding='utf-8') as f:
    poem_dict = {item['video_id']: item['poem'] for item in json.load(f)}
with open('stories.json', 'r', encoding='utf-8') as f:
    story_dict = {item['id']: item['text'] for item in json.load(f)}

def strip_html(text):
    return re.sub(r'<[^>]+>', '', text or '') if text else ''

@app.errorhandler(429)
def ratelimit_handler(e):
    logger.warning(f"Rate limit exceeded: {e.description}")
    return jsonify({
        "error": "Rate limit exceeded",
        "details": f"Too many requests. Please wait and try again. Limit: {e.description}"
    }), 429

@app.route('/search_content', methods=['GET'])
@limiter.limit("60 per hour")  # 60 requests per hour per IP
def search_content():
    query = re.sub(r'[^\w\s.,!?]', '', request.args.get('q', '')).strip()
    content_type = request.args.get('content_type', '').strip()
    category = request.args.get('category', 'all').strip()
    page = max(1, int(request.args.get('page', 1)))
    size = max(1, min(100, int(request.args.get('per_page', 5))))

    if not query or not content_type or content_type not in ['songs', 'poems', 'stories']:
        logger.error(f"Invalid request: query='{query}', content_type='{content_type}'")
        return jsonify({"error": "Invalid or missing query or content type"}), 400

    valid_categories = {
        'songs': ['1074'],
        'poems': ['1082'],
        'stories': ['1028', '1042']
    }
    if category != 'all' and category not in valid_categories[content_type]:
        logger.error(f"Invalid category: '{category}' for content_type='{content_type}'")
        return jsonify({"error": "Invalid category for selected content type"}), 400

    try:
        embedding_response = client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        query_embedding = embedding_response.data[0].embedding
    except APIError as e:
        logger.error(f"OpenAI embedding failed: {