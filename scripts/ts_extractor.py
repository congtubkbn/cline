import sys
import json
import os
from tree_sitter import Language, Parser
import tree_sitter_cpp

def extract_function_bounds(filepath: str, target_line: int) -> dict:
    if not os.path.exists(filepath):
        return {"error": f"File {filepath} not found."}

    # 1. Initialize Tree-sitter Parser for C/C++
    CPP_LANGUAGE = Language(tree_sitter_cpp.language())
    parser = Parser(CPP_LANGUAGE)

    with open(filepath, 'rb') as f:
        source_bytes = f.read()

    # 2. Parse the code into an AST
    tree = parser.parse(source_bytes)
    root_node = tree.root_node

    # Tree-sitter line arrays are 0-indexed
    target_idx = target_line - 1 

    # 3. Locate the deepest node intersecting the target line
    # (Using Tree-sitter's built-in traversal instead of a custom Python loop)
    target_node = root_node.named_descendant_for_point_range(
        (target_idx, 0), (target_idx, 10000) # Assume lines are < 10000 chars wide
    )

    if target_node is None:
        target_node = root_node

    # 4. Traverse Upwards to locate the enclosing structural boundary
    current_node = target_node
    while current_node is not None:
        if current_node.type == 'function_definition':
            break
        current_node = current_node.parent

    if current_node is None:
        return {
            "file_code": filepath,
            "line_number": target_line,
            "error": "The specified line is not enclosed within a recognizable function definition."
        }

    # 5. Extract Complete Function Body
    function_body = source_bytes[current_node.start_byte:current_node.end_byte].decode('utf-8')

    # 6. Resolve Function Name (Identifier Extraction)
    function_name = "Unknown"
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
        "file_code": filepath,
        "line_number": target_line,
        "function_name": function_name,
        "function_bodies": function_body
    }

if __name__ == "__main__":
    # Validate argument length (supports 2 or 3 arguments)
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python ts_extractor.py <filepath> <line_number> [output_json_path]")
        sys.exit(1)

    file_arg = sys.argv[1]
    
    try:
        line_arg = int(sys.argv[2])
    except ValueError:
        print("Error: line_number must be an integer.")
        sys.exit(1)
        
    # Execute Extraction
    result = extract_function_bounds(file_arg, line_arg)
    
    # Handle File Output vs Stdout
    if len(sys.argv) == 4:
        output_path = sys.argv[3]
        # Ensure the target directory architecture exists
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4)
            
        print(f"SUCCESS: AST data serialized to {output_path}")
    else:
        print(json.dumps(result, indent=4))