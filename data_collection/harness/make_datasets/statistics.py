import os
import re
import json
from numpy import std, mean, sqrt
import math
from harness.utils import filter_outliers, find_max_significant_improvement

def count_files_and_lines(directory):
    """
    Count the number of files and total lines in a directory (recursively)
    
    Args:
        directory (str): Path to the target directory
    
    Returns:
        tuple: (file_count, total_lines)
    """
    file_count = 0
    total_lines = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.startswith("test_"):
                continue
            if not file.endswith(".py"):
                continue
            file_path = os.path.join(root, file)
            
            # Skip if it's not a file (e.g., symlink)
            if not os.path.isfile(file_path):
                continue
                
            file_count += 1
            
            try:
                # Open with 'r' mode and universal newline support
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Count lines using generator expression for memory efficiency
                    lines = sum(1 for line in f)
                    total_lines += lines
            except Exception as e:
                # Skip files that can't be read (e.g., binary files)
                continue
                
    return file_count, total_lines


def analyze_patch(patch_content):
    """Analyze git patch content and return editing metrics.
    
    Args:
        patch_content: String containing git patch content
        
    Returns:
        Dictionary with lines_edited, files_edited, functions_edited
    """
    # Split patch into individual file diffs
    file_diffs = re.findall(
        r'^diff --git .*?(?=^diff --git |\Z)', 
        patch_content, 
        flags=re.DOTALL | re.MULTILINE
    )
    
    files_edited = len(file_diffs)
    lines_edited = 0
    edited_functions = list()

    for file_diff in file_diffs:
        # # Extract all diff hunks (code blocks) in the file
        # hunks = re.findall(
        #     r'^@@ .*?(?=^@@ |\Z)', 
        #     file_diff, 
        #     flags=re.MULTILINE | re.DOTALL
        # )

        # func_in_file = set()
        
        # for hunk in hunks:
        #     lines = hunk.split('\n')
        #     if not lines:
        #         continue

        #     # Extract context from hunk header
        #     header = lines[0]
        #     context = header.split(' @@ ')[-1].strip()
            
        #     # Find function name from context
        #     if match := re.search(r'def (\w+)\(', context):
        #         func_in_file.add(match.group(1))
            
        #     # Process each line in the hunk
        #     for line in lines[1:]:  # Skip header line
        #         # Count additions/removals
        #         if line.startswith('+') or line.startswith('-'):
        #             lines_edited += 1
        #             # Check for function definitions in changed lines
        #             code_line = line[1:].lstrip()  # Remove +/- and whitespace
        #             if func_match := re.search(r'^def (\w+)\(', code_line):
        #                 func_in_file.add(func_match.group(1))
        
        flag_name = None # e.g. @@ -203,9 +203,7 @@ def is_clean(self) -> bool:
        function_name = None
        function_has_been_changed = False
        first_line = False
        function_name_changed = []
        func_pattern = re.compile(r'def\s+([\w_]+)\s*\(')
        for line in file_diff.split("\n"):
            if line.startswith("diff --git "): 
                continue

            func_match = re.search(func_pattern, line)
            if line.startswith("+++") or line.startswith("---"):
                continue
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
                lines_edited += 1

        if function_name != None and function_has_been_changed:
            function_name_changed.append(function_name)

        edited_functions.extend(list(set(function_name_changed)))

    return lines_edited, files_edited,len(edited_functions)


def coefficient_of_variation(data):
    mean = sum(data) / len(data)
    squared_diff = [(x - mean)**2 for x in data]
    std_dev = (sum(squared_diff) / len(data))**0.5
    cv = (std_dev / mean) * 100
    return cv

def caculate_cohen_d(x,y):
    nx = len(x)
    ny = len(y)
    dof = nx + ny - 2
    return (mean(x) - mean(y)) / sqrt(((nx-1)*std(x, ddof=1) ** 2 + (ny-1)*std(y, ddof=1) ** 2) / dof)

