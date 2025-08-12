from __future__ import annotations

from collections import defaultdict
import json
import logging
import re
import requests
import time
import os
from fastcore.xtras import obj2dict

from bs4 import BeautifulSoup
from ghapi.core import GhApi
from fastcore.net import HTTP404NotFoundError, HTTP403ForbiddenError
from typing import Callable, Iterator, Optional
from unidiff import PatchSet

from collect.request_ import request_

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Repo:
    def __init__(self, owner: str, name: str, token: Optional[str] = None, cutoff_date: str = None, need_workflow: bool = False):
        """
        Init to retrieve target repository and create ghapi tool

        Args:
            owner (str): owner of target repository
            name (str): name of target repository
            token (str): github token
        """
        self.owner = owner
        self.name = name
        self.token = token
        self.api = GhApi(token=token)
        self.repo = self.call_api(self.api.repos.get, owner=owner, repo=name)
        if need_workflow:
            workflow_path = f"../ReCE/{name}/workflows/{name}-workflows-{cutoff_date}.json" if cutoff_date!=None else f"../ReCE/{name}/workflows/{name}-workflows.json"
            if os.path.exists(workflow_path):
                with open(workflow_path, "r") as f:
                    self.workflow_runs = json.load(f)
            else:
                logger.info(f"Get workflow runs for {self.owner}/{self.name}")
                self.workflow_runs = self.log_all_workflows(cutoff_date)
                with open(workflow_path, "w") as f:
                    json.dump(obj2dict(self.workflow_runs), f)
                raise HTTP404NotFoundError("stop")


    def call_api(self, func: Callable, **kwargs) -> dict|None:
        """
        API call wrapper with rate limit handling (checks every 5 minutes if rate limit is reset)

        Args:
            func (callable): API function to call
            **kwargs: keyword arguments to pass to API function
        Return:
            values (dict): response object of `func`
        """
        while True:
            try:
                values = func(**kwargs)
                return values
            except HTTP403ForbiddenError as e:
                while True:
                    rl = self.api.rate_limit.get()
                    logger.info(
                        f"[{self.owner}/{self.name}] Rate limit exceeded for token {self.token[:10]}, "
                        f"waiting for 5 minutes, remaining calls: {rl.resources.core.remaining}"
                    )
                    if rl.resources.core.remaining > 0:
                        break
                    time.sleep(60 * 5)
            except HTTP404NotFoundError as e:
                logger.info(f"[{self.owner}/{self.name}] Resource not found {kwargs}")
                return None

    def extract_resolved_issues(self, pull: dict) -> list[str]:
        """
        Extract list of issues referenced by a PR

        Args:
            pull (dict): PR dictionary object from GitHub
        Return:
            resolved_issues (list): list of issue numbers referenced by PR
        """
        # Define 1. issue number regex pattern 2. comment regex pattern 3. keywords
        issues_pat = re.compile(r"(\w+)\s+\#(\d+)")
        comments_pat = re.compile(r"(?s)<!--.*?-->")
        keywords = {
            "close",
            "closes",
            "closed",
            "fix",
            "fixes",
            "fixed",
            "resolve",
            "resolves",
            "resolved",
        }

        # Construct text to search over for issue numbers from PR body and commit messages
        text = pull.title if pull.title else ""
        text += "\n" + (pull.body if pull.body else "")
        commits = self.get_all_loop(
            self.api.pulls.list_commits, pull_number=pull.number, quiet=True
        )
        commit_messages = [commit.commit.message for commit in commits]
        commit_text = "\n".join(commit_messages) if commit_messages else ""
        text += "\n" + commit_text
        # Remove comments from text
        text = comments_pat.sub("", text)
        # Look for issue numbers in text via scraping <keyword, number> patterns
        references = dict(issues_pat.findall(text))
        resolved_issues = list()
        if references:
            for word, issue_num in references.items():
                if word.lower() in keywords:
                    resolved_issues.append(issue_num)
        return resolved_issues

    def get_all_loop(
        self,
        func: Callable,
        per_page: int = 100,
        num_pages: Optional[int] = None,
        quiet: bool = False,
        **kwargs,
    ) -> Iterator:
        """
        Return all values from a paginated API endpoint.
        
        Args:
            func (callable): API function to call
            per_page (int): number of values to return per page
            num_pages (int): number of pages to return
            quiet (bool): whether to print progress
            **kwargs: keyword arguments to pass to API function
        """
        page = 1
        args = {
            "owner": self.owner,
            "repo": self.name,
            "per_page": per_page,
            **kwargs,
        }
        while True:
            try:
                # Get values from API call
                values = func(**args, page=page)
                yield from values
                if len(values) == 0:
                    break
                if not quiet:
                    rl = self.api.rate_limit.get()
                    logger.info(
                        f"[{self.owner}/{self.name}] Processed page {page} ({per_page} values per page). "
                        f"Remaining calls: {rl.resources.core.remaining}"
                    )
                if num_pages is not None and page >= num_pages:
                    break
                page += 1
            except Exception as e:
                # Rate limit handling
                logger.error(
                    f"[{self.owner}/{self.name}] Error processing page {page} "
                    f"w/ token {self.token[:10]} - {e}"
                )
                while True:
                    rl = self.api.rate_limit.get()
                    if rl.resources.core.remaining > 0:
                        break
                    logger.info(
                        f"[{self.owner}/{self.name}] Waiting for rate limit reset "
                        f"for token {self.token[:10]}, checking again in 5 minutes"
                    )
                    time.sleep(60 * 5)
        if not quiet:
            logger.info(
                f"[{self.owner}/{self.name}] Processed {(page-1)*per_page + len(values)} values"
            )

    def get_all_issues(
        self,
        per_page: int = 100,
        num_pages: Optional[int] = None,
        direction: str = "desc",
        sort: str = "created",
        state: str = "closed",
        quiet: bool = False,
    ) -> Iterator:
        """
        Wrapper for API call to get all issues from repo

        Args:
            per_page (int): number of issues to return per page
            num_pages (int): number of pages to return
            direction (str): direction to sort issues
            sort (str): field to sort issues by
            state (str): state of issues to look for
            quiet (bool): whether to print progress
        """
        issues = self.get_all_loop(
            self.api.issues.list_for_repo,
            num_pages=num_pages,
            per_page=per_page,
            direction=direction,
            sort=sort,
            state=state,
            quiet=quiet,
        )
        return issues

    def get_all_pulls(
        self,
        per_page: int = 100,
        num_pages: Optional[int] = None,
        direction: str = "desc",
        sort: str = "created",
        state: str = "closed",
        quiet: bool = False,
    ) -> Iterator:
        """
        Wrapper for API call to get all PRs from repo

        Args:
            per_page (int): number of PRs to return per page
            num_pages (int): number of pages to return
            direction (str): direction to sort PRs
            sort (str): field to sort PRs by
            state (str): state of PRs to look for
            quiet (bool): whether to print progress
        """
        pulls = self.get_all_loop(
            self.api.pulls.list,
            num_pages=num_pages,
            direction=direction,
            per_page=per_page,
            sort=sort,
            state=state,
            quiet=quiet,
        )
        return pulls

        
    def get_all_workflows(self, per_page: int = 100, num_pages: Optional[int] = None, quiet: bool = False):
        """
        Wrapper for API call to get all workflows from repo

        Args:
            per_page (int): number of workflows to return per page
            num_pages (int): number of pages to return
            quiet (bool): whether to print progress
        """
        def list_workflow_runs_for_repo(**kwargs):
            return self.api.actions.list_workflow_runs_for_repo(
                **kwargs
            )['workflow_runs']
        workflows = self.get_all_loop(
            # self.api.actions.list_workflow_runs_for_repo,
            list_workflow_runs_for_repo,
            num_pages=num_pages,
            per_page=per_page,
            quiet=quiet,
        )
        return workflows

    def log_all_workflows(
        self, cutoff_date: str = None,
    ):
        cutoff_date = datetime.strptime(cutoff_date, "%Y%m%d") \
            .strftime("%Y-%m-%dT%H:%M:%SZ") \
            if cutoff_date is not None else None
        workflows = defaultdict(list)
        for i_pull, workflow in enumerate(self.get_all_workflows()):
            workflows[workflow['head_sha']].append(workflow)
            if cutoff_date is not None and workflow.created_at < cutoff_date:
                break
        return workflows


