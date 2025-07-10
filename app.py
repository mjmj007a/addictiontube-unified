from flask import Flask, request, jsonify
from openai import OpenAI, APIError
from pinecone import Pinecone
from flask_cors import CORS
import os, json, tiktoken
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
index = pc.Index("addictiontube-unified")  # Make sure this is your unified index

def strip_html(text):
    return BeautifulSoup(text or "", "html.parser").get_text()

@app.route('/search', methods=['GET'])
def unified_search():
    query = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', '').strip()
    page = max(1, int(request.args.get('page', 1)))
    size = max(1, int(request.args.get('per_page', 5)))

    if not category_id or not query:
        return jsonify({"error": "Missing query or category_id"}), 400

    try:
        embedding_response = client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        query_embedding = embedding_response.data[0].embedding
    except APIError as e:
        return jsonify({"error": "OpenAI embedding failed", "details": str(e)}), 500

    try:
        top_k = max(200, size * page)
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter={"category_id": {"$eq": category_id}}
        )
        matches = results.matches
        start = (page - 1) * size
        end = min(start + size, len(matches))
        paginated = matches[start:end]

        items = [{
            "id": m.id,
            "score": m.score,
            "title": m.metadata.get("title", "N/A"),
            "description": m.metadata.get("description", ""),
            "category_id": m.metadata.get("category_id", "")
        } for m in paginated]

        return jsonify({"results": items, "total": len(matches)})
    except Exception as e:
        return jsonify({"error": "Pinecone query failed", "details": str(e)}), 500

@app.route('/rag_answer', methods=['GET'])
def unified_rag():
    query = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', '').strip()

    if not query or not category_id:
        return jsonify({"error": "Missing query or category_id"}), 400

    try:
        embedding_response = client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        query_embedding = embedding_response.data[0].embedding
    except APIError as e:
        return jsonify({"error": "OpenAI embedding failed", "details": str(e)}), 500

    try:
        results = index.query(
            vector=query_embedding,
            top_k=5,
            include_metadata=True,
            filter={"category_id": {"$eq": category_id}}
        )
        context_docs = [strip_html(m.metadata.get("description", ""))[:3000] for m in results.matches]
        encoding = tiktoken.encoding_for_model("gpt-4")
        total_tokens = sum(len(encoding.encode(doc)) for doc in context_docs)
        if total_tokens > 4000:
            context_docs = context_docs[:1]

        context_text = "\n\n".join(context_docs)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"You are an assistant answering questions about {category_id}s."},
                {"role": "user", "content": f"{context_text}\n\nQuestion: {query}\nAnswer:"}
            ]
        )
        answer = response.choices[0].message.content
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": "RAG processing failed", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
