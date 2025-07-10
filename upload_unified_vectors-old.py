import json
from pinecone import Pinecone, ServerlessSpec
from config_v import PINECONE_API_KEY, PINECONE_ENV

# Initialize Pinecone instance
pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "addictiontube-unified"

# Create the index if it doesn't exist
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",              # your environment is AWS
            region=PINECONE_ENV       # "us-east-1"
        )
    )

# Connect to the index
index = pc.Index(index_name)

# Load unified records
with open("unified_records_with_embeddings.json", "r", encoding="utf-8") as f:
    records = json.load(f)

# Upload in batches of 100
batch_size = 100
for i in range(0, len(records), batch_size):
    batch = records[i:i + batch_size]
    vectors = [(r["id"], r["values"], r["metadata"]) for r in batch]
    index.upsert(vectors)

print(f"✅ Uploaded {len(records)} records to {index_name}")