def extract_problem_statement_and_hints(pull: dict, repo: Repo) -> tuple[str, str]:
    """
    Extract problem statement from issues associated with a pull request

    Args:
        pull (dict): PR dictionary object from GitHub
        repo (Repo): Repo object
    Return:
        text (str): problem statement
        hints (str): hints
    """
    if repo.name == "django":
        return extract_problem_statement_and_hints_django(pull, repo)
    text = ""
    all_hint_texts = list()
    for issue_number in pull["resolved_issues"]:
        issue = repo.call_api(
            repo.api.issues.get,
            owner=repo.owner,
            repo=repo.name,
            issue_number=issue_number,
        )
        if issue is None:
            continue
        title = issue.title if issue.title else ""
        body = issue.body if issue.body else ""
        text += f"{title}\n{body}\n"
        issue_number = issue.number
        hint_texts = _extract_hints(pull, repo, issue_number)
        hint_text = "\n".join(hint_texts)
        all_hint_texts.append(hint_text)
    return text, "\n".join(all_hint_texts) if all_hint_texts else ""


def _extract_hints(pull: dict, repo: Repo, issue_number: int) -> list[str]:
    """
    Extract hints from comments associated with a pull request (before first commit)

    Args:
        pull (dict): PR dictionary object from GitHub
        repo (Repo): Repo object
        issue_number (int): issue number
    Return:
        hints (list): list of hints
    """
    # Get all commits in PR
    commits = repo.get_all_loop(
        repo.api.pulls.list_commits, pull_number=pull["number"], quiet=True
    )
    commits = list(commits)
    if len(commits) == 0:
        # If there are no comments, return no hints
        return []
    # Get time of first commit in PR
    commit_time = commits[0].commit.author.date  # str
    commit_time = time.mktime(time.strptime(commit_time, "%Y-%m-%dT%H:%M:%SZ"))
    # Get all comments in PR
    all_comments = repo.get_all_loop(
        repo.api.issues.list_comments, issue_number=issue_number, quiet=True
    )
    all_comments = list(all_comments)
    # Iterate through all comments, only keep comments created before first commit
    comments = list()
    for comment in all_comments:
        comment_time = time.mktime(
            time.strptime(comment.updated_at, "%Y-%m-%dT%H:%M:%SZ")
        )  # use updated_at instead of created_at
        if comment_time < commit_time:
            comments.append(comment)
        else:
            break
        # only include information available before the first commit was created
    # Keep text from comments
    comments = [comment.body for comment in comments]
    return comments


