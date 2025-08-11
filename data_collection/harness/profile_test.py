#!/usr/bin/env python3
# Filename: profile_pytest.py

import sys
import os
import runpy
import argparse
import yappi
import ast
import importlib.util
from pathlib import Path
import json
# --- AST ---
class CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.calls = set()
    def visit_Call(self, node: ast.Call):
        name = self._get_full_name(node.func)
        if name:
            self.calls.add(name)
        self.generic_visit(node)
    def _get_full_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parent = self._get_full_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None

def extract_decorator_name(node):
    """Recursively extract the core name of decorator (outermost function/attribute)"""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return extract_decorator_name(node.value) + '.' + node.attr
    elif isinstance(node, ast.Call):
        return extract_decorator_name(node.func)
    return None
    
# --- Parse specified function AST ---
def analyze_function_calls(py_path: Path, entry_func: str):
    """
    Recursively parse entry_func and its internal calls to same-file functions and external module functions,
    returns call mapping: { (alias, attr): (file, line) }
    """
    # Read and parse AST
    source = py_path.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(py_path))
    # Collect top-level import mapping alias->fullname
    # 1. Get current file path and project root directory
    current_file = Path(py_path).resolve()
    project_root = Path("/testbed")  # Adjust root directory retrieval logic based on actual situation
    
    # 2. Calculate the package path where current file is located
    # Example: /project_root/C/file.py → C
    relative_to_root = current_file.relative_to(project_root)
    package_parts = list(relative_to_root.parent.parts)  # ["C"]
    
    imports = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                full_name = a.name
                imports[a.asname or a.name] = full_name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for a in node.names:
                fullname = f"{module}" if module else a.name
                # level=1 means backtrack one level → current directory is package root
                if node.level >= 1:
                    package_parts_ = package_parts[:-(node.level - 1)] if node.level > 1 else package_parts[:]
                
                    if len(package_parts_) > 0:
                        # Concatenate target module full path
                        fullname = ".".join(package_parts_) + f".{fullname}"
                imports[a.asname or a.name] = fullname
    # Collect function nodes defined in the file
    func_defs = {}
    # Collect top-level functions and methods inside classes
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_defs[node.name] = node
        elif isinstance(node, ast.ClassDef):
            # Collect methods in class, key uses methodName
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    func_defs[item.name] = item
    # Recursive call collection
    results = {}
    visited = set()
    def process(func_name):
        func_name = func_name.split('.')[-1]
        if func_name in visited:
            return
        visited.add(func_name)
        node = func_defs.get(func_name)
        if not node:
            return
        all_calls = []
        # Process function decorators
        for decorator in node.decorator_list:
            decorator_name = extract_decorator_name(decorator)
            if decorator_name:
                all_calls.append(decorator_name)

        # Collect all calls within current function body
        collector = CallCollector()
        for stmt in node.body:
            collector.visit(stmt)
        all_calls.extend(collector.calls)

        for call in all_calls:
            parts = call.split('.',1)
            #print(f'ast {parts}')
            # Function calls without alias in current file
            if len(parts)==1:
                local = parts[0]
                # Recursively enter current file function
                if local in func_defs:
                    process(local)
                    continue
                else:
                    alias = None
                    attr = local
                    modname = imports.get(local)
            elif parts[0] == "self":
                local = parts[1]
                # Recursively enter current file function
                if local in func_defs:
                    process(local)
                    continue
                else:
                    # External module call alias.attr
                    alias, attr = parts
                    modname = imports.get(alias)
            else:
                # External module call alias.attr
                alias, attr = parts
                modname = imports.get(alias)
            if not modname:
                results[attr] = (None, None, alias)
                continue
            # Locate module file
            spec = None
            try:
                spec = importlib.util.find_spec(modname)
            except Exception:
                parent,_sep,_ = modname.rpartition('.')
                spec = importlib.util.find_spec(parent) if parent else None
            path = spec.origin if spec and spec.origin and spec.origin.endswith('.py') else None
            if not path:
                results[attr] = (None, None, alias)
                continue
            # Find definition line number
            def_line = None
            mod_src = Path(path).read_text(encoding='utf-8')
            mod_tree = ast.parse(mod_src, filename=path)
            for mn in mod_tree.body:
                if isinstance(mn, ast.FunctionDef) and mn.name==attr:
                    def_line = mn.lineno
                    break
            results[attr] = (path, def_line, alias)
            print(f'ast {path} {def_line} {alias} {attr}')
    # Start recursion
    process(entry_func)
    return results

