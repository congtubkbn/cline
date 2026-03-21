import sys, subprocess, json, time, os

def execute_heuristic_extraction(trace_log: str, file_path: str):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    os.makedirs(os.path.join("process", "input"), exist_ok=True)
    
    # Execute the heuristic chunking
    cmd = ["rg", "-n", "-B", "30", "-A", "50", trace_log, file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    payload = {
        "trace_log": trace_log,
        "file_code": file_path,
        "extracted_chunk": result.stdout
    }
    
    out_path = os.path.join("process", "input", f"query_function_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
        
    print(out_path) # Output for the LLM to read

if __name__ == "__main__":
    execute_heuristic_extraction(sys.argv[7], sys.argv[8])