def count_test(duration_changes, efficiency_test):
    # Find common keys present in all three dictionaries
    common_keys = set(duration_changes[0].keys())
    for d in duration_changes[1:]:
        common_keys &= set(d.keys())
    common_keys = sorted(common_keys)  # Sort for consistent ordering
    
    # Extract inner dictionary keys (e.g., 'base', 'head')
    sample_key = next(iter(duration_changes[0].values()))  # Get first inner dict as sample
    inner_keys = list(sample_key.keys())
    
    # Create one table per inner key
    tables = {}
    for inner_key in inner_keys:
        # Build list of lists containing only values
        table_data = {key:
            [
                duration_changes[0][key][inner_key],  # Dict1 value
                duration_changes[1][key][inner_key],  # Dict2 value
                duration_changes[2][key][inner_key]   # Dict3 value
            ]
            for key in common_keys
        }
        
        tables[inner_key] = table_data

    base_runtimes_list = []
    head_runtimes_list = []
    cv_base_list = []
    cv_head_list = []
    cohen_d_list = []
    ratio_list = []
    for key in common_keys:
        if key not in efficiency_test:
            continue
        base_runtimes = tables["base"][key]
        base_runtimes = filter_outliers(base_runtimes)
        base_runtimes_list.extend(base_runtimes)
        cv_base = coefficient_of_variation(base_runtimes)
        cv_base_list.append(cv_base)
        head_runtimes = tables["head"][key]
        head_runtimes = filter_outliers(head_runtimes)
        head_runtimes_list.extend(head_runtimes)
        cv_head = coefficient_of_variation(head_runtimes)
        cv_head_list.append(cv_head)
        
        cohen_d_ = caculate_cohen_d(base_runtimes, head_runtimes)
        if not math.isinf(cohen_d_):
            cohen_d_list.append(cohen_d_)

        sig = find_max_significant_improvement(head_runtimes, base_runtimes)
        # avg_A = sum(base_runtimes) / len(base_runtimes)
        # avg_B = sum(head_runtimes) / len(head_runtimes)
        # ratio = (avg_B - avg_A) / avg_A
        ratio_list.append(sig)
    return base_runtimes_list, head_runtimes_list, cv_base_list, cv_head_list, cohen_d_list, ratio_list


def count_all(instance):
    codebase_files, codebase_lines = count_files_and_lines(".")
    patch_line, patch_file, patch_func = analyze_patch(instance["patch"])
    efficiency_test = eval(instance["efficiency_test"])
    duration_changes = json.loads(instance["duration_changes"])
    test_num = len(efficiency_test)
    base_runtimes_list, head_runtimes_list, cv_base_list, cv_head_list, cohen_d_list, ratio_list = count_test(duration_changes,efficiency_test)
    return {
        "codebase_files": codebase_files,
        "codebase_lines": codebase_lines,
        "patch_line": patch_line,
        "patch_file": patch_file,
        "patch_func": patch_func,
        "test_num": test_num,
        "base_runtimes_list": base_runtimes_list,
        "head_runtimes_list": head_runtimes_list,
        "cv_base_list": cv_base_list,
        "cv_head_list": cv_head_list,
        "cohen_d_list": cohen_d_list,
        "ratio_list": ratio_list,
    }


