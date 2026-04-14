"""
WORKER NODE - MAP PHASE
========================
Each worker container runs this script.
It waits for the Master to send a chunk of text,
then performs the MAP operation (word count),
and returns the result back to the Master.
"""

from flask import Flask, request, jsonify
import socket
import re

app = Flask(__name__)

# Get this container's own IP address
def get_my_ip():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    return ip

# ─────────────────────────────────────────
# MAP FUNCTION
# Input : a string of text (chunk)
# Output: a dictionary {word: count}
# ─────────────────────────────────────────
def map_word_count(text_chunk):
    # Lowercase everything and extract only words
    words = re.findall(r'\b[a-zA-Z]+\b', text_chunk.lower())

    word_count = {}
    for word in words:
        if word in word_count:
            word_count[word] += 1
        else:
            word_count[word] = 1

    return word_count


# ─────────────────────────────────────────
# ROUTE: Health check
# Master calls this to confirm worker is alive
# ─────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    my_ip = get_my_ip()
    print(f"[WORKER {my_ip}] Health check received ✓")
    return jsonify({
        "status": "alive",
        "worker_ip": my_ip
    })


# ─────────────────────────────────────────
# ROUTE: /map
# Master sends a text chunk here
# Worker returns word counts (Map result)
# ─────────────────────────────────────────
@app.route("/map", methods=["POST"])
def map_task():
    my_ip = get_my_ip()

    # Get the data sent by master
    data = request.get_json()

    if not data or "chunk" not in data:
        return jsonify({"error": "No chunk provided"}), 400

    chunk_id   = data.get("chunk_id", "?")
    text_chunk = data["chunk"]

    print(f"\n[WORKER {my_ip}] Received chunk #{chunk_id}")
    print(f"[WORKER {my_ip}] Chunk preview: {text_chunk[:80]}...")
    print(f"[WORKER {my_ip}] Running MAP (word count)...")

    # ── Run the MAP function ──
    result = map_word_count(text_chunk)

    print(f"[WORKER {my_ip}] MAP done → {len(result)} unique words found")

    return jsonify({
        "worker_ip" : my_ip,
        "chunk_id"  : chunk_id,
        "word_count": result
    })


# ─────────────────────────────────────────
# START SERVER
# Workers listen on port 5001
# ─────────────────────────────────────────
if __name__ == "__main__":
    my_ip = get_my_ip()
    print(f"\n{'='*45}")
    print(f"  WORKER NODE STARTED")
    print(f"  IP Address : {my_ip}")
    print(f"  Listening  : port 5001")
    print(f"  Waiting for MAP tasks from Master...")
    print(f"{'='*45}\n")
    app.run(host="0.0.0.0", port=5001, debug=False)
