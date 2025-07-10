import os
import json
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

pc = Pinecone(api_key=pinecone_api_key)
index = pc.Index(pinecone_index_name)

with open("unified_records_with_embeddings.json", "r", encoding="utf-8") as f:
    all_vectors = json.load(f)

filtered_vectors = []
skipped_items = []

for item in all_vectors:
    embedding = item.get("values")  # FIXED HERE
    if embedding and any(x != 0.0 for x in embedding):
        filtered_vectors.append({
            "id": item["id"],
            "values": embedding,
            "metadata": item.get("metadata", {})
        })
    else:
        skipped_items.append(item["id"])

if skipped_items:
    print(f"⚠️ Skipped {len(skipped_items)} items (missing or zero embedding):")
    for _id in skipped_items:
        print(f" - {_id}")

print(f"📤 Uploading {len(filtered_vectors)} valid vectors to Pinecone...")
index.upsert(vectors=filtered_vectors)
print("✅ Upload completed.")


