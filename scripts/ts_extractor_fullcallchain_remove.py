import sys
import json
import os
import subprocess
from tree_sitter import Language, Parser
import tree_sitter_cpp

MAX_DEPTH = 10 # Constrained to prevent exponential explosion; adjust as needed

# Initialize Global AST Parser
CPP_LANGUAGE = Language(tree_sitter_cpp.language())
parser = Parser(CPP_LANGUAGE)

def get_ast_node(filepath: str, target_line: int) -> dict:
    """Parses a file into an AST and returns the exact enclosing function."""
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, 'rb') as f:
            source_bytes = f.read()

        tree = parser.parse(source_bytes)
        target_idx = target_line - 1 

        # O(log N) depth traversal to the target line
        def traverse_to_line(node, line):
            for child in node.children:
                if child.start_point.row <= line <= child.end_point.row:
                    return traverse_to_line(child, line)
            return node

        target_node = traverse_to_line(tree.root_node, target_idx)

        # Traverse Upwards to boundary
        current_node = target_node
        while current_node is not None:
            if current_node.type == 'function_definition':
                break
            current_node = current_node.parent

        if current_node is None:
            return None

        function_body = source_bytes[current_node.start_byte:current_node.end_byte].decode('utf-8')
        function_name = "Unknown"
        
        # Resolve Identifier
        for child in current_node.children:
            if child.type in ['function_declarator', 'declaration', 'pointer_declarator', 'reference_declarator']:
                def find_identifier(n):
                    if n.type in ['identifier', 'field_identifier']:
                        return source_bytes[n.start_byte:n.end_byte].decode('utf-8')
                    for c in n.children:
                        res = find_identifier(c)
                        if res: return res
                    return None
                
                name = find_identifier(child)
                if name:
                    function_name = name
                    break

        return {
            "name": function_name,
            "body": function_body
        }
    except Exception:
        return None

def determine_call_type(call_statement: str, target: str) -> tuple:
    """Classifies if the invocation relies on pointer/vtable abstraction."""
    if f"->{target}" in call_statement or f".{target}" in call_statement:
        return "indirect", "Resolved via interface pointer or object member"
    return "direct", "Static compilation linkage"

def trace_callers(target_func: str, current_depth: int, visited: set) -> list:
    """Recursively utilizes rg and Tree-sitter to map upstream callers."""
    if current_depth > MAX_DEPTH or target_func in visited:
        return []
        
    visited.add(target_func)
    callers = []
    
    # Track unique callers specifically for this parent at this depth level
    seen_callers_at_this_depth = set()
    
    # Optimized Lexical Search for Callers
    cmd = ["rg", "-n", f"{target_func}\\s*\\(", "-t", "c", "-t", "cpp"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if not result.stdout:
        return []

    for line in result.stdout.strip().split('\n'):
        parts = line.split(':', 2)
        
        # SAFE UNPACKING: Bypasses the UI bracket stripping bug
        if len(parts) == 3:
            file_code, line_num_str, statement = parts
            statement = statement.strip()
            
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue
                
            # Filter definitions and declarations
            if "def " in statement or statement.startswith("//"):
                continue
                
            node_data = get_ast_node(file_code, line_num)
            if not node_data or node_data.get('name') == "Unknown":
                continue
                
            caller_func_name = node_data.get('name')
            
            # Identify the caller uniquely by its file AND function name
            caller_id = f"{file_code}::{caller_func_name}"
            
            # PRE-RECURSION DEDUPLICATION: Skip if we already recorded this caller function
            # This prevents us from doing expensive, redundant recursive traces.
            if caller_id in seen_callers_at_this_depth:
                continue
                
            # Mark as seen
            seen_callers_at_this_depth.add(caller_id)
            
            call_type, res_note = determine_call_type(statement, target_func)
            
            caller_node = {
                "depth": current_depth,
                "file_code": file_code,
                "function_name": caller_func_name,
                "summary": "Pending LLM synthesis",
                "function_body": node_data.get('body'),
                "call_type": call_type,
                "call_statement": statement,
                "target_line": line_num,
                "resolution_note": res_note,
                # Now the recursive call only happens if the caller is truly unique
                "callers": trace_callers(caller_func_name, current_depth + 1, visited.copy())
            }
            
            callers.append(caller_node)
            
    return callers

def get_max_depth(nodes: list) -> int:
    """Calculates the deepest branch of the recursive tree safely."""
    if not nodes:
        return 0
    depths = []
    for node in nodes:
        depths.append(node.get("depth", 0))
        depths.append(get_max_depth(node.get("callers", [])))
    return max(depths)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage: python ts_extractor_fullcallchain.py "<trace_payload>" <output_json_path>')
        sys.exit(1)

    # SAFE UNPACKING: Eliminates sys.argv bracket indexing bug
    _, trace_payload, output_path = sys.argv
    
    print(f"Executing lexical search for '{trace_payload}'...")
    
    cmd = ["rg", "-n", trace_payload, "-t", "c", "-t", "cpp"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    payload = {
        "trace_analysis_session": {
            "trace_payload": trace_payload,
            "total_targets_found": 0 
        },
        "target_functions": []
    }
    
    if not result.stdout:
        print("No targets found.")
        sys.exit(0)
        
    lines = result.stdout.strip().split('\n')
    
    # Keep track of unique targets to prevent duplicate root processing
    seen_targets = set()
    
    for line in lines:
        parts = line.split(':', 2)
        
        # SAFE UNPACKING
        if len(parts) == 3:
            file_code, line_num_str, statement = parts
            line_num = int(line_num_str)
            
            node_data = get_ast_node(file_code, line_num)
            if not node_data:
                continue
                
            func_name = node_data.get('name')
            
            # Create a unique identifier for the target function
            target_id = f"{file_code}::{func_name}"
            
            if target_id in seen_targets:
                continue # Skip if we already mapped this exact function
                
            seen_targets.add(target_id)
            
            print(f"Mapping call chain for target: {func_name}...")
            
            callers_tree = trace_callers(func_name, 1, set())
            
            target_node = {
                "file_code": file_code,
                "target_line": line_num,
                "function_name": func_name,
                "summary": "Pending LLM synthesis",
                "function_body": node_data.get('body'),
                "max_depth_reached": get_max_depth(callers_tree),
                "callers": callers_tree
            }
            payload["target_functions"].append(target_node)

    # Update total with the actual number of unique targets processed
    payload["trace_analysis_session"]["total_targets_found"] = len(payload["target_functions"])

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        
    print(f"\nSUCCESS: Mathematical 1-to-N-to-N AST Call Chain written to {output_path}")