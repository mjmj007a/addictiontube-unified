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
try:
    import config_v
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", config_v.OPENAI_API_KEY)
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", config_v.PINECONE_API_KEY)
    PINECONE_ENV = os.getenv("PINECONE_ENV", config_v.PINECONE_ENV)
except ImportError:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENV = os.getenv("PINECONE_ENV")

# Detailed validation for environment variables
missing_vars = []
if not OPENAI_API_KEY:
    missing_vars.append("OPENAI_API_KEY")
if not PINECONE_API_KEY:
    missing_vars.append("PINECONE_API_KEY")
if not PINECONE_ENV:
    missing_vars.append("PINECONE_ENV")
if missing_vars:
    error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
    logger.error(error_msg)
    raise EnvironmentError(error_msg)

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
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

@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    logger.info("Health check endpoint accessed")
    return jsonify({"status": "ok", "message": "AddictionTube Unified API is running"}), 200

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
        logger.error(f"OpenAI embedding failed: {str(e)}")
        return jsonify({"error": "Embedding service unavailable", "details": str(e)}), 500

    try:
        filter_dict = {"category": {"$eq": category}} if category != 'all' else {}
        total_results = index.query(
            vector=query_embedding,
            top_k=1000,
            include_values=False,
            include_metadata=False,
            namespace=content_type,
            filter=filter_dict
        )
        total = len(total_results.matches)

        top_k = min(200, size * page)
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            namespace=content_type,
            filter=filter_dict
        )
        start = (page - 1) * size
        end = min(start + size, len(results.matches))
        paginated = results.matches[start:end] if start < len(results.matches) else []

        items = []
        for m in paginated:
            item = {
                "id": m.id,
                "score": m.score,
                "title": strip_html(m.metadata.get("title", "N/A")),
                "description": strip_html(m.metadata.get("description", ""))
            }
            if content_type == 'stories':
                item['image'] = m.metadata.get("image", "")
            items.append(item)

        logger.info(f"Search completed: query='{query}', content_type='{content_type}', category='{category}', page={page}, total={total}")
        return jsonify({"results": items, "total": total})
    except Exception as e:
        logger.error(f"Pinecone query failed for {content_type}: {str(e)}")
        return jsonify({"error": "Search service unavailable", "details": str(e)}), 500

@app.route('/rag_answer_content', methods=['GET'])
@limiter.limit("30 per hour")  # 30 requests per hour per IP
def rag_answer_content():
    query = re.sub(r'[^\w\s.,!?]', '', request.args.get('q', '')).strip()
    content_type = request.args.get('content_type', '').strip()
    category = request.args.get('category', 'all').strip()
    reroll = request.args.get('reroll', '').lower().startswith('yes')

    if not query or not content_type or content_type not in ['songs', 'poems', 'stories']:
        logger.error(f"Invalid RAG request: query='{query}', content_type='{content_type}'")
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
        logger.error(f"OpenAI embedding failed: {str(e)}")
        return jsonify({"error": "Embedding service unavailable", "details": str(e)}), 500

    try:
        filter_dict = {"category": {"$eq": category}} if category != 'all' else {}
        results = index.query(
            vector=query_embedding,
            top_k=5,
            include_metadata=True,
            namespace=content_type,
            filter=filter_dict
        )

        matches = results.matches
        if reroll:
            random.shuffle(matches)

        if not matches:
            logger.warning(f"No matches found for query='{query}', content_type='{content_type}'")
            return jsonify({"error": "No relevant context found"}), 404

        encoding = tiktoken.get_encoding("cl100k_base")
        max_tokens = 16384 - 1000
        context_docs = []
        total_tokens = 0
        content_dict = {'songs': song_dict, 'poems': poem_dict, 'stories': story_dict}

        for match in matches:
            text = content_dict[content_type].get(match.id, match.metadata.get("description", ""))
            if not text:
                logger.warning(f"Match {match.id} has no text metadata in {content_type}")
                continue
            doc = strip_html(text)[:3000]
            doc_tokens = len(encoding.encode(doc))
            if total_tokens + doc_tokens <= max_tokens:
                context_docs.append(doc)
                total_tokens += doc_tokens
            else:
                break

        if not context_docs:
            logger.warning(f"No usable context data for query='{query}', content_type='{content_type}'")
            return jsonify({"error": "No usable context data found"}), 404

        context_text = "\n\n---\n\n".join(context_docs)
        system_prompt = f"You are an expert assistant for addiction recovery {content_type}."
        user_prompt = f"""Use the following {content_type} to answer the question.\n\n{context_text}\n\nQuestion: {query}\nAnswer:"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000
        )
        answer = response.choices[0].message.content
        logger.info(f"RAG answer generated for query='{query}', content_type='{content_type}'")
        return jsonify({"answer": answer})
    except Exception as e:
        logger.error(f"RAG processing failed for {content_type}: {str(e)}")
        return jsonify({"error": "RAG processing failed", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)