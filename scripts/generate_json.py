import os
import json

def generate_compile_commands():
    # Your specific directory
    base_dir = r"D:\4 5G Study\VSC"
    compile_commands = []
    
    # Walk through the directory to find all C and C++ files
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.c') or file.endswith('.cpp'):
                # Get the absolute path to the file
                full_file_path = os.path.join(root, file)
                
                # Convert backslashes to forward slashes for cross-platform safety in JSON
                safe_base_dir = base_dir.replace('\\', '/')
                safe_file_path = full_file_path.replace('\\', '/')
                
                # Assign the correct compiler based on the file extension
                if file.endswith('.c'):
                    command = f'gcc -c "{safe_file_path}" -I"{safe_base_dir}"'
                else:
                    command = f'g++ -std=c++17 -c "{safe_file_path}" -I"{safe_base_dir}"'
                    
                # Build the JSON object
                entry = {
                    "directory": safe_base_dir,
                    "command": command,
                    "file": safe_file_path
                }
                compile_commands.append(entry)
                
    # Define where to save the compile_commands.json
    output_path = os.path.join(base_dir, "compile_commands.json")
    
    # Write the JSON data to the file
    with open(output_path, 'w') as f:
        json.dump(compile_commands, f, indent=4)
        
    print(f"Success! Generated compile_commands.json with {len(compile_commands)} files.")
    print(f"Saved to: {output_path}")

if __name__ == "__main__":
    generate_compile_commands()