def extract_patches(pull: dict, repo: Repo) -> tuple[str, str]:
    """
    Get patch and test patch from PR

    Args:
        pull (dict): PR dictionary object from GitHub
        repo (Repo): Repo object
    Return:
        patch_change_str (str): gold patch
        patch_test_str (str): test patch
    """
    patch = request_(pull["diff_url"]).text
    patch_test = ""
    patch_fix  = ""
    for hunk in PatchSet(patch):
        if any(
            test_word in hunk.path for test_word in
            ['test', 'tests', 'e2e', 'testing']
        ):
            patch_test += str(hunk)
        else:
            patch_fix += str(hunk)
    return patch_fix, patch_test


### MARK: Repo Specific Parsing Functions ###
def extract_problem_statement_and_hints_django(
    pull: dict, repo: Repo
) -> tuple[str, list[str]]:
    """
    Get problem statement and hints from issues associated with a pull request

    Args:
        pull (dict): PR dictionary object from GitHub
        repo (Repo): Repo object
    Return:
        text (str): problem statement
        hints (str): hints
    """
    text = ""
    all_hints_text = list()
    for issue_number in pull["resolved_issues"]:
        url = f"https://code.djangoproject.com/ticket/{issue_number}"
        resp = requests.get(url)
        if resp.status_code != 200:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")

        # Get problem statement (title + body)
        issue_desc = soup.find("div", {"id": "ticket"})
        title = issue_desc.find("h1", class_="searchable").get_text()
        title = re.sub(r"\s+", " ", title).strip()
        body = issue_desc.find("div", class_="description").get_text()
        body = re.sub(r"\n+", "\n", body)
        body = re.sub(r"    ", "\t", body)
        body = re.sub(r"[ ]{2,}", " ", body).strip()
        text += f"{title}\n{body}\n"

        # Get time of first commit in PR
        commits = repo.get_all_loop(
            repo.api.pulls.list_commits, pull_number=pull["number"], quiet=True
        )
        commits = list(commits)
        if len(commits) == 0:
            continue
        commit_time = commits[0].commit.author.date
        commit_time = time.mktime(time.strptime(commit_time, "%Y-%m-%dT%H:%M:%SZ"))

        # Get all comments before first commit
        comments_html = soup.find("div", {"id": "changelog"})
        div_blocks = comments_html.find_all("div", class_="change")
        # Loop through each div block
        for div_block in div_blocks:
            # Find the comment text and timestamp
            comment_resp = div_block.find("div", class_="comment")
            timestamp_resp = div_block.find("a", class_="timeline")
            if comment_resp is None or timestamp_resp is None:
                continue

            comment_text = re.sub(r"\s+", " ", comment_resp.text).strip()
            timestamp = timestamp_resp["title"]
            if timestamp.startswith("See timeline at "):
                timestamp = timestamp[len("See timeline at ") :]
            if "/" in timestamp:
                timestamp = time.mktime(time.strptime(timestamp, "%m/%d/%y %H:%M:%S"))
            elif "," in timestamp:
                timestamp = time.mktime(time.strptime(timestamp, "%b %d, %Y, %I:%M:%S %p"))
            else:
                raise ValueError(f"Timestamp format not recognized: {timestamp}")

            # Append the comment and timestamp as a tuple to the comments list
            if timestamp < commit_time:
                all_hints_text.append((comment_text, timestamp))

    return text, all_hints_text

