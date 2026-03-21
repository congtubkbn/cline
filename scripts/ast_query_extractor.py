#!/usr/bin/env python3
"""
AST Query Extractor - Core component for recursive caller discovery workflow.

This script extracts function call information from C/C++ source files using AST parsing via Tree-Sitter.
It supports two query types:
- "trace": For log messages and trace strings (extracts functions that contain these strings)
- "function": For function names (extracts callers of the specified function)

Usage:
    python ast_query_extractor.py <query_type> "<query_string>"
    
Examples:
    python ast_query_extractor.py trace "EMERGENCY_CALL_SET mode type"
    python ast_query_extractor.py function "tx_handle_emergency_call_set"
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import tree_sitter_cpp
from tree_sitter import Language, Parser

class ASTQueryExtractor:
    def __init__(self):
        self.source_dirs = ["sipc"]
        self.output_dir = Path("process/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Tree-Sitter Parser for C/C++
        CPP_LANGUAGE = Language(tree_sitter_cpp.language())
        self.parser = Parser(CPP_LANGUAGE)
        
    def classify_query(self, query_string: str) -> str:
        """Classify query as 'trace' or 'function' based on content analysis."""
        if any(char in query_string for char in [' ', '%', '_SET', '_GET', '_IND']):
            return "trace"
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', query_string):
            return "function"
        return "trace"
    
    def find_source_files(self) -> List[Path]:
        """Find all C/C++ source files in the project."""
        source_files = []
        for source_dir in self.source_dirs:
            if os.path.exists(source_dir):
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        if file.endswith(('.c', '.cpp', '.cc', '.h', '.hpp')):
                            source_files.append(Path(root) / file)
        return source_files
    
    def _get_node_name(self, node, source_bytes: bytes) -> str:
        """Helper to safely extract the identifier name from an AST node."""
        if node is None:
            return None
        if node.type in ['identifier', 'field_identifier']:
            return source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
        for child in node.children:
            res = self._get_node_name(child, source_bytes)
            if res: return res
        return None

    def extract_function_calls_from_ast(self, source_file: Path) -> Dict[str, List[str]]:
        """Extract function calls using Tree-Sitter AST."""
        function_calls = {}
        
        try:
            with open(source_file, 'rb') as f:
                source_bytes = f.read()
                
            tree = self.parser.parse(source_bytes)
            
            def find_calls_in_body(node, calls_list):
                if node.type == 'call_expression':
                    func_node = node.child_by_field_name('function') or node.children[0]
                    called_name = self._get_node_name(func_node, source_bytes)
                    if called_name and called_name not in calls_list:
                        calls_list.append(called_name)
                
                for child in node.children:
                    find_calls_in_body(child, calls_list)

            def traverse_for_definitions(node):
                if node.type == 'function_definition':
                    func_name = None
                    for child in node.children:
                        if child.type in ['function_declarator', 'declaration', 'pointer_declarator', 'reference_declarator']:
                            func_name = self._get_node_name(child, source_bytes)
                            break
                    
                    if func_name:
                        if func_name not in function_calls:
                            function_calls[func_name] = []
                        
                        body_node = node.child_by_field_name('body')
                        if body_node:
                            find_calls_in_body(body_node, function_calls[func_name])
                else:
                    for child in node.children:
                        traverse_for_definitions(child)

            traverse_for_definitions(tree.root_node)
            
        except Exception as e:
            print(f"Error parsing {source_file}: {e}")
            
        return function_calls
    
    def search_trace_strings(self, query_string: str) -> List[Dict]:
        """Search for trace strings in source files and find containing functions."""
        results = []
        source_files = self.find_source_files()
        pattern = re.escape(query_string).replace(r'\%', r'.*?')
        
        for source_file in source_files:
            try:
                with open(source_file, 'rb') as f:
                    source_bytes = f.read()
                    
                content = source_bytes.decode('utf-8', errors='ignore')
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                
                if matches:
                    tree = self.parser.parse(source_bytes)
                    processed_functions = set()
                    
                    for match in matches:
                        line_no = content.count('\n', 0, match.start())
                        
                        def find_enclosing_func(node, target_row):
                            if node.type == 'function_definition' and node.start_point.row <= target_row <= node.end_point.row:
                                for child in node.children:
                                    inner = find_enclosing_func(child, target_row)
                                    if inner: return inner
                                return node
                            for child in node.children:
                                if child.start_point.row <= target_row <= child.end_point.row:
                                    res = find_enclosing_func(child, target_row)
                                    if res: return res
                            return None

                        func_node = find_enclosing_func(tree.root_node, line_no)
                        
                        if func_node:
                            func_name = "Unknown"
                            for child in func_node.children:
                                if child.type in ['function_declarator', 'declaration', 'pointer_declarator', 'reference_declarator']:
                                    name = self._get_node_name(child, source_bytes)
                                    if name: 
                                        func_name = name
                                        break
                                        
                            if func_name not in processed_functions:
                                processed_functions.add(func_name)
                                results.append({
                                    "function_name": func_name,
                                    "file_path": str(source_file),
                                    "line_number": func_node.start_point.row + 1,
                                    "function_body": source_bytes[func_node.start_byte:func_node.end_byte].decode('utf-8', errors='ignore'),
                                    "llm_synthesis": "Pending LLM synthesis"
                                })
                                
            except Exception as e:
                print(f"Error reading {source_file}: {e}")
                
        return results
    
    def find_function_callers(self, target_function: str) -> List[Dict]:
        """Find all functions that call the target function."""
        results = []
        source_files = self.find_source_files()
        
        for source_file in source_files:
            try:
                # Extract all function calls from this file
                function_calls = self.extract_function_calls_from_ast(source_file)
                
                # Find functions that call our target
                for caller_func, called_funcs in function_calls.items():
                    if target_function in called_funcs:
                        # Extract the metadata for the caller via Tree-Sitter
                        node, source_bytes = self._get_function_node(source_file, caller_func)
                        if node:
                            function_body = source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                            line_number = node.start_point.row + 1
                            
                            results.append({
                                "function_name": caller_func,
                                "file_path": str(source_file),
                                "line_number": line_number,
                                "function_body": function_body,
                                "llm_synthesis": "Pending LLM synthesis"
                            })
                        
            except Exception as e:
                print(f"Error processing {source_file}: {e}")
                
        return results

    def _get_function_node(self, source_file: Path, target_function: str):
        """Helper to fetch the Tree-Sitter node of a specific function by name."""
        try:
            with open(source_file, 'rb') as f:
                source_bytes = f.read()
            tree = self.parser.parse(source_bytes)
            
            result_node = None
            def traverse(node):
                nonlocal result_node
                if result_node: return
                if node.type == 'function_definition':
                    for child in node.children:
                        if child.type in ['function_declarator', 'declaration', 'pointer_declarator', 'reference_declarator']:
                            if self._get_node_name(child, source_bytes) == target_function:
                                result_node = node
                                return
                for child in node.children:
                    traverse(child)

            traverse(tree.root_node)
            return result_node, source_bytes
        except Exception:
            return None, None
    
    def generate_output_filename(self, query_type: str, query_string: str) -> str:
        """Generate output filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r'[^\w\-\.]', '_', query_string)[:50]
        return f"query_{query_type}_{safe_query}_{timestamp}.json"
    
    def save_results(self, results: List[Dict], query_type: str, query_string: str) -> str:
        """Save results to JSON file and return the filepath."""
        output_file = self.output_dir / self.generate_output_filename(query_type, query_string)
        
        output_data = {
            "query_type": query_type,
            "query_string": query_string,
            "timestamp": datetime.now().isoformat(),
            "source_files": [str(f) for f in self.find_source_files()],
            "caller": results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        return str(output_file)

def main():
    if len(sys.argv) != 3:
        print("Usage: python ast_query_extractor.py <query_type> \"<query_string>\"")
        print("Examples:")
        print("  python ast_query_extractor.py trace \"EMERGENCY_CALL_SET mode type\"")
        print("  python ast_query_extractor.py function \"tx_handle_emergency_call_set\"")
        sys.exit(1)
    
    query_type = sys.argv[1].lower()
    query_string = sys.argv[2]
    
    if query_type not in ['trace', 'function']:
        print("Error: query_type must be 'trace' or 'function'")
        sys.exit(1)
    
    extractor = ASTQueryExtractor()
    
    print(f"Processing {query_type} query: '{query_string}'")
    
    if query_type == 'trace':
        results = extractor.search_trace_strings(query_string)
    else:  
        results = extractor.find_function_callers(query_string)
    
    output_file = extractor.save_results(results, query_type, query_string)
    
    print(f"Results saved to: {output_file}")
    print(f"Found {len(results)} matching functions")
    
    return output_file

if __name__ == "__main__":
    main()