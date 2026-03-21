import clang.cindex
import sys
import os
import json

# ==============================================================================
# IMPROVED AST ANALYZER
# ==============================================================================
clang.cindex.Config.set_library_path('C:\\Program Files\\LLVM\\bin')

def get_callers_exact(target_func_name, search_dir):
    index = clang.cindex.Index.create()
    callers = []
    
    # We use a set to avoid duplicate parent functions from the same file
    seen_callers = set()

    for root, _, files in os.walk(search_dir):
        for file in files:
            if file.endswith(('.c', '.cpp', '.cc', '.h', '.hpp')):
                filepath = os.path.join(root, file)
                # Parse the file into an AST
                tu = index.parse(filepath, args=['-x', 'c++', '-std=c++17'])
                
                # Traverse the AST looking for Call Expressions
                for node in tu.cursor.walk_preorder():
                    # Check if this node is a function call
                    if node.kind in [clang.cindex.CursorKind.CALL_EXPR, 
                                    clang.cindex.CursorKind.MEMBER_REF_EXPR]:
                        
                        # Verify the name matches your target
                        if node.spelling == target_func_name:
                            # Find the function that contains this call
                            parent = get_parent_function(node)
                            if parent and parent.spelling != target_func_name:
                                caller_id = f"{filepath}:{parent.spelling}"
                                if caller_id not in seen_callers:
                                    seen_callers.add(caller_id)
                                    callers.append({
                                        "caller": parent.spelling,
                                        "file": filepath,
                                        "line": node.location.line
                                    })
     #print(callers)                               
    return callers

def get_parent_function(node):
    """Recursively climb the AST to find the function declaration containing this node."""
    p = node.semantic_parent
    while p:
        if p.kind in [clang.cindex.CursorKind.FUNCTION_DECL, 
                      clang.cindex.CursorKind.CXX_METHOD, 
                      clang.cindex.CursorKind.CONSTRUCTOR]:
            return p
        p = p.semantic_parent
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing target function name"}))
        sys.exit(1)
    
    target = sys.argv[1]
    directory = sys.argv[2] if len(sys.argv) > 2 else "."
    results = get_callers_exact(target, directory)
    # Structured output for Cline to parse easily
    print(json.dumps(results, indent=2))