import json
import logging
import os
import traceback
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unidiff
from tqdm.auto import tqdm

from harness.make_datasets.tokenize_dataset import TOKENIZER_FUNCS
from harness.make_datasets.utils import AutoContextManager, ingest_directory_contents
from harness.make_datasets.statistics import count_all
from harness.make_datasets.get_test_contents_from_test_name import get_test_contents
from harness.make_datasets.get_optim_function_name_from_test import resolve_called_functions_to_paths
from harness.make_datasets.get_functions_from_patch import find_modified_functions
import ast

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


PATCH_EXAMPLE = """--- a/file.py
+++ b/file.py
@@ -1,27 +1,35 @@
 def euclidean(a, b):
-    while b:
-        a, b = b, a % b
-    return a
+    if b == 0:
+        return a
+    return euclidean(b, a % b)
 
 
 def bresenham(x0, y0, x1, y1):
     points = []
     dx = abs(x1 - x0)
     dy = abs(y1 - y0)
-    sx = 1 if x0 < x1 else -1
-    sy = 1 if y0 < y1 else -1
-    err = dx - dy
+    x, y = x0, y0
+    sx = -1 if x0 > x1 else 1
+    sy = -1 if y0 > y1 else 1
 
-    while True:
-        points.append((x0, y0))
-        if x0 == x1 and y0 == y1:
-            break
-        e2 = 2 * err
-        if e2 > -dy:
+    if dx > dy:
+        err = dx / 2.0
+        while x != x1:
+            points.append((x, y))
             err -= dy
-            x0 += sx
-        if e2 < dx:
-            err += dx
-            y0 += sy
+            if err < 0:
+                y += sy
+                err += dx
+            x += sx
+    else:
+        err = dy / 2.0
+        while y != y1:
+            points.append((x, y))
+            err -= dx
+            if err < 0:
+                x += sx
+                err += dy
+            y += sy
 
+    points.append((x, y))
     return points"""


FULL_GENERATION_EXAMPLE = """[start of /src/this_file.py]
import os

def euclidean(a, b):
    if b == 0:
        return a
    return euclidean(b, a % b)
[end of /src/this_file.py]
[start of /src/another_file.py]
def bresenham(x0, y0, x1, y1):
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    if dx > dy:
        err = dx / 2.0
        while x != x1:
            points.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y1:
            points.append((x
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    points.append((x, y))
    return points
[end of /src/another_file.py]"""


def add_lines_list(content):
    content_with_lines = list()
    for ix, line in enumerate(content.split("\n"), start=1):
        content_with_lines.append(f"{ix} {line}")
    return content_with_lines


def add_lines(content):
    return "\n".join(add_lines_list(content))


def make_code_text(files_dict, add_line_numbers=True):
    all_text = ""
    for filename, contents in sorted(files_dict.items()):
        all_text += f"[start of {filename}]\n"
        if add_line_numbers:
            all_text += add_lines(contents)
        else:
            all_text += contents
        all_text += f"\n[end of {filename}]\n"
    return all_text.strip("\n")


def make_code_text_edits_only(files_dict, patch, add_line_numbers=True):
    files = dict()
    patch = unidiff.PatchSet(patch)
    for patched_file in patch:
        source_file = patched_file.source_file.split("a/", 1)[-1]
        files[source_file] = list()
        for hunk in patched_file:
            start = hunk.source_start - 15
            end = start + hunk.source_length + 15
            files[source_file].append((start, end))
    all_text = ""
    for filename, content in files_dict.items():
        all_text += f"[start of {filename}]\n"
        content_with_lines = add_lines_list(content)
        for start, end in files[filename]:
            if start > 0:
                all_text += "...\n"
            all_text += "\n".join(content_with_lines[start:end])
            all_text += "\n"
            if end < len(content_with_lines):
                all_text += "...\n"
        all_text = all_text.strip("\n")
        all_text += f"\n[end of {filename}]\n"
    return all_text.strip("\n")


