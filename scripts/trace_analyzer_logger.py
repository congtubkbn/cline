import clang.cindex
import sys
import os
import re
import logging
from datetime import datetime

# ==============================================================================
# CONFIGURATION
# ==============================================================================
clang.cindex.Config.set_library_path('C:\\Program Files\\LLVM\\bin')

def setup_logger(script_path):
    """Sets up the logging configuration to write to both console and a timestamped file."""
    # Extract the script name (e.g., trace_analyzer.py)
    script_name = os.path.basename(script_path)
    
    # Define the log directory
    log_dir = os.path.join("process", "log")
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate timestamp and final log file path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{timestamp}_{script_name}.txt"
    log_filepath = os.path.join(log_dir, log_filename)
    
    # Configure the logger
    logging.basicConfig(
        level=logging.DEBUG, # Set base logging level
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Logging initialized. Saving logs to: {log_filepath}")

def find_keyword_fast(keyword, search_dir):
    """Phase 1: Fast text search to find candidate files and line numbers."""
    locations = []
    valid_exts = ('.c', '.cpp', '.h', '.hpp')
    
    pattern = re.compile(r'\b' + re.escape(keyword) + r'\b')
    
    for root, _, files in os.walk(search_dir):
        for file in files:
            if file.endswith(valid_exts):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if pattern.search(line):
                                locations.append((filepath, i + 1))
                                logging.debug(f"Candidate match found for '{keyword}' at {filepath}:{i + 1}")
                except UnicodeDecodeError:
                    logging.warning(f"Warning: Skipping binary or unreadable file: for {filepath}")
    return locations

def is_active_code(tu, filepath, line_number, keyword):
    """Phase 2: Uses Clang Tokenizer to ensure the keyword is an active code token."""
    file_obj = tu.get_file(filepath)
    
    start_loc = clang.cindex.SourceLocation.from_position(tu, file_obj, 1, 1)
    end_loc = clang.cindex.SourceLocation.from_position(tu, file_obj, line_number, 10000)
    
    extent = clang.cindex.SourceRange.from_locations(start_loc, end_loc)
    
    tokens = tu.get_tokens(extent=extent)
    
    for token in tokens:
        if token.location.line == line_number:
            if token.spelling == keyword and token.kind != clang.cindex.TokenKind.COMMENT:
                return True 
                
    return False

def get_enclosing_function(cursor, target_line):
    """Phase 3: Recursively traverse the AST to find the function boundaries."""
    if cursor.kind in (clang.cindex.CursorKind.FUNCTION_DECL, clang.cindex.CursorKind.CXX_METHOD):
        if cursor.extent.start.line <= target_line <= cursor.extent.end.line:
            return cursor
            
    for child in cursor.get_children():
        result = get_enclosing_function(child, target_line)
        if result:
            return result
    return None

def extract_macros_from_file(filepath):
    """Scans the file for preprocessor macros to ensure AST includes them."""
    macros = set()
    
    ifdef_pattern = re.compile(r'^\s*#\s*(?:ifdef|ifndef)\s+([A-Za-z0-9_]+)')
    defined_pattern = re.compile(r'defined\s*\(?\s*([A-Za-z0-9_]+)\s*\)?')

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.lstrip().startswith('#'):
                    continue

                m1 = ifdef_pattern.search(line)
                if m1:
                    macros.add(m1.group(1))

                if '#if' in line or '#elif' in line:
                    for match in defined_pattern.finditer(line):
                        macros.add(match.group(1))
    except Exception as e:
        logging.warning(f"Failed to read macros from {filepath}: {e}")
        
    return macros

def analyze_and_extract(keyword, search_dir):
    locations = find_keyword_fast(keyword, search_dir)
    if not locations:
        logging.info(f"Keyword '{keyword}' not found in any source files.")
        return

    logging.info(f"Found {len(locations)} raw occurrence(s). Booting Clang analyzer...")
    
    index = clang.cindex.Index.create()
    processed_functions = set()
    
    for filepath, line_number in locations:
        compdb_dir = os.path.dirname(os.path.abspath(filepath))
        args = ['-x', 'c++']
        try:
            while not os.path.exists(os.path.join(compdb_dir, 'compile_commands.json')):
                parent_dir = os.path.dirname(compdb_dir)
                if parent_dir == compdb_dir:
                    break
                compdb_dir = parent_dir
            compdb = clang.cindex.CompilationDatabase.fromDirectory(compdb_dir)
            compile_cmds = compdb.getCompileCommands(filepath)
            if compile_cmds:
                args = list(compile_cmds[0].arguments)[1:-1]
                    
        except Exception:
            logging.warning(f"Warning: Failed to load or parse compile_commands.json for {filepath}")

        detected_macros = extract_macros_from_file(filepath)
        for macro in detected_macros:
            macro_flag = f"-D{macro}"
            if macro_flag not in args:
                args.insert(0, macro_flag)
                
        tu = index.parse(filepath, args=args)
        
        if not is_active_code(tu, filepath, line_number, keyword):
            logging.debug(f"Skipping '{keyword}' at {filepath}:{line_number} (inactive code or comment)")
            continue
        # ------------------------------

        func_cursor = get_enclosing_function(tu.cursor, line_number)
        
        if func_cursor:
            func_name = func_cursor.spelling
            
            # If the enclosing function is the keyword itself, we found its definition/self-reference. Skip it.
            if func_name == keyword:
                logging.debug(f"Skipping exact match definition of '{keyword}' at {filepath}:{line_number}")
                continue
            # ------------------
            
            start_line = func_cursor.extent.start.line
            end_line = func_cursor.extent.end.line
            
            unique_key = f"{filepath}::{func_name}"
            
            if unique_key not in processed_functions:
                processed_functions.add(unique_key)
                
                logging.info(f"### Location: `{filepath}` (Line {line_number})")
                logging.info(f"### Function: `{func_name}`")
                
                """ with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    body = "".join(lines[start_line-1:end_line])
                    # If you want to log the function body as well, you can uncomment the next line:
                    #logging.debug(f"Function Body:\n{body.strip()}\n") """

if __name__ == "__main__":
    # Initialize the logger first so we capture everything, including usage errors
    setup_logger(sys.argv[0])

    if len(sys.argv) < 2:
        logging.error("Usage: python trace_analyzer.py <keyword>")
        sys.exit(1)
        
    target_keyword = sys.argv[1]
    target_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    
    logging.info(f"Starting trace analysis for keyword: '{target_keyword}' in directory: '{target_dir}'")
    analyze_and_extract(target_keyword, target_dir)