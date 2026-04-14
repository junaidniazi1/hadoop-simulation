"""
app.py — LOCAL TEST SCRIPT
============================
Run this on your own machine (outside Docker)
to trigger the MapReduce job and display results.

Requirements: pip install requests
Usage       : python app.py
"""

import requests
import json
import time

MASTER_URL = "http://localhost:5000"

def print_banner():
    print("\n" + "="*55)
    print("   HADOOP SIMULATION — MapReduce Test Client")
    print("="*55)

def check_master():
    print("\n[1] Checking Master node health...")
    try:
        resp = requests.get(f"{MASTER_URL}/health", timeout=5)
        if resp.status_code == 200:
            print("    ✅ Master node is RUNNING")
            return True
        else:
            print("    ❌ Master node returned error")
            return False
    except Exception as e:
        print(f"    ❌ Cannot reach Master: {e}")
        print("    → Make sure you ran: docker-compose up")
        return False

def run_job():
    print("\n[2] Triggering MapReduce job...")
    print("    Sending request to http://localhost:5000/run")
    try:
        start = time.time()
        resp = requests.get(f"{MASTER_URL}/run", timeout=60)
        elapsed = round(time.time() - start, 2)

        if resp.status_code == 200:
            data = resp.json()
            print(f"    ✅ Job completed in {elapsed} seconds!")
            return data
        else:
            print(f"    ❌ Job failed: {resp.status_code}")
            print(f"    {resp.text}")
            return None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None

def display_results(data):
    if not data:
        return

    print("\n" + "="*55)
    print("   MAPREDUCE RESULTS")
    print("="*55)
    print(f"   Status          : {data.get('status', 'unknown')}")
    print(f"   Workers Used    : {data.get('workers_used', '?')}")
    print(f"   Total Unique Words: {data.get('total_unique_words', '?')}")
    print(f"   Time Taken      : {data.get('elapsed_seconds', '?')} seconds")

    print("\n" + "-"*55)
    print("   TOP 20 MOST FREQUENT WORDS (Reduce Output)")
    print("-"*55)

    top_20 = data.get("top_20_words", {})
    if top_20:
        rank = 1
        for word, count in top_20.items():
            bar = "█" * min(count, 40)
            print(f"   {rank:>2}. {word:<20} {count:>4}  {bar}")
            rank += 1
    else:
        print("   No results found.")

    print("\n" + "="*55)
    print("   Full results saved to: data/output.json (inside container)")
    print("="*55 + "\n")

def save_results_locally(data):
    if not data:
        return
    with open("mapreduce_output.json", "w") as f:
        json.dump(data, f, indent=2)
    print("   💾 Results also saved locally to: mapreduce_output.json")

def main():
    print_banner()

    # Step 1: Check master is alive
    if not check_master():
        print("\n⚠️  Please run 'docker-compose up' first, then try again.\n")
        return

    # Step 2: Run the MapReduce job
    result = run_job()

    # Step 3: Display results nicely
    display_results(result)

    # Step 4: Save results locally
    save_results_locally(result)

if __name__ == "__main__":
    main()