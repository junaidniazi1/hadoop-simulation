"""
MASTER NODE - CHUNK + REDUCE PHASE
=====================================
The Master node does 3 things:
  1. READ & CHUNK  → Reads dataset.csv, splits rows across workers
  2. MAP DISPATCH  → Sends each chunk to a worker via HTTP POST /map
  3. REDUCE        → Collects all word counts, merges into final result
"""

from flask import Flask, jsonify
import requests
import csv
import time
import json

app = Flask(__name__)

# ─────────────────────────────────────────
# WORKER CONFIGURATION
# Static IPs assigned in docker-compose.yml
# ─────────────────────────────────────────
WORKERS = [
    {"id": 1, "ip": "172.20.0.3", "port": 5001},
    {"id": 2, "ip": "172.20.0.4", "port": 5001},
    {"id": 3, "ip": "172.20.0.5", "port": 5001},
]

CSV_FILE = "/data/dataset.csv"


# ─────────────────────────────────────────
# STEP 1: READ CSV AND EXTRACT TEXT
# Reads every row's 'review' column into a list
# ─────────────────────────────────────────
def read_csv(filepath):
    print(f"\n[MASTER] Reading CSV file: {filepath}")
    rows = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # We process the 'review' column as text
            rows.append(str(row.get('Country/Region', '')) + ' ' + str(row.get('WHO Region', '')))
    print(f"[MASTER] Total rows loaded: {len(rows)}")
    return rows


# ─────────────────────────────────────────
# STEP 2: SPLIT ROWS INTO CHUNKS
# Divides rows evenly among available workers
# ─────────────────────────────────────────
def split_into_chunks(rows, num_workers):
    chunks = []
    chunk_size = max(1, len(rows) // num_workers)

    for i in range(num_workers):
        start = i * chunk_size
        # Last worker gets any remaining rows
        end = start + chunk_size if i < num_workers - 1 else len(rows)
        chunk_text = " ".join(rows[start:end])
        chunks.append(chunk_text)
        print(f"[MASTER] Chunk #{i+1} → rows {start+1} to {end} ({end-start} rows)")

    return chunks


# ─────────────────────────────────────────
# STEP 3: CHECK WORKER HEALTH
# Ping each worker before sending data
# ─────────────────────────────────────────
def check_workers():
    alive = []
    print("\n[MASTER] Checking worker health...")
    for worker in WORKERS:
        url = f"http://{worker['ip']}:{worker['port']}/health"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print(f"[MASTER] Worker {worker['id']} ({worker['ip']}) → ✅ ALIVE")
                alive.append(worker)
            else:
                print(f"[MASTER] Worker {worker['id']} ({worker['ip']}) → ❌ NOT OK")
        except Exception as e:
            print(f"[MASTER] Worker {worker['id']} ({worker['ip']}) → ❌ UNREACHABLE ({e})")
    return alive


# ─────────────────────────────────────────
# STEP 4: SEND CHUNKS TO WORKERS (MAP)
# Each worker gets one chunk via POST /map
# ─────────────────────────────────────────
def dispatch_to_workers(alive_workers, chunks):
    results = []
    print(f"\n[MASTER] Dispatching {len(chunks)} chunks to {len(alive_workers)} workers...")

    for i, worker in enumerate(alive_workers):
        if i >= len(chunks):
            break

        url = f"http://{worker['ip']}:{worker['port']}/map"
        payload = {
            "chunk_id": i + 1,
            "chunk": chunks[i]
        }

        try:
            print(f"[MASTER] Sending chunk #{i+1} to Worker {worker['id']} ({worker['ip']})...")
            resp = requests.post(url, json=payload, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                results.append(data)
                print(f"[MASTER] ✅ Worker {worker['id']} returned {len(data['word_count'])} unique words")
            else:
                print(f"[MASTER] ❌ Worker {worker['id']} returned error: {resp.status_code}")

        except Exception as e:
            print(f"[MASTER] ❌ Failed to contact Worker {worker['id']}: {e}")

    return results


# ─────────────────────────────────────────
# STEP 5: REDUCE PHASE
# Merge all worker word counts into one dict
# ─────────────────────────────────────────
def reduce_results(worker_results):
    print(f"\n[MASTER] Running REDUCE phase...")
    final_count = {}

    for result in worker_results:
        worker_ip  = result.get("worker_ip", "unknown")
        chunk_id   = result.get("chunk_id", "?")
        word_count = result.get("word_count", {})

        print(f"[MASTER] Merging results from Worker (chunk #{chunk_id}, IP: {worker_ip})...")

        for word, count in word_count.items():
            if word in final_count:
                final_count[word] += count
            else:
                final_count[word] = count

    # Sort by frequency descending
    sorted_count = dict(sorted(final_count.items(), key=lambda x: x[1], reverse=True))
    print(f"[MASTER] REDUCE complete → {len(sorted_count)} total unique words")
    return sorted_count


# ─────────────────────────────────────────
# ROUTE: /run
# Triggers the full MapReduce pipeline
# Visit http://localhost:5000/run to start
# ─────────────────────────────────────────
@app.route("/run", methods=["GET"])
def run_mapreduce():
    print("\n" + "="*50)
    print("  MAPREDUCE JOB STARTED")
    print("="*50)

    start_time = time.time()

    # 1. Read CSV
    rows = read_csv(CSV_FILE)

    # 2. Check which workers are alive
    alive_workers = check_workers()
    if not alive_workers:
        return jsonify({"error": "No workers available!"}), 503

    # 3. Split data into chunks
    chunks = split_into_chunks(rows, len(alive_workers))

    # 4. Send chunks to workers (MAP phase)
    worker_results = dispatch_to_workers(alive_workers, chunks)

    # 5. Combine results (REDUCE phase)
    final_result = reduce_results(worker_results)

    elapsed = round(time.time() - start_time, 2)

    # Top 20 most frequent words
    top_20 = dict(list(final_result.items())[:20])

    print(f"\n[MASTER] ✅ JOB COMPLETE in {elapsed}s")
    print(f"[MASTER] Top 10 words: { {k: final_result[k] for k in list(final_result)[:10]} }")

    # Save full result to file
    with open("/data/output.json", "w") as f:
        json.dump(final_result, f, indent=2)
    print("[MASTER] Full results saved to /data/output.json")

    return jsonify({
        "status"         : "success",
        "elapsed_seconds": elapsed,
        "total_unique_words": len(final_result),
        "workers_used"   : len(alive_workers),
        "top_20_words"   : top_20,
        "full_results_saved_to": "/data/output.json"
    })


# ─────────────────────────────────────────
# ROUTE: /results
# View saved output from last run
# ─────────────────────────────────────────
@app.route("/results", methods=["GET"])
def view_results():
    try:
        with open("/data/output.json", "r") as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "No results yet. Please run /run first."}), 404


# ─────────────────────────────────────────
# ROUTE: /health
# ─────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "Master node is running"})


# ─────────────────────────────────────────
# START MASTER SERVER
# ─────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  MASTER NODE STARTED")
    print(f"  IP Address  : 172.20.0.2")
    print(f"  Port        : 5000")
    print(f"  Workers     : {[w['ip'] for w in WORKERS]}")
    print(f"  To start job: GET http://localhost:5000/run")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
