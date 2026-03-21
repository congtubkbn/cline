import sys, subprocess, json, time


def generate_input(trace_string, file_path):
       timestamp = time.strftime("%Y%m%d_%H%M%S")
       # Execute the user-requested rg -n -B 30 -A 50 command
       cmd = ["rg", "-n", "-B", "30", "-A", "50", trace_string, file_path]
       result = subprocess.run(cmd, capture_output=True, text=True)
       
       payload = {
           "trace_log": trace_string,
           "file_code": file_path,
           "extracted_chunk": result.stdout
       }
       
       out_path = f"process/input/query_function_{timestamp}.json"
       with open(out_path, "w", encoding="utf-8") as f:
           json.dump(payload, f, indent=4)
       print(out_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_input_json.py <trace_string> <file_path>")
        sys.exit(1)
    generate_input(sys.argv[1], sys.argv[2])
