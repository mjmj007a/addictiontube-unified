import time
import openai
import json
from openai import OpenAI
from config_v import OPENAI_API_KEY
from tqdm import tqdm

client = OpenAI(api_key=OPENAI_API_KEY)
EMBED_MODEL = "text-embedding-ada-002"

def get_embedding(text):
    while True:
        try:
            response = client.embeddings.create(input=[text], model=EMBED_MODEL)
            return response.data[0].embedding
        except openai.RateLimitError as e:
            print("⏳ Rate limit hit. Waiting 10 seconds before retrying...")
            time.sleep(10)
        except Exception as e:
            print(f"❌ Embedding failed: {e}")
            return [0.0] * 1536

def process_records(data, key, prefix, id_counter):
    output = []
    for record in tqdm(data, desc=f"Processing {prefix.capitalize()}s"):
        text = record.get(key, "").strip()
        if not text:
            continue
        emb = get_embedding(text)
        metadata = {
            "title": record.get("title", ""),
            "type": prefix,
            "description": record.get("description", ""),
            "category_id": record.get("category_id", ""),
            "video_id": record.get("video_id", ""),
        }
        output.append({
            "id": f"{prefix}-{id_counter}",
            "values": emb,
            "metadata": metadata
        })
        id_counter += 1
    return output, id_counter

def main():
    id_counter = 0
    all_vectors = []

    with open("songs_revised_with_songs-july06.json", encoding="utf-8") as f:
        songs = json.load(f)
    vectors, id_counter = process_records(songs, "song", "song", id_counter)
    all_vectors.extend(vectors)

    with open("videos_revised_with_poems-july04.json", encoding="utf-8") as f:
        poems = json.load(f)
    vectors, id_counter = process_records(poems, "poem", "poem", id_counter)
    all_vectors.extend(vectors)

    with open("stories2.json", encoding="utf-8") as f:
        stories = json.load(f)

    for s in tqdm(stories, desc="Processing Stories"):
        if not s.get("text"):
            continue
        emb = get_embedding(s["text"])
        all_vectors.append({
            "id": f"story-{id_counter}",
            "values": emb,
            "metadata": {
                "title": s.get("title", ""),
                "type": "story",
                "description": s.get("description", ""),
                "category": s.get("category", ""),
                "id": s.get("id", "")
            }
        })
        id_counter += 1

    with open("unified_records_with_embeddings.json", "w", encoding="utf-8") as f:
        json.dump(all_vectors, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(all_vectors)} vectors to unified_records_with_embeddings.json")

if __name__ == "__main__":
    main()
