import clang.cindex
import sys
import os
import re
# ==============================================================================
# CONFIGURATION
# Uncomment and set this if Python cannot automatically find your libclang!
# Linux example:   clang.cindex.Config.set_library_file('/usr/lib/llvm-14/lib/libclang.so')
# macOS example:   clang.cindex.Config.set_library_file('/opt/homebrew/opt/llvm/lib/libclang.dylib')
clang.cindex.Config.set_library_path('C:\\Program Files\\LLVM\\bin')
# ==============================================================================

def find_keyword_fast(keyword, search_dir):
    """Phase 1: Fast text search to find candidate files and line numbers."""
    locations = []
    valid_exts = ('.c', '.cpp', '.h', '.hpp')
    
    # 1. Compile the regex pattern once using word boundaries (\b)
    # 2. re.escape ensures special characters in the keyword are treated as raw text
    pattern = re.compile(r'\b' + re.escape(keyword) + r'\b')
    
    for root, _, files in os.walk(search_dir):
        for file in files:
            if file.endswith(valid_exts):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            # 3. Use regex search instead of the 'in' operator
                            if pattern.search(line):
                                locations.append((filepath, i + 1))
                except UnicodeDecodeError:
                    pass # Skip binaries or unreadable files
    return locations

def is_active_code(tu, filepath, line_number, keyword):
    """Phase 2: Uses Clang Tokenizer to ensure the keyword is an active code token."""
    file_obj = tu.get_file(filepath)
    
    # FIX: Start tokenizing from Line 1 instead of the target line.
    # This guarantees the lexer sees any '/*' that opened on previous lines.
    start_loc = clang.cindex.SourceLocation.from_position(tu, file_obj, 1, 1)
    end_loc = clang.cindex.SourceLocation.from_position(tu, file_obj, line_number, 10000)
    
    extent = clang.cindex.SourceRange.from_locations(start_loc, end_loc)
    
    # Extract all tokens from the start of the file up to the target line
    tokens = tu.get_tokens(extent=extent)
    
    for token in tokens:
        # We only care about matching tokens that physically reside on our target line
        if token.location.line == line_number:
            if token.spelling == keyword and token.kind != clang.cindex.TokenKind.COMMENT:
                return True 
                
    # If we finish the loop without returning True, the keyword was hidden 
    # inside a multiline comment or string literal.
    return False

def get_enclosing_function(cursor, target_line):
    """Phase 3: Recursively traverse the AST to find the function boundaries."""
    # Check if current node is a function or method
    if cursor.kind in (clang.cindex.CursorKind.FUNCTION_DECL, clang.cindex.CursorKind.CXX_METHOD):
        if cursor.extent.start.line <= target_line <= cursor.extent.end.line:
            return cursor
            
    # Search children
    for child in cursor.get_children():
        result = get_enclosing_function(child, target_line)
        if result:
            return result
    return None

def extract_macros_from_file(filepath):
    """Scans the file for preprocessor macros to ensure AST includes them."""
    macros = set()
    
    # Matches: #ifdef FEATURE or #ifndef FEATURE
    ifdef_pattern = re.compile(r'^\s*#\s*(?:ifdef|ifndef)\s+([A-Za-z0-9_]+)')
    
    # Matches: defined(FEATURE) or defined FEATURE
    defined_pattern = re.compile(r'defined\s*\(?\s*([A-Za-z0-9_]+)\s*\)?')

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                # Quick skip for lines that aren't preprocessor directives
                if not line.lstrip().startswith('#'):
                    continue

                # Check for #ifdef / #ifndef
                m1 = ifdef_pattern.search(line)
                if m1:
                    macros.add(m1.group(1))

                # Check for #if / #elif defined(...)
                if '#if' in line or '#elif' in line:
                    for match in defined_pattern.finditer(line):
                        macros.add(match.group(1))
    except Exception as e:
        print(f"[DEBUG] Warning: Failed to read macros from {filepath}: {e}")
        
    return macros

def analyze_and_extract(keyword, search_dir):
    locations = find_keyword_fast(keyword, search_dir)
    if not locations:
        print(f"Keyword '{keyword}' not found in any source files.")
        return

    print(f"Found {len(locations)} raw occurrence(s). Booting Clang analyzer...\n")
    
    index = clang.cindex.Index.create()
    processed_functions = set() # Prevent printing the same function multiple times
    
    for filepath, line_number in locations:
        # Load compilation database for accurate macro resolution
        compdb_dir = os.path.dirname(os.path.abspath(filepath))
        args = ['-x', 'c++']
        try:
            # Look up the directory tree for compile_commands.json
            while not os.path.exists(os.path.join(compdb_dir, 'compile_commands.json')):
                parent_dir = os.path.dirname(compdb_dir)
                if parent_dir == compdb_dir:  # We have reached the root (e.g., '/' or 'C:\')
                    break
                compdb_dir = parent_dir
            compdb = clang.cindex.CompilationDatabase.fromDirectory(compdb_dir)
            compile_cmds = compdb.getCompileCommands(filepath)
            if compile_cmds:
                args = list(compile_cmds[0].arguments)[1:-1]
                    
        except Exception:
            print(f"\n[DEBUG] Warning: Failed to load or parse compile_commands.json for {filepath}")

        
        detected_macros = extract_macros_from_file(filepath)
        for macro in detected_macros:
            macro_flag = f"-D{macro}"
            if macro_flag not in args:
                args.insert(0, macro_flag)
                
        # Parse the file into an AST
        tu = index.parse(filepath, args=args)
        
        # Filter out comments
        if not is_active_code(tu, filepath, line_number, keyword):
            continue

        # Find the function
        func_cursor = get_enclosing_function(tu.cursor, line_number)
        
        if func_cursor:
            func_name = func_cursor.spelling
            start_line = func_cursor.extent.start.line
            end_line = func_cursor.extent.end.line
            
            unique_key = f"{filepath}::{func_name}"
            
            if unique_key not in processed_functions:
                processed_functions.add(unique_key)
                
                print(f"### Location: `{filepath}` (Line {line_number})")
                print(f"### Function: `{func_name}`")
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    body = "".join(lines[start_line-1:end_line])
                    #print(body.strip())
                    print("\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trace_analyzer.py <keyword>")
        sys.exit(1)
        
    target_keyword = sys.argv[1]
    target_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    
    analyze_and_extract(target_keyword, target_dir)