if __name__ == "__main__":
    print(count_files_and_lines("."))
    patch = '''diff --git a/src/sqlfluff/cli/commands.py b/src/sqlfluff/cli/commands.py
--- a/src/sqlfluff/cli/commands.py
+++ b/src/sqlfluff/cli/commands.py
@@ -44,6 +44,7 @@
dialect_selector,
dialect_readout,
)
+from sqlfluff.core.linter import LintingResult
from sqlfluff.core.config import progress_bar_configuration

from sqlfluff.core.enums import FormatType, Color
@@ -691,12 +692,16 @@ def lint(
sys.exit(EXIT_SUCCESS)


-def do_fixes(lnt, result, formatter=None, **kwargs):
+def do_fixes(
+ result: LintingResult, formatter: Optional[OutputStreamFormatter] = None, **kwargs
+):
"""Actually do the fixes."""
- click.echo("Persisting Changes...")
+ if formatter and formatter.verbosity >= 0:
+ click.echo("Persisting Changes...")
res = result.persist_changes(formatter=formatter, **kwargs)
if all(res.values()):
- click.echo("Done. Please check your files to confirm.")
+ if formatter and formatter.verbosity >= 0:
+ click.echo("Done. Please check your files to confirm.")
return True
# If some failed then return false
click.echo(
@@ -708,7 +713,7 @@ def do_fixes(lnt, result, formatter=None, **kwargs):
return False # pragma: no cover


-def _stdin_fix(linter, formatter, fix_even_unparsable):
+def _stdin_fix(linter: Linter, formatter, fix_even_unparsable):
"""Handle fixing from stdin."""
exit_code = EXIT_SUCCESS
stdin = sys.stdin.read()
@@ -751,7 +756,7 @@ def _stdin_fix(linter, formatter, fix_even_unparsable):


def _paths_fix(
- linter,
+ linter: Linter,
formatter,
paths,
processes,
@@ -765,11 +770,12 @@ def _paths_fix(
):
"""Handle fixing from paths."""
# Lint the paths (not with the fix argument at this stage), outputting as we go.
- click.echo("==== finding fixable violations ====")
+ if formatter.verbosity >= 0:
+ click.echo("==== finding fixable violations ====")
exit_code = EXIT_SUCCESS

with PathAndUserErrorHandler(formatter):
- result = linter.lint_paths(
+ result: LintingResult = linter.lint_paths(
paths,
fix=True,
ignore_non_existent_files=False,
@@ -781,20 +787,18 @@ def _paths_fix(

# NB: We filter to linting violations here, because they're
# the only ones which can be potentially fixed.
- if result.num_violations(types=SQLLintError, fixable=True) > 0:
- click.echo("==== fixing violations ====")
- click.echo(
- f"{result.num_violations(types=SQLLintError, fixable=True)} fixable "
- "linting violations found"
- )
+ num_fixable = result.num_violations(types=SQLLintError, fixable=True)
+ if num_fixable > 0:
+ if formatter.verbosity >= 0:
+ click.echo("==== fixing violations ====")
+ click.echo(f"{num_fixable} " "fixable linting violations found")
if force:
- if warn_force:
+ if warn_force and formatter.verbosity >= 0:
click.echo(
f"{formatter.colorize('FORCE MODE', Color.red)}: "
"Attempting fixes..."
)
success = do_fixes(
- linter,
result,
formatter,
types=SQLLintError,
@@ -809,9 +813,9 @@ def _paths_fix(
c = click.getchar().lower()
click.echo("...")
if c in ("y", "\r", "\n"):
- click.echo("Attempting fixes...")
+ if formatter.verbosity >= 0:
+ click.echo("Attempting fixes...")
success = do_fixes(
- linter,
result,
formatter,
types=SQLLintError,
@@ -829,8 +833,9 @@ def _paths_fix(
click.echo("Aborting...")
exit_code = EXIT_FAIL
else:
- click.echo("==== no fixable linting violations found ====")
- formatter.completion_message()
+ if formatter.verbosity >= 0:
+ click.echo("==== no fixable linting violations found ====")
+ formatter.completion_message()

error_types = [
(
@@ -841,7 +846,7 @@ def _paths_fix(
]
for num_violations_kwargs, message_format, error_level in error_types:
num_violations = result.num_violations(**num_violations_kwargs)
- if num_violations > 0:
+ if num_violations > 0 and formatter.verbosity >= 0:
click.echo(message_format.format(num_violations))
exit_code = max(exit_code, error_level)

@@ -880,10 +885,20 @@ def _paths_fix(
"--force",
is_flag=True,
help=(
- "skip the confirmation prompt and go straight to applying "
+ "Skip the confirmation prompt and go straight to applying "
"fixes. **Use this with caution.**"
),
)
+@click.option(
+ "-q",
+ "--quiet",
+ is_flag=True,
+ help=(
+ "Reduces the amount of output to stdout to a minimal level. "
+ "This is effectively the opposite of -v. NOTE: It will only "
+ "take effect if -f/--force is also set."
+ ),
+)
@click.option(
"-x",
"--fixed-suffix",
@@ -913,6 +928,7 @@ def fix(
force: bool,
paths: Tuple[str],
bench: bool = False,
+ quiet: bool = False,
fixed_suffix: str = "",
logger: Optional[logging.Logger] = None,
processes: Optional[int] = None,
@@ -932,6 +948,13 @@ def fix(
"""
# some quick checks
fixing_stdin = ("-",) == paths
+ if quiet:
+ if kwargs["verbose"]:
+ click.echo(
+ "ERROR: The --quiet flag can only be used if --verbose is not set.",
+ )
+ sys.exit(EXIT_ERROR)
+ kwargs["verbose"] = -1

config = get_config(
extra_config_path, ignore_local_config, require_dialect=False, **kwargs
diff --git a/src/sqlfluff/cli/formatters.py b/src/sqlfluff/cli/formatters.py
--- a/src/sqlfluff/cli/formatters.py
+++ b/src/sqlfluff/cli/formatters.py
@@ -94,7 +94,7 @@ def __init__(
):
self._output_stream = output_stream
self.plain_output = self.should_produce_plain_output(nocolor)
- self._verbosity = verbosity
+ self.verbosity = verbosity
self._filter_empty = filter_empty
self.output_line_length = output_line_length

@@ -116,13 +116,13 @@ def _format_config(self, linter: Linter) -> str:
"""Format the config of a `Linter`."""
text_buffer = StringIO()
# Only show version information if verbosity is high enough
- if self._verbosity > 0:
+ if self.verbosity > 0:
text_buffer.write("==== sqlfluff ====\n")
config_content = [
("sqlfluff", get_package_version()),
("python", get_python_version()),
("implementation", get_python_implementation()),
- ("verbosity", self._verbosity),
+ ("verbosity", self.verbosity),
]
if linter.dialect:
config_content.append(("dialect", linter.dialect.name))
@@ -138,7 +138,7 @@ def _format_config(self, linter: Linter) -> str:
col_width=41,
)
)
- if self._verbosity > 1:
+ if self.verbosity > 1:
text_buffer.write("\n== Raw Config:\n")
text_buffer.write(self.format_config_vals(linter.config.iter_vals()))
return text_buffer.getvalue()
@@ -150,7 +150,7 @@ def dispatch_config(self, linter: Linter) -> None:
def dispatch_persist_filename(self, filename, result):
"""Dispatch filenames during a persist operation."""
# Only show the skip records at higher levels of verbosity
- if self._verbosity >= 2 or result != "SKIP":
+ if self.verbosity >= 2 or result != "SKIP":
self._dispatch(self.format_filename(filename=filename, success=result))

def _format_path(self, path: str) -> str:
@@ -159,14 +159,14 @@ def _format_path(self, path: str) -> str:

def dispatch_path(self, path: str) -> None:
"""Dispatch paths for display."""
- if self._verbosity > 0:
+ if self.verbosity > 0:
self._dispatch(self._format_path(path))

def dispatch_template_header(
self, fname: str, linter_config: FluffConfig, file_config: FluffConfig
) -> None:
"""Dispatch the header displayed before templating."""
- if self._verbosity > 1:
+ if self.verbosity > 1:
self._dispatch(self.format_filename(filename=fname, success="TEMPLATING"))
# This is where we output config diffs if they exist.
if file_config:
@@ -182,12 +182,12 @@ def dispatch_template_header(

def dispatch_parse_header(self, fname: str) -> None:
"""Dispatch the header displayed before parsing."""
- if self._verbosity > 1:
+ if self.verbosity > 1:
self._dispatch(self.format_filename(filename=fname, success="PARSING"))

def dispatch_lint_header(self, fname: str, rules: List[str]) -> None:
"""Dispatch the header displayed before linting."""
- if self._verbosity > 1:
+ if self.verbosity > 1:
self._dispatch(
self.format_filename(
filename=fname, success=f"LINTING ({', '.join(rules)})"
@@ -202,7 +202,7 @@ def dispatch_compilation_header(self, templater, message):

def dispatch_processing_header(self, processes: int) -> None:
"""Dispatch the header displayed before linting."""
- if self._verbosity > 0:
+ if self.verbosity > 0:
self._dispatch( # pragma: no cover
f"{self.colorize('effective configured processes: ', Color.lightgrey)} "
f"{processes}"
@@ -228,7 +228,7 @@ def _format_file_violations(
show = fails + warns > 0

# Only print the filename if it's either a failure or verbosity > 1
- if self._verbosity > 0 or show:
+ if self.verbosity > 0 or show:
text_buffer.write(self.format_filename(fname, success=fails == 0))
text_buffer.write("\n")

@@ -253,6 +253,8 @@ def dispatch_file_violations(
self, fname: str, linted_file: LintedFile, only_fixable: bool
) -> None:
"""Dispatch any violations found in a file."""
+ if self.verbosity < 0:
+ return
s = self._format_file_violations(
fname,
linted_file.get_violations(
@@ -392,10 +394,13 @@ def format_filename(
if isinstance(success, str):
status_string = success
else:
- status_string = self.colorize(
- success_text if success else "FAIL",
- Color.green if success else Color.red,
- )
+ status_string = success_text if success else "FAIL"
+
+ if status_string in ("PASS", "FIXED", success_text):
+ status_string = self.colorize(status_string, Color.green)
+ elif status_string in ("FAIL", "ERROR"):
+ status_string = self.colorize(status_string, Color.red)
+
return f"== [{self.colorize(filename, Color.lightgrey)}] {status_string}"

def format_violation(
diff --git a/src/sqlfluff/core/linter/linted_dir.py b/src/sqlfluff/core/linter/linted_dir.py
--- a/src/sqlfluff/core/linter/linted_dir.py
+++ b/src/sqlfluff/core/linter/linted_dir.py
@@ -117,7 +117,11 @@ def persist_changes(
for file in self.files:
if file.num_violations(fixable=True, **kwargs) > 0:
buffer[file.path] = file.persist_tree(suffix=fixed_file_suffix)
- result = buffer[file.path]
+ result: Union[bool, str]
+ if buffer[file.path] is True:
+ result = "FIXED"
+ else: # pragma: no cover
+ result = buffer[file.path]
else: # pragma: no cover TODO?
buffer[file.path] = True
result = "SKIP"'''
    print(analyze_patch(patch))