def prompt_style_2(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    instructions = (
        f"I need you to solve this issue by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the following format."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
    ]
    final_text = "\n".join(final_text)
    return final_text


def prompt_style_2_edits_only(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text_edits_only(instance["file_contents"], instance["patch"])
    instructions = (
        f"I need you to solve this issue by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the following format."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
    ]
    final_text = "\n".join(final_text)
    return final_text


def prompt_style_3(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    example_explanation = (
        f"Here is an example of a patch file. It consists of changes to the code base. "
        + f"It specifies the file names, the line numbers of each change, and the removed and added lines. "
        + f"A single patch file can contain changes to multiple files."
    )
    final_instruction = (
        f"I need you to solve the provided issue by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the format shown above."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        "",
        example_explanation,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
        "",
        final_instruction,
        "Respond below:",
    ]
    final_text = "\n".join(final_text)
    return final_text


def full_file_gen(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"], add_line_numbers=False)
    code_text = make_code_text(instance["file_contents"], add_line_numbers=False)
    instructions = (
        f"I need you to solve this issue by regenerating the full files in the code base that you would like to change. "
        + f"You can change as many files as you like. "
        + f"Please respond with a list of files and their revised contents in the following format."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        instructions,
        "<example>",
        FULL_GENERATION_EXAMPLE,
        "</example>",
    ]
    final_text = "\n".join(final_text)
    return final_text

def prompt_efficiency_1(instance):
    premise = "You will be provided with a partial code base and you need to improve its efficiency and execution speed."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    example_explanation = (
        f"Here is an example of a patch file. It consists of changes to the code base. "
        + f"It specifies the file names, the line numbers of each change, and the removed and added lines. "
        + f"A single patch file can contain changes to multiple files."
    )
    final_instruction = (
        f"I need you to improve its efficiency and execution speed by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the format shown above."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        # "<issue>",
        # problem_statement,
        # "</issue>",
        # "",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        "",
        example_explanation,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
        "",
        final_instruction,
        "Respond below:",
    ]
    final_text = "\n".join(final_text)
    return final_text

def prompt_efficiency_2(instance):
    premise = "You will be provided with a partial code base and test case. You need to improve the test case's efficiency and execution speed by editing the code base."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    example_explanation = (
        f"Here is an example of a patch file. It consists of changes to the code base. "
        + f"It specifies the file names, the line numbers of each change, and the removed and added lines. "
        + f"A single patch file can contain changes to multiple files."
    )
    final_instruction = (
        f"I need you to improve its efficiency and execution speed by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the format shown above."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        # "<issue>",
        # problem_statement,
        # "</issue>",
        # "",
        "<efficiency_test>",
        instance["efficiency_test"],
        "</efficiency_test>",
        "",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        "",
        example_explanation,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
        "",
        final_instruction,
        "Respond below:",
    ]
    final_text = "\n".join(final_text)
    return final_text

def prompt_type(instance):
    premise = "下面是一个repo代码的PR，其改动带来了部分test case效率的提升，即运行时间的缩短。帮我分析其改动为什么可以带来效率提升，以及代码改动的分类。"
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    example_explanation = (
        f"Here is an example of a patch file. It consists of changes to the code base. "
        + f"It specifies the file names, the line numbers of each change, and the removed and added lines. "
        + f"A single patch file can contain changes to multiple files."
    )
    final_instruction = (
        f"I need you to solve the provided issue by generating a single patch file that I can apply "
        + f"directly to this repository using git apply. Please respond with a single patch "
        + f"file in the format shown above."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        "",
        # example_explanation,
        "<patch>",
        instance["patch"],
        "</patch>",
        "",
        "<test_patch>",
        instance["test_patch"],
        "</test_patch>",
        "",
        "<durations_changes>",
        str(instance["durations_changes"]),
        "</durations_changes>",
        "",
        "<efficiency_test>",
        instance["efficiency_test"],
        "</efficiency_test>",
        "",
    ]
    final_text = "\n".join(final_text)
    return final_text

import re
def single_function(patch):
    # More than 1 file
    if patch.count("diff --git ") > 1:
        return False
    
    flag_name = None # e.g. @@ -203,9 +203,7 @@ def is_clean(self) -> bool:
    function_name = None
    function_has_been_changed = False
    first_line = False
    function_name_changed = []
    func_pattern = re.compile(r'def\s+([\w_]+)\s*\(')
    for line in patch.split("\n"):
        if line.startswith("diff --git "): 
            continue

        func_match = re.search(func_pattern, line)
        if line.startswith("+++") or line.startswith("---"):
            if func_match:
                return False
        if first_line and func_match: # The first line of chunk
            flag_name = None
            function_name = func_match.group(1)
            first_line = False
        elif first_line: # The first line of chunk
            function_name = flag_name
            first_line = False
        elif func_match and not line.startswith("@@"): # match function and not in @@ line
            # Deal with the last chunk
            if function_name != None and function_has_been_changed:
                function_name_changed.append(function_name)
            function_has_been_changed = False
            function_name = func_match.group(1)
        elif line.startswith("@@"): # @@ line
            first_line = True
            flag_name = func_match.group(1) if func_match else None

            # Deal with the last chunk
            if function_name != None and function_has_been_changed:
                function_name_changed.append(function_name)
            function_name = None
            function_has_been_changed = False
            
        if line.startswith("+") or line.startswith("-"):
            function_has_been_changed = True

    if function_name != None and function_has_been_changed:
        function_name_changed.append(function_name)

    # if len(set(function_name_changed)) == 1: # v1, the same function name may be from the different class
    if len(function_name_changed) == 1: # v2 
        return function_name_changed[0]
    else:
        return False

def prompt_function_efficiency(instance):
    target_func = single_function(instance["patch"])
    prompt = f"""
## Instructions
You are an expert competitive programmer who excels at solving algorithm problems in multiple programming languages.
Your task is to implement a solution to the following problem in python.
## Problem Description
{instance["problem_statement"]}
The modification should be exclusively restricted to the {target_func} function.
## Original Solution
{make_code_text(instance["file_contents"])}
## Output Format
- Provide the complete solution code in **one markdown code block** with appropriate language identifier.
- Fix the original solution if it was not passed. Optimize the time efficient performance if the original solution was passed.
- EXCLUDE ALL explanations, code comments, import/package/library statements, additional classes or functions outside of the starter code scope, or starting code like `if __name__ == "__main__":` or `func main()` or `package main` or `using namespace std;`.
"""
    return prompt

def prompt_repair_efficiency(instance):
    premise = "You will be provided with a partial code base and test case. You need to improve the test case's efficiency and execution speed by editing the code base."
    readmes_text = make_code_text(instance["readmes"], add_line_numbers=False)
    code_text = make_code_text(instance["file_contents"], add_line_numbers=False)
    efficiency_test_test = make_code_text(instance["efficiency_test_contents"], add_line_numbers=False)
    final_instruction = (
"""Please improve its efficiency and execution speed by generate *SEARCH/REPLACE* edits to fix the issue.

Every *SEARCH/REPLACE* edit must use this format:
1. The file path
2. The start of search block: <<<<<<< SEARCH
3. A contiguous chunk of lines to search for in the existing source code
4. The dividing line: =======
5. The lines to replace into the source code
6. The end of the replace block: >>>>>>> REPLACE
7. You can't edit the test case, only the code base.
8. Only use standard python libraries, don't suggest installing any packages.

Here is an example:

```python
### mathweb/flask/app.py
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
```

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. If you would like to add the line '        print(x)', you must fully write that out, with all those spaces before the code!
Wrap the *SEARCH/REPLACE* edit in blocks ```python...```."""
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        # "<issue>",
        # problem_statement,
        # "</issue>",
        # "",
        "<efficiency_test>",
        problem_statement,
        "</efficiency_test>",
        "",
        "<code>",
        readmes_text,
        efficiency_test_test,
        code_text,
        "</code>",
        "",
        final_instruction,
    ]
    final_text = "\n".join(final_text)
    return final_text

def prompt_efficiency_3(instance):
    premise = "You will be provided with a partial code base and objective functions. You need to improve the objective function's efficiency and execution speed by editing the code base."
    readmes_text = make_code_text(instance["readmes"], add_line_numbers=False)
    code_text = make_code_text(instance["file_contents"], add_line_numbers=False)
    final_instruction = (
"""Please improve its efficiency and execution speed by generate *SEARCH/REPLACE* edits to fix the issue.

Every *SEARCH/REPLACE* edit must use this format:
1. The file path
2. The start of search block: <<<<<<< SEARCH
3. A contiguous chunk of lines to search for in the existing source code
4. The dividing line: =======
5. The lines to replace into the source code
6. The end of the replace block: >>>>>>> REPLACE
7. You can't edit the test case, only the code base.
8. Only use standard python libraries, don't suggest installing any packages.

Here is an example:

```python
### mathweb/flask/app.py
<<<<<<< SEARCH
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
```

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. If you would like to add the line '        print(x)', you must fully write that out, with all those spaces before the code!
Wrap the *SEARCH/REPLACE* edit in blocks ```python...```."""
    )
    problem_statement = instance["problem_statement_oracle"]
    final_text = [
        premise,
        # "<issue>",
        # problem_statement,
        # "</issue>",
        # "",
        "<problem_statement>",
        problem_statement,
        "</problem_statement>",
        "",
        "<code>",
        readmes_text,
        code_text,
        "</code>",
        "",
        final_instruction,
    ]
    final_text = "\n".join(final_text)
    return final_text

def ingest_files(filenames):
    files_dict = dict()
    for filename in filenames:
        with open(filename) as f:
            content = f.read()
        files_dict[filename] = content
    return files_dict


PROMPT_FUNCTIONS = {
    "style-2": prompt_style_2,
    "style-3": prompt_style_3,
    "full_file_gen": full_file_gen,
    "style-2-edits-only": prompt_style_2_edits_only,    
    "type": prompt_type,
    "efficiency1": prompt_efficiency_1,
    "efficiency2": prompt_efficiency_2,
    "func_effi": prompt_function_efficiency,
    "repair_efficiency": prompt_repair_efficiency,
    "efficiency3": prompt_efficiency_3
}


def add_retrieval_results(input_instances, retrieval_file, k, file_source):
    """
    Adds retrieval results to input_instances in-place
    """
    retrieval_results_path = Path(retrieval_file)
    assert (
        retrieval_results_path.exists()
    ), f"Retrieval results not found at {retrieval_results_path}"
    retrieval_results = [json.loads(line) for line in open(retrieval_results_path)]
    retrieval_results = {x["instance_id"]: x["hits"] for x in retrieval_results}
    for instance_id, instance in tqdm(
        input_instances.items(),
        total=len(input_instances),
        desc="Adding retrieval results",
    ):
        try:
            instance["hits"] = retrieval_results[instance_id][:k]
        except KeyError:
            logger.warning(f"Instance {instance_id} not found in retrieval results")
            instance["hits"] = list()


def get_oracle_filenames(instance):
    """
    Returns the filenames that are changed in the patch
    """
    source_files = {
        patch_file.source_file.split("a/", 1)[-1]
        for patch_file in unidiff.PatchSet(instance["patch"])
    }
    gold_docs = set()
    for source_file in source_files:
        gold_docs.add(source_file)
    return gold_docs


def add_text_inputs(
    input_instances,
    retrieval_file,
    k,
    prompt_style,
    file_source,
    max_context_len=None,
    tokenizer_name=None,
    verbose=False,
):
    """Adds text inputs context for prediction in-place.

    Args:
    - input_instances: dictionary with unprocessed input instances.
    - retrieval_file: if using retrieval method for file_contents, specify retrieval_file to add retrieval results
    - k: if using retrieval, specifies the maximum number of files to included within context
    - prompt_style: specify the function to generate instructions and prompt provided an instance (from PROMPT_FUNCTIONS)
    - file_source: where to collect file_contents (e.g. oracle or bm25)
    - verbose: set ContextManager verbose to True
    """
    if max_context_len is not None:
        assert (
            tokenizer_name is not None
        ), "Must specify tokenizer_name if using max_context_len"
        tokenizer, tokenizer_func = TOKENIZER_FUNCS[tokenizer_name]
    input_instances_copy = deepcopy(input_instances)
    if file_source in {"bm25"}:
        add_retrieval_results(input_instances_copy, retrieval_file, k, file_source)
    orig_dir = os.getcwd()
    with TemporaryDirectory(
        dir="/scratch" if os.path.exists("/scratch") else "/tmp"
    ) as root_dir:
        for instance_id, instance in tqdm(
            input_instances_copy.items(),
            total=len(input_instances_copy),
            desc="Adding text inputs",
        ):
            try:
                with AutoContextManager(
                    instance, root_dir, verbose=verbose
                ) as cm:
                    if prompt_style == "statistics":
                        input_instances[instance_id]["statistics"] = count_all(instance)
                        os.chdir(orig_dir)
                        continue

                    if prompt_style == "get_function_from_test":
                        test_contents = get_test_contents(instance)
                        input_instances[instance_id]["function"] = {}
                        for test_name, test_content in test_contents.items():
                            try:
                                called_funcs, import_map, resolved = resolve_called_functions_to_paths(test_content, test_name.split("::")[0])
                            except:
                                input_instances[instance_id]["function"][test_name] = {
                                    "test_content": test_content,
                                }
                            input_instances[instance_id]["function"][test_name] = {
                                "test_content": test_content,
                                "called_funcs": called_funcs,
                                "import_map": import_map,
                                "resolved": resolved
                            }
                        continue

                    readmes = cm.get_readme_files()
                    instance["readmes"] = ingest_files(readmes)
                    if max_context_len is not None:
                        instance["file_contents"] = dict()
                        base_text_inputs = PROMPT_FUNCTIONS[prompt_style](instance)
                        base_text_input_length = len(
                            tokenizer_func(base_text_inputs, tokenizer)
                        )
                    if file_source in {"oracle"}:
                        instance["file_contents"] = ingest_files(
                            get_oracle_filenames(instance)
                        )
                    elif file_source in {"bm25"}:
                        instance["file_contents"] = ingest_files(
                            [x["docid"] for x in instance["hits"]]
                        )
                    elif file_source in {"all"}:
                        instance["file_contents"] = ingest_directory_contents(
                            cm.repo_path
                        )
                    elif file_source in {"none"}:
                        instance["file_contents"] = dict()
                    else:
                        raise ValueError(f"Invalid file source {file_source}")
                    
                    if prompt_style == "get_function_from_patch":
                        functions = find_modified_functions(instance["patch"], instance["file_contents"])
                        if len(functions) == 0:
                            print(f"Warning: There is no function for {instance_id}.")
                        input_instances[instance_id]["functions"] = functions
                        continue
                    
                    if max_context_len is not None:
                        cur_input_len = base_text_input_length
                        include_files = list()
                        for filename in [x["docid"] for x in instance["hits"]]:
                            content = make_code_text(
                                {filename: instance["file_contents"][filename]}
                            )
                            if tokenizer_name in {"llama"}:
                                tokens = tokenizer_func("\n" + content, tokenizer)
                                idx = tokens.index(13)
                                assert (
                                    idx <= 2
                                ), "Expected newline token id (13) to be one of the first three tokens"
                                tokens = tokens[idx + 1 :]  # remove newline tokens
                            else:
                                tokens = tokenizer_func(content, tokenizer)
                            if cur_input_len + len(tokens) < max_context_len:
                                include_files.append(filename)
                                cur_input_len += len(tokens)
                        instance["file_contents"] = {
                            filename: instance["file_contents"][filename]
                            for filename in include_files
                        }

                    # performance related test
                    if "efficiency_test" in instance:
                        instance["efficiency_test_contents"] = get_test_contents(instance)
                    input_instances[instance_id]["text_inputs"] = PROMPT_FUNCTIONS[
                        prompt_style
                    ](instance)
                    input_instances[instance_id]["file_contents"] = json.dumps(instance["file_contents"])
            except Exception as e:
                print(f"Failed on instance {instance_id}", e)
                traceback.print_exc()
                input_instances[instance_id]["text_inputs"] = None
            finally:
                # if AutoContextManager fails to exit properly future exits will return the wrong directory
                os.chdir(orig_dir)
    os.chdir(orig_dir)
