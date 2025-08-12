import ast
from pathlib import Path
import os

def extract_function_source(source, func_node):
    start_line = func_node.lineno - 1
    linenos = [
        getattr(child, 'end_lineno', getattr(child, 'lineno', None))
        for child in ast.walk(func_node)
        if hasattr(child, 'lineno') or hasattr(child, 'end_lineno')
    ]
    end_line = max(l for l in linenos if l is not None)
    return '\n'.join(source.splitlines()[start_line:end_line])

def find_function_in_class(class_node, function_name):
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == function_name:
            return item
    return None

def find_class_by_name(tree, class_name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None

def resolve_imports(tree, current_file_path):
    """
    Build a mapping: class_name -> file_path
    """
    imports = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module_path = node.module.replace(".", "/") if node.module else ""
            for name in node.names:
                full_path = Path(current_file_path).parent / f"{module_path}/{name.name}.py"
                if full_path.exists():
                    imports[name.asname or name.name] = full_path.resolve()
        elif isinstance(node, ast.Import):
            for name in node.names:
                parts = name.name.split(".")
                if len(parts) >= 2:
                    mod_path = "/".join(parts)
                    full_path = Path(current_file_path).parent / f"{mod_path}.py"
                    if full_path.exists():
                        imports[name.asname or parts[-1]] = full_path.resolve()
    return imports

def search_in_class_hierarchy(class_name, function_name, searched_files, base_paths):
    for base_path in base_paths:
        # if base_path in searched_files:
        #     continue
        searched_files.add(base_path)
        if not base_path.exists():
            continue
        source = base_path.read_text()
        tree = ast.parse(source)
        imports = resolve_imports(tree, base_path)

        class_node = find_class_by_name(tree, class_name)
        if class_node:
            func_node = find_function_in_class(class_node, function_name)
            if func_node:
                return extract_function_source(source, func_node)

            # Recurse into base classes
            base_class_names = [
                b.id if isinstance(b, ast.Name) else b.attr for b in class_node.bases
                if isinstance(b, (ast.Name, ast.Attribute))
            ]
            base_class_paths =  [(b, imports.get(b))  if b in imports else (b,[base_path]) for b in base_class_names]
            for base_class, base_path in base_class_paths:
                result = search_in_class_hierarchy(function_name=function_name,
                                                class_name=base_class,
                                                searched_files=searched_files,
                                                base_paths=base_path)
                if result:
                    return result
    return None

def get_test_contents(instance):
    """
    Returns the contents of the efficiency test
    """
    contents = {}
    # try:
    for test in eval(instance["efficiency_test"]):
        test_split = test.split("::")
        file_name = test_split[0]
        file_path = Path(file_name)
        source = file_path.read_text()
        tree = ast.parse(source)
        imports = resolve_imports(tree, file_path)

        if len(test_split) == 2:
            function_name = test_split[1].split("[")[0].split("(")[0].strip().split(".")[-1]
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    contents[test] = extract_function_source(source, node)
                    break
                elif isinstance(node, ast.ClassDef) and node.name == function_name:
                    contents[test] = extract_function_source(source, node)
                    break
                elif isinstance(node, ast.AsyncFunctionDef) and node.name == function_name:
                    contents[test] = extract_function_source(source, node)
                    break
            else:
                print(f"[{test}]Function {function_name} not found in {file_name}")
                continue

        elif len(test_split) == 3:
            class_name = test_split[1]
            function_name = test_split[2].split("[")[0].split("(")[0].strip()

            class_node = find_class_by_name(tree, class_name)
            if class_node:
                func_node = find_function_in_class(class_node, function_name)
                if func_node:
                    contents[test] = extract_function_source(source, func_node)
                    continue
                # Search base class definitions (possibly in other files)
                base_class_names = [
                    b.id if isinstance(b, ast.Name) else b.attr for b in class_node.bases
                    if isinstance(b, (ast.Name, ast.Attribute))
                ]
                base_class_paths = [(b, imports.get(b))  if b in imports else (b,[file_path]) for b in base_class_names]
                for base_class, base_path in base_class_paths:
                    result = search_in_class_hierarchy(class_name=base_class,
                                                    function_name=function_name,
                                                    searched_files=set(),
                                                    base_paths=base_path)
                    if result:
                        contents[test] = result
                        break
                else:
                    print(f"[{test}]Function {function_name} not found in base classes of {class_name}")
            else:
                print(f"[{test}]Class {class_name} not found in {file_name}")
        else:
            print(f"Invalid test format: {test}")
            continue
    # except Exception as e:
    #     print(f"Error processing efficiency test contents for instance {instance.get('instance_id', 'UNKNOWN')}: {e}")
    return contents
