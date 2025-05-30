import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict

class GitHubStatsAnalyzerOnline:
    def __init__(self, username: str, token: str):
        self.username = username
        self.token = token
        self.api_url = "https://api.github.com"
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        # Obter lista de repositórios públicos do usuário
        self.repos = self._get_user_repositories()

    def _get_user_repositories(self):
        repos = []
        page = 1
        while True:
            url = f"{self.api_url}/users/{self.username}/repos?per_page=100&page={page}"
            resp = requests.get(url, headers=self.headers)
            data = resp.json()
            if not isinstance(data, list) or not data:
                break
            repos.extend(data)
            page += 1
        return repos

    def _get_commit_stats(self, repo_full_name):
        all_commits = []
        page = 1
        per_page = 100

        while True:
            url = f"{self.api_url}/repos/{repo_full_name}/commits"
            params = {
                'author': self.username,
                'since': (datetime.now() - timedelta(days=365)).isoformat(),
                'per_page': per_page,
                'page': page
            }
            resp = requests.get(url, headers=self.headers, params=params)
            data = resp.json()

            # Trata repositório vazio ou erro da API
            if isinstance(data, dict) and data.get('message'):
                msg = data['message'].lower()
                if 'empty' in msg or 'not found' in msg or 'error' in msg:
                    return {'lines_changed': 0,
                            'monthly_contributions': {},
                            'consecutive_contribution_streak': 0,
                            'commit_count': 0}
                break

            if not isinstance(data, list) or not data:
                break

            all_commits.extend(data)
            if len(data) < per_page:
                break
            page += 1

        total_lines = 0
        monthly_contrib = defaultdict(int)
        weeks = set()

        for commit in all_commits:
            info = commit.get('commit', {})
            author = info.get('author', {})
            date_str = author.get('date')
            if not date_str:
                continue
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue

            monthly_contrib[date_obj.strftime('%Y-%m')] += 1
            weeks.add(date_obj.strftime('%Y-%U'))

            # Estatísticas de adições/deleções
            commit_url = commit.get('url')
            if commit_url:
                detail = requests.get(commit_url, headers=self.headers).json()
                stats = detail.get('stats', {})
                total_lines += stats.get('additions', 0) + stats.get('deletions', 0)

        return {
            'lines_changed': total_lines,
            'monthly_contributions': dict(monthly_contrib),
            'consecutive_contribution_streak': self._compute_weekly_streak(weeks),
            'commit_count': len(all_commits)
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
            is_owner = owner.lower() == self.username.lower()

            stats = self._get_commit_stats(full_name)

            results[name] = {
                'repo_name': name,
                'is_owner': is_owner,
                'has_write_permission': not repo.get('fork', False),
                **stats
            }
        return results

    def get_results_as_json(self) -> str:
        """
        Retorna um JSON com todos os dados coletados nos repositórios.
        """
        data = self.analyze_all()
        return json.dumps(data, indent=2)

# Exemplo de uso
def stats_analyzer(user: str, token: str):

    analyzer = GitHubStatsAnalyzerOnline(user, token)
    print(analyzer.get_results_as_json())
    return analyzer.get_results_as_json()