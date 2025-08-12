import ast
import os
import re
from unidiff import PatchSet, Hunk

def get_qualified_functions(code):
    """Get all functions/methods with fully qualified names and line ranges"""
    functions = []
    try:
        tree = ast.parse(code)
    except:
        print(code)
    
    class StackVisitor(ast.NodeVisitor):
        def __init__(self):
            self.stack = []  # Tracks current class/function nesting
            self.functions = []
        
        def visit_ClassDef(self, node):
            """Handle class definitions and track nesting"""
            self.stack.append(node.name)
            self.generic_visit(node)  # Continue traversing child nodes
            self.stack.pop()
        
        def visit_FunctionDef(self, node):
            """Handle regular function definitions"""
            self._handle_function(node)
        
        def visit_AsyncFunctionDef(self, node):
            """Handle async function definitions"""
            self._handle_function(node)
        
        def _handle_function(self, node):
            """Process function node and record metadata"""
            # Build qualified name (e.g., "ClassName.method_name")
            qualifier = ".".join(self.stack) if self.stack else ""
            full_name = f"{qualifier}.{node.name}" if qualifier else node.name
            
            # Get line range
            start_line = node.lineno
            end_line = getattr(node, 'end_lineno', None)
            
            # Fallback for Python <3.8
            if end_line is None:
                end_line = max(
                    n.lineno for n in ast.walk(node) 
                    if hasattr(n, 'lineno')
                )
            
            self.functions.append({
                'name': full_name,
                'start': start_line,
                'end': end_line
            })
            
            # Handle nested functions
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
    
    visitor = StackVisitor()
    visitor.visit(tree)
    return visitor.functions

def get_modified_lines(hunk):
    modified_lines = []
    current_line = hunk.source_start
    
    for line in hunk:
        if line.is_added or line.is_removed:
            modified_lines.append(current_line)
        if not line.is_added:  # be deleted or context
            current_line += 1
    
    return (min(modified_lines), max(modified_lines))

def find_modified_functions(patch_content, file_contents):
    """Identify modified functions from patch (file path or content string)"""
    
    modified_functions = {}
    patch = PatchSet.from_string(patch_content)
    
    for patched_file in patch:
        src_file = patched_file.source_file
        if not src_file.endswith(".py"):
            continue
        if src_file.startswith("a/"):
            src_file = "/".join(src_file.split("/")[1:])
        file_content = file_contents[src_file]
        
        
        functions = get_qualified_functions(file_content)
        modified_in_file = set()
        
        for hunk in patched_file:
            # Get the actual modified line range
            start_line, end_line = get_modified_lines(hunk)
            
            # Check which functions overlap with the modified range
            for func in functions:
                # Check if function overlaps with modified block
                if (func['start'] <= end_line and func['end'] >= start_line):
                    modified_in_file.add(func['name'])
        
        if modified_in_file:
            modified_functions[src_file] = list(modified_in_file)
    
    return modified_functions