def get_file_from_test(test):
    file_path = test.split("::")[0]
    return file_path

def get_short_test_name(test):
    return test.split("::")[-1].split("[")[0]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, help="output path")
    p.add_argument("--test", "-t", required=True,
                   help="test node-id or path")
    # Capture all arguments after "--" here
    p.add_argument("pytest_args", nargs=argparse.REMAINDER,
                   help="all flags/options to pass through to pytest")
    args = p.parse_args()
    test = args.test
    py_args = args.pytest_args
    if py_args and py_args[0] == "--":
        py_args = py_args[1:]

    functions = []

    # 3. Start yappi sampling (including C extensions)
    print("[profile_pytest] Yappi plugin is loaded")
    yappi.set_clock_type('cpu')
    yappi.start(builtins=True)

    # 4. Assemble pytest's sys.argv
    #    sys.argv[0] must be "pytest" for run_module to correctly recognize
    sys.argv = py_args + [test]
    # 5. Run pytest as __main__ and catch SystemExit
    exit_code = 0
    try:
        runpy.run_module("pytest", run_name="__main__")
    except SystemExit as e:
        exit_code = e.code
        print(f"[profile_pytest] pytest exited with code {exit_code!r}, continuing teardown...")

    yappi.stop()

    # Recursively find AST in all test files
    ast_results = {}
    visit = set()
    def recursive_call(test_path, test_func):
        if test_path in visit:
            return
        visit.add(test_path)
        ast_results_new = analyze_function_calls(Path(test_path), test_func)
        for key, value in ast_results_new.items():
            if value[0] is not None:
                mod = "/".join(value[0].split("/")[2:]) # /testbed/xxx
                if os.path.exists(mod) and (("tests" in mod or "testing" in mod) and 'sphinx/testing' not in mod):
                    recursive_call(Path(value[0]), key if value[2] is None else f"{value[2]}.{key}")
                else:
                    ast_results[key] = value
            else:
                ast_results[key] = value

    recursive_call(Path(get_file_from_test(test)), get_short_test_name(test))
    print(ast_results)
    print("[profile_pytest] Yappi plugin is stopped")
    stats = yappi.get_func_stats()

    # 7. Convert to pstats to read callers/callees
    ps = yappi.convert2pstats(stats)

    # 8. Output functions invoked by the test
    print(f"\n=== callees invoked by {test} {get_short_test_name(test)} ===\n")
    for (mod, lineno, func_name), (_, _, _, _, callers) in ps.stats.items():
        mod = "/".join(mod.split("/")[2:]) # /testbed/xxx
        if not os.path.exists(mod):
            continue
        
        # if "Run" in func_name:
        #     print(f"!!!{(mod, lineno, func_name), (_, _, _, _, callers)}")

        for (caller_mod, caller_lineno, caller_name), (call_count, _, _, call_time) in callers.items():
            # Only show calls from the test
            if get_file_from_test(test) in caller_mod and (("tests" not in mod and "testing" not in mod) or 'sphinx/testing' in mod) \
                and ("__" not in func_name):
                        print(f"trace: {mod}:{lineno}:{func_name}")
                        functions.append({"mod":mod, "func_name": func_name, "type":"trace"})
            elif (("tests" not in mod and "testing" not in mod) or 'sphinx/testing' in mod) \
                and ("__" not in func_name):
                base_func_name = func_name.split('.')[-1]
                if base_func_name in ast_results and is_same_mod(ast_results[base_func_name], mod):
                    print(f"ast: {mod}:{lineno}:{func_name}")
                    functions.append({"mod":mod, "func_name": func_name, "type":"ast"})
            #else:
            #    print(f"missing: {mod}:{lineno}:{func_name}")

    # 9. Exit with pytest's exit code
    with open(args.output, "w") as f:
        json.dump(functions,f)
    sys.exit(exit_code)


def is_same_mod(ast_result, mod):
    file,_,_ = ast_result
    if not file:
        return True
    file = "/".join(file.split("/")[2:])
    if file.endswith("__init__.py"):
        file = "/".join(file.split("/")[:-1])
    if mod.endswith("__init__.py"):
        mod = "/".join(mod.split("/")[:-1])
    if file in mod or mod in file:
        return True
    return False


if __name__ == "__main__":
    main()