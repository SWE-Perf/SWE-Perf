import ast
from pathlib import Path

def extract_called_functions(source_code):
    """
    Returns a list of (object_name, function_name) or (function_name,) from the test code.
    """
    # unexpected indent
    try:
        first_chara = [l[0] for l in source_code.splitlines() if len(l)>0]
        while len(set(first_chara)) == 1:
            source_code = "\n".join([l[1:] if len(l)>0 else l for l in source_code.splitlines()])
            first_chara = [l[0] for l in source_code.splitlines() if len(l)>0]
        tree = ast.parse(source_code)
    except:
        first_chara = [l[0] for l in source_code.splitlines() if len(l)>0]
        if len(set(first_chara)) == 1:
            source_code = "\n".join([l[1:] if len(l)>0 else l for l in source_code.splitlines()])
        print(source_code)

    called_functions = set()
    var_class_map = {}  

    # Assigned classes to variables
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, (ast.Name, ast.Attribute)):
                class_name = resolve_node_name(node.value.func)
                if class_name:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_class_map[target.id] = class_name[0]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            called_func = resolve_node_name(func)
            if called_func and len(called_func) == 2 and called_func[0] in var_class_map:
                called_functions.add((var_class_map[called_func[0]], called_func[1]))
            elif called_func:
                called_functions.add(called_func)

        # Deco
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                # @deco
                if isinstance(decorator, ast.Name):
                    called_functions.add((decorator.id,))
                # @module.deco
                elif isinstance(decorator, ast.Attribute):
                    decorator_name = resolve_node_name(decorator)
                    if decorator_name:
                        called_functions.add(decorator_name)
                # @deco(arg)
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        called_functions.add((decorator.func.id,))
                    elif isinstance(decorator.func, ast.Attribute):
                        decorator_name = resolve_node_name(decorator.func)
                        if decorator_name:
                            called_functions.add(decorator_name)
    return called_functions

def resolve_node_name(node):
    if isinstance(node, ast.Attribute):
        # e.g., obj.method() or Class.method()
        if isinstance(node.value, ast.Name):
            return (node.value.id, node.attr)
        elif isinstance(node.value, ast.Attribute):  # e.g., pkg.Class.method
            parts = []
            val = node
            while isinstance(val, ast.Attribute):
                parts.append(val.attr)
                val = val.value
            if isinstance(val, ast.Name):
                parts.append(val.id)
            full_call = ".".join(reversed(parts))
            return (full_call,)
    elif isinstance(node, ast.Name):
        # e.g., direct function call
        return (node.id,)
    else:
        return None

def parse_imports(file_name):
    """
    Parse import statements and return a mapping of local name -> module path
    """
    file_path = Path(file_name)
    source_code = file_path.read_text()
    tree = ast.parse(source_code)
    import_map = {}
    asname_map = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module
            for alias in node.names:
                local_name = alias.asname or alias.name
                if "pytest" not in local_name and (not module or "pytest" not in module):
                    if alias.asname:
                        asname_map[alias.asname] = alias.name
                    import_map[local_name] = f"{module}.{alias.name}" if module else alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                local_name = alias.asname or name.split('.')[0]
                if "pytest" not in name:
                    if alias.asname:
                        asname_map[alias.asname] = name.split('.')[0]
                    import_map[local_name] = name
    return import_map, asname_map

def module_to_filepath(module_name):
    """
    Convert 'package.module' to 'package/module.py'
    Also handles direct function/class references
    """
    # Try as a module first
    paths = [
        Path(*module_name.split(".")).with_suffix(".py"),
        Path(*module_name.split(".")) / "__init__.py"
    ]
    
    # If it's a function/class reference, get its containing module
    if '.' in module_name:
        base_module = module_name.rsplit('.', 1)[0]
        paths.extend([
            Path(*base_module.split(".")).with_suffix(".py"),
            Path(*base_module.split(".")) / "__init__.py"
        ])
    
    return paths

def resolve_called_functions_to_paths(test_source, test_path, repo_root="."):
    """
    Main function: extract called functions and resolve them to paths under repo_root
    """
    called_funcs = extract_called_functions(test_source)
    import_map, asname_map = parse_imports(test_path)
    if "matplotlib" in test_path or "mpl_toolkits" in test_path:
        called_funcs_new = set()
        for call in list(called_funcs):
            if call[0] == "ax":
                # Special case for matplotlib, where 'ax' is often used
                called_funcs_new.add(("matplotlib.axes.Axes", call[1]) if len(call) > 1 else ("matplotlib.axes.Axes",))
            elif call[0] == "fig":
                # Special case for matplotlib, where 'fig' is often used
                called_funcs_new.add(("matplotlib.figure.Figure", call[1]) if len(call) > 1 else ("matplotlib.figure.Figure",))
            else:
                called_funcs_new.add(call)
        called_funcs = called_funcs_new
        import_map["matplotlib.axes.Axes"] = "matplotlib.axes.Axes"
        import_map["matplotlib.figure.Figure"] = "matplotlib.figure.Figure"
    # print(called_funcs)
    resolved = {}

    for call in called_funcs:
        if len(call) == 2:
            obj_name, func_name = call
            # print(f"{obj_name}.{func_name} in import map? {obj_name in import_map}")
            if obj_name in import_map:
                module_path = import_map[obj_name]
                rel_paths = module_to_filepath(module_path)
                if "matplotlib" in test_path or "mpl_toolkits" in test_path:
                    # Special case for matplotlib, which has many submodules
                    rel_paths = [Path("lib")/p for p in rel_paths]
                for rel_path in rel_paths:
                    full_path = Path(repo_root) / rel_path
                    # print(full_path)
                    if full_path.exists():
                        resolved[f"{module_path}.{func_name}"] = str(rel_path)
                        break
        elif len(call) == 1:
            func_or_module = call[0]
            # print(f"{func_or_module} in import map? {func_or_module in import_map}")
            if func_or_module in import_map:
                module_path = import_map[func_or_module]
                rel_paths = module_to_filepath(module_path)
                if "matplotlib" in test_path or "mpl_toolkits" in test_path:
                    # Special case for matplotlib, which has many submodules
                    rel_paths = [Path("lib")/p for p in rel_paths]
                for rel_path in rel_paths:
                    full_path = Path(repo_root) / rel_path
                    # print(full_path)
                    if full_path.exists():
                        resolved[f"{module_path}"] = str(rel_path)
                        break
    if len(resolved) == 0:
        print("----------------------------")
        print(test_path)
        print(test_source)
        print(called_funcs)
    return called_funcs, import_map, resolved