def get_workflow_runs(repo:Repo, commit_sha: str) -> list:  
    """Fetch the workflow runs for a specific commit."""  
    return repo.workflow_runs[commit_sha] 
  

from datetime import datetime  

def get_workflow_run_logs(repo: Repo, run_id: int) -> str:  
    """Download logs for a specific workflow run."""  
    log_url = f"https://api.github.com/repos/{repo.owner}/{repo.name}/actions/runs/{run_id}/jobs"  

    response = request_(log_url, headers={'Authorization': f'token {repo.token}'})
    # response = request_(log_url)
    # try:
    if response.status_code == 404:
        return "failure"
    response.raise_for_status()  

    def calculate_time_difference(start_time: str, end_time: str) -> float:  
        """Calculate the difference in minutes between two timestamps."""  
        # Parse the ISO 8601 formatted date strings into datetime objects  
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))  
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))  
    
        # Calculate the difference between the two datetime objects  
        time_difference = end_dt - start_dt  
    
        # Return the difference in minutes  
        return time_difference.total_seconds() / 60  
    
    run_duration = {}
    for job in response.json().get('jobs', []):  
        # print(f"{job['workflow_name']}/{job['name']}")
        # if job['name'] == 'ubuntu-22.04 actions-310.yaml':
        # if "310" in job['name'] and 'ubuntu' in job["name"] and ('latest' in job['name'] or '22.04' in job['name']):
        # if job['name'] == 'ubuntu-latest actions-310.yaml' or job['name'] == 'ubuntu-22.04 actions-310.yaml':
        # if job['name'] == 'Python 3.11 on ubuntu-22.04':
        # if 'Python 3.11 (Docutils 0.20)' == job['name']:
        if "ubuntu" in job['name']:
            job_name = f"{job['workflow_name']}/{job['name']}"
            if job['conclusion'] != 'success':
                run_duration[job_name]="failure"
                continue
            run_duration[job_name]=None
            
            # # Store the job logs
            # run_logs[job_name] = log_response.text
            # print(log_response.text)
            # raise ValueError("Not implemented")
    if all(value == 'failure' for value in run_duration.values()):
        run_duration = "failure"
  
    return run_duration  
  
  
def get_inference_time_from_actions(repo: Repo, commit_sha: str):  
    """Get inference time for a commit using GitHub Actions."""  
    try:
        workflow_runs = get_workflow_runs(repo, commit_sha) 
    except:
        print(f"There is no workflow for {commit_sha}")
        return "failure"

    # Get all run['conclusion'] == 'success'
    run_durations = {} 
    for run in workflow_runs:  
        if run['name'] == 'Unit Tests':
        # if run['name'] == "Tests":
        # if run['name'] == 'CI':
            # if run['conclusion'] != 'success' and run['conclusion'] != 'skipped':
            #     return "failure"
            # elif run['conclusion'] == 'success':
            #     # print(run['name'])
            run_duration = get_workflow_run_logs(repo, run['id'])  
            if type(run_duration) == dict:
                run_durations.update(run_duration)
            else: # failure
                return run_duration
    if len(run_durations) == 0:
        print(f"No success run found in {commit_sha}")
    return run_durations

