import requests
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

class GitHubStatsAnalyzerAllTime:
    def __init__(self, username: str, token: str):
        self.username = username
        self.token = token
        self.api_url = "https://api.github.com"
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.repos = self._get_user_repositories()

    def _get_user_repositories(self):
        repos = []
        page = 1
        while True:
            url = f"{self.api_url}/users/{self.username}/repos?per_page=100&page={page}"
            resp = requests.get(url, headers=self.headers)
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except (ValueError, json.JSONDecodeError):
                break
            if not isinstance(data, list) or not data:
                break
            repos.extend(data)
            page += 1
        return repos

    def _get_commit_stats(self, repo_full_name):
        url = f"{self.api_url}/repos/{repo_full_name}/stats/contributors"
        max_retries = 10
        for attempt in range(max_retries):
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 202:
                time.sleep(2)
                continue
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except (ValueError, json.JSONDecodeError):
                break
            if not isinstance(data, list) or not data:
                break

            user_stats = None
            for contributor in data:
                author = contributor.get('author')
                if author and author.get('login', '').lower() == self.username.lower():
                    user_stats = contributor
                    break

            if not user_stats:
                break

            total_lines = 0
            monthly_contrib = defaultdict(int)
            weeks_with_commits = set()
            total_commits = 0

            for week_info in user_stats.get('weeks', []):
                week_timestamp = week_info.get('w')
                additions = week_info.get('a', 0)
                deletions = week_info.get('d', 0)
                commits = week_info.get('c', 0)

                date_obj = datetime.utcfromtimestamp(week_timestamp)

                total_lines += additions + deletions
                month_key = date_obj.strftime('%Y-%m')
                monthly_contrib[month_key] += commits

                if commits > 0:
                    iso_week = date_obj.strftime('%Y-%U')
                    weeks_with_commits.add(iso_week)
                    total_commits += commits

            streak = self._compute_weekly_streak(weeks_with_commits)

            return {
                'Linhas_trocas': total_lines,
                'Contribuicoes_mensais': dict(monthly_contrib),
                'Streak_contribuicoes_consecutivas': streak,
                'Total_commits': total_commits
            }

        return {
            'Linhas_trocas': 0,
            'Contribuicoes_mensais': {},
            'Streak_contribuicoes_consecutivas': 0,
            'Total_commits': 0
        }

    def _compute_weekly_streak(self, weeks: set) -> int:
        week_list = sorted(weeks)
        max_streak = current_streak = 0
        last_week = None

        for week in week_list:
            if last_week is None:
                current_streak = 1
            else:
                y1, w1 = map(int, last_week.split('-'))
                y2, w2 = map(int, week.split('-'))
                if (y2 == y1 and w2 == w1 + 1) or (y2 == y1 + 1 and w2 == 0 and w1 == 52):
                    current_streak += 1
                else:
                    current_streak = 1
            max_streak = max(max_streak, current_streak)
            last_week = week

        return max_streak

    def analyze_all(self) -> dict:
        results = {}
        for repo in self.repos:
            name = repo['name']
            full_name = repo['full_name']
            owner = repo['owner']['login']
            eh_dono = owner.lower() == self.username.lower()
            stats = self._get_commit_stats(full_name)
            results[name] = {
                'Repositoria': name,
                'eh_dono': eh_dono,
                'Permissao_escritura': not repo.get('fork', False),
                **stats
            }
        return results

    def get_results_as_json(self) -> str:
        data = self.analyze_all()
        return json.dumps(data, indent=2)

    def get_aggregate_stats(self) -> dict:
        aggregate_lines = 0
        aggregate_commits = 0
        all_weeks_with_commits = set()

        for repo in self.repos:
            full_name = repo['full_name']
            url = f"{self.api_url}/repos/{full_name}/stats/contributors"
            max_retries = 10
            for attempt in range(max_retries):
                resp = requests.get(url, headers=self.headers)
                if resp.status_code == 202:
                    time.sleep(2)
                    continue
                if resp.status_code != 200:
                    break
                try:
                    data = resp.json()
                except (ValueError, json.JSONDecodeError):
                    break
                if not isinstance(data, list) or not data:
                    break

                user_stats = None
                for contributor in data:
                    author = contributor.get('author')
                    if author and author.get('login', '').lower() == self.username.lower():
                        user_stats = contributor
                        break
                if not user_stats:
                    break

                for week_info in user_stats.get('weeks', []):
                    week_timestamp = week_info.get('w')
                    additions = week_info.get('a', 0)
                    deletions = week_info.get('d', 0)
                    commits = week_info.get('c', 0)

                    date_obj = datetime.utcfromtimestamp(week_timestamp)
                    aggregate_lines += additions + deletions
                    aggregate_commits += commits
                    if commits > 0:
                        iso_week = date_obj.strftime('%Y-%U')
                        all_weeks_with_commits.add(iso_week)
                break

        aggregate_streak = self._compute_weekly_streak(all_weeks_with_commits)

        return {
            'Linhas_trocas': aggregate_lines,
            'Total_commits': aggregate_commits,
            'Streak_contribuicoes_consecutivas': aggregate_streak
        }

