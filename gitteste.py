import os
import subprocess
import json
import re
import time
import stat
import requests
import platform 
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import re
from typing import Dict, List, Tuple, Set, Optional, Union, Any
import configparser as cfgparser

config = cfgparser.ConfigParser()
config.read('config.ini')
username = config['github']['username']
token = config['github']['token']

class GitHubStatsAnalyzer:
    """
    Classe para analisar estatísticas de contribuição em repositórios Git
    usando PyDrill para processar os dados.
    """
    
    def __init__(self, repositories_path: str, username: str = None):
        """
        Inicializa o analisador de estatísticas do GitHub.
        
        Args:
            repositories_path: Caminho para a pasta que contém os repositórios a serem analisados
            username: Nome de usuário do GitHub a ser analisado (opcional)
        """
        self.repositories_path = repositories_path
        self.username = username
        self.repos = self._discover_repositories()
        self.results = {}
    
    def _discover_repositories(self) -> List[str]:
        """
        Descobre todos os repositórios Git no caminho fornecido.
        
        Returns:
            Lista de caminhos para repositórios Git
        """
        repos = []
        
        for root, dirs, _ in os.walk(self.repositories_path):
            if '.git' in dirs:
                repos.append(root)
        
        return repos
    
    def _run_git_command(self, repo_path: str, command: List[str]) -> str:
        """
        Executa um comando git no repositório especificado.
        
        Args:
            repo_path: Caminho para o repositório
            command: Lista com o comando git a ser executado
            
        Returns:
            Saída do comando git
        """
        full_command = ['git', '-C', repo_path] + command
        result = subprocess.run(full_command, capture_output=True, text=True)
        return result.stdout.strip()
    
    def _get_repository_owner(self, repo_path: str) -> str:
        """
        Obtém o nome do proprietário do repositório.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Nome do proprietário do repositório
        """
        remote_url = self._run_git_command(repo_path, ['remote', 'get-url', 'origin'])
        
        # Padrão para extrair o nome do proprietário de URLs do GitHub
        if 'github.com' in remote_url:
            match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', remote_url)
            if match:
                owner = match.group(1)
                repo_name = match.group(2)
                
                # Tenta obter o proprietário real usando a API do GitHub
                try:
                    response = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}")
                    if response.status_code == 200:
                        return response.json().get('owner', {}).get('login', owner)
                except:
                    pass
                
                return owner
        
        # Se não conseguir determinar o proprietário, retorna o nome de usuário local
        config_user = self._run_git_command(repo_path, ['config', 'user.name'])
        return config_user
    
    def _get_repository_name(self, repo_path: str) -> str:
        """
        Obtém o nome do repositório.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Nome do repositório
        """
        # Extrai o nome do repositório do caminho
        return os.path.basename(repo_path)
    
    def _get_repository_contributors(self, repo_path: str) -> Dict[str, int]:
        """
        Obtém todos os contribuidores do repositório e o número de commits.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Dicionário com contribuidores e número de commits
        """
        output = self._run_git_command(repo_path, ['shortlog', '-sne', 'HEAD'])
        contributors = {}
        
        for line in output.split('\n'):
            if not line.strip():
                continue
                
            parts = re.match(r'^\s*(\d+)\s+(.+?)\s+<(.+?)>$', line)
            if parts:
                commits, name, email = parts.groups()
                contributors[email] = int(commits)
        
        return contributors
    
    def _get_current_user_email(self, repo_path: str) -> str:
        """
        Obtém o email do usuário atual configurado no git.
        Se um username foi fornecido, busca o email deste usuário no histórico de commits.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Email do usuário atual ou do usuário especificado
        """
        if self.username:
            # Busca por commits do usuário especificado
            output = self._run_git_command(repo_path, ['log', '--all', '--format=%ae %an', '--author=' + self.username])
            
            if output:
                # Pega o primeiro email associado ao usuário
                first_line = output.split('\n')[0]
                if ' ' in first_line:
                    email = first_line.split(' ')[0]
                    return email
            
            # Se não encontrar, tenta uma busca mais ampla pelo nome
            output = self._run_git_command(repo_path, ['log', '--all', '--format=%ae %an'])
            for line in output.split('\n'):
                if self.username.lower() in line.lower():
                    email = line.split(' ')[0]
                    return email
                    
            # Se ainda não encontrar, usa o username como parte do email
            return f"{self.username}@github.com"
            
        # Se nenhum username específico foi fornecido, usa o email configurado localmente
        return self._run_git_command(repo_path, ['config', 'user.email'])
    
    def _get_repository_permissions(self, repo_path: str) -> Dict[str, Any]:
        """
        Verifica as permissões do usuário no repositório.
        Se um username foi fornecido, verifica as permissões desse usuário.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Dicionário com informações de permissão
        """
        user_email = self._get_current_user_email(repo_path)
        owner = self._get_repository_owner(repo_path)
        
        # Extrai informações do remoto para verificação na API
        remote_url = self._run_git_command(repo_path, ['remote', 'get-url', 'origin'])
        repo_owner = None
        repo_name = None
        
        if 'github.com' in remote_url:
            match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', remote_url)
            if match:
                repo_owner = match.group(1)
                repo_name = match.group(2)
        
        # Verifica se o usuário tem commits no repositório
        contributors = self._get_repository_contributors(repo_path)
        has_commits = user_email in contributors
        
        # Verifica se o usuário é o dono do repositório
        is_owner = False
        has_write_permission = False
        
        if self.username and repo_owner and repo_name:
            # Tenta verificar através da API do GitHub
            try:
                # Verifica se o usuário é o dono
                is_owner = repo_owner.lower() == self.username.lower()
                
                # Verifica se o usuário tem permissão de escrita
                # Note: Esta é uma verificação simples que busca se o usuário é colaborador
                response = requests.get(f"https://api.github.com/repos/{repo_owner}/{repo_name}/collaborators/{self.username}")
                if response.status_code == 204:  # Código 204 indica que é colaborador
                    has_write_permission = True
                    
                    # Verifica o nível de permissão, se disponível
                    permission_response = requests.get(f"https://api.github.com/repos/{repo_owner}/{repo_name}/collaborators/{self.username}/permission")
                    if permission_response.status_code == 200:
                        permission = permission_response.json().get('permission')
                        has_write_permission = permission in ['admin', 'write', 'maintain']
            except:
                # Se falhar ao verificar pela API, usamos verificações locais
                pass
        
        # Se não conseguiu verificar pela API ou não tem username específico,
        # tenta verificar localmente
        if not self.username or (not has_write_permission and not is_owner):
            if has_commits:
                # Se tem commits, assume algum nível de acesso
                has_write_permission = True
                
                # Verifica se o usuário é dono pela comparação de emails/nomes
                if user_email and owner:
                    is_owner = user_email.lower() == owner.lower() or (
                        self.username and self.username.lower() == owner.lower()
                    )
            else:
                # Tenta verificar permissão de escrita tentando criar um arquivo
                try:
                    temp_file = os.path.join(repo_path, '.temp_pydrill_test')
                    with open(temp_file, 'w') as f:
                        f.write('test')
                    os.remove(temp_file)
                    has_write_permission = True
                except:
                    has_write_permission = False
        
        return {
            'user_email': user_email,
            'owner': owner,
            'is_owner': is_owner,
            'has_commits': has_commits,
            'commit_count': contributors.get(user_email, 0) if has_commits else 0,
            'has_write_permission': has_write_permission
        }
    
    def _get_lines_changed(self, repo_path: str) -> int:
        """
        Calcula o total de linhas alteradas pelo usuário específico no repositório.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Número total de linhas alteradas
        """
        user_email = self._get_current_user_email(repo_path)
        
        # Prepara o comando git para buscar estatísticas do usuário
        author_param = user_email
        if self.username:
            # Se temos um nome de usuário específico, incluímos como opção alternativa
            author_param = f"{self.username}|{user_email}"
        
        # Busca estatísticas de todos os commits do usuário
        output = self._run_git_command(repo_path, ['log', f'--author={author_param}', '--stat', 'HEAD'])
        
        total_lines = 0
        for line in output.split('\n'):
            match = re.search(r'(\d+) files? changed, (\d+) insertions?\(\+\), (\d+) deletions?\(-\)', line)
            if match:
                _, insertions, deletions = match.groups()
                total_lines += int(insertions) + int(deletions)
                
            # Busca também por formato alternativo de saída do git
            match = re.search(r'(\d+) insertions?\(\+\), (\d+) deletions?\(-\)', line)
            if match and not total_lines:
                insertions, deletions = match.groups()
                total_lines += int(insertions) + int(deletions)
        
        # Se não encontrou linhas pelo autor, tenta uma abordagem diferente com nome de usuário
        if total_lines == 0 and self.username:
            try:
                # Tenta buscar informações do GitHub API
                remote_url = self._run_git_command(repo_path, ['remote', 'get-url', 'origin'])
                if 'github.com' in remote_url:
                    match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', remote_url)
                    if match:
                        owner = match.group(1)
                        repo_name = match.group(2)
                        
                        # Busca commits do usuário via API
                        response = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}/commits?author={self.username}")
                        if response.status_code == 200:
                            commits = response.json()
                            
                            # Estima linhas alteradas (aproximado)
                            for commit in commits:
                                commit_sha = commit['sha']
                                stats_response = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}/commits/{commit_sha}")
                                if stats_response.status_code == 200:
                                    stats = stats_response.json().get('stats', {})
                                    total_lines += stats.get('additions', 0) + stats.get('deletions', 0)
            except:
                pass
        
        return total_lines
    
    def _get_monthly_contributions(self, repo_path: str, months: int = 12) -> Dict[str, int]:
        """
        Verifica a contribuição mensal do usuário nos últimos X meses.
        
        Args:
            repo_path: Caminho para o repositório
            months: Número de meses a serem analisados
            
        Returns:
            Dicionário com meses e número de contribuições
        """
        user_email = self._get_current_user_email(repo_path)
        
        # Calcula a data de início (X meses atrás)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30 * months)
        
        # Formato de data para comandos git
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Prepara parâmetro de autor
        author_param = user_email
        if self.username:
            # Se temos um nome de usuário específico, incluímos como opção alternativa
            author_param = f"{self.username}|{user_email}"
        
        # Obtém todos os commits do usuário
        output = self._run_git_command(
            repo_path, 
            ['log', '--author=' + author_param, '--since=' + start_date_str, '--until=' + end_date_str, '--format=%ad', '--date=format:%Y-%m']
        )
        
        # Agrupa por mês
        monthly_contributions = defaultdict(int)
        for line in output.split('\n'):
            if line.strip():
                monthly_contributions[line] += 1
        
        # Se não encontrou contribuições e temos um nome de usuário específico,
        # tenta buscar pela API do GitHub
        if not monthly_contributions and self.username:
            try:
                remote_url = self._run_git_command(repo_path, ['remote', 'get-url', 'origin'])
                if 'github.com' in remote_url:
                    match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', remote_url)
                    if match:
                        owner = match.group(1)
                        repo_name = match.group(2)
                        
                        # Busca commits via API
                        response = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}/commits?author={self.username}")
                        if response.status_code == 200:
                            commits = response.json()
                            
                            for commit in commits:
                                commit_date = commit.get('commit', {}).get('author', {}).get('date', '')
                                if commit_date:
                                    # Formata data para padrão de mês
                                    try:
                                        date_obj = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
                                        month_key = date_obj.strftime('%Y-%m')
                                        
                                        # Verifica se está dentro do período de análise
                                        if start_date <= date_obj <= end_date:
                                            monthly_contributions[month_key] += 1
                                    except:
                                        pass
            except:
                pass
        
        return dict(monthly_contributions)
    
    def _get_consecutive_contribution_streak(self, repo_path: str) -> int:
        """
        Calcula a sequência máxima de contribuições consecutivas por semana no ano.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Número máximo de semanas consecutivas com contribuições
        """
        user_email = self._get_current_user_email(repo_path)
        
        # Prepara parâmetro de autor
        author_param = user_email
        if self.username:
            author_param = f"{self.username}|{user_email}"
        
        # Obtém todos os commits do usuário no último ano
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        output = self._run_git_command(
            repo_path, 
            ['log', '--author=' + author_param, '--since=' + one_year_ago, '--format=%ad', '--date=format:%Y-%U']
        )
        
        # Cria conjunto de semanas com contribuições
        weeks_with_contributions = set()
        for line in output.split('\n'):
            if line.strip():
                weeks_with_contributions.add(line)
        
        # Se não encontrou contribuições e temos um nome de usuário específico,
        # tenta buscar pela API do GitHub
        if not weeks_with_contributions and self.username:
            try:
                remote_url = self._run_git_command(repo_path, ['remote', 'get-url', 'origin'])
                if 'github.com' in remote_url:
                    match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', remote_url)
                    if match:
                        owner = match.group(1)
                        repo_name = match.group(2)
                        
                        # Busca commits via API
                        response = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}/commits?author={self.username}")
                        if response.status_code == 200:
                            commits = response.json()
                            
                            for commit in commits:
                                commit_date = commit.get('commit', {}).get('author', {}).get('date', '')
                                if commit_date:
                                    try:
                                        date_obj = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
                                        one_year_ago_date = datetime.now() - timedelta(days=365)
                                        
                                        if date_obj >= one_year_ago_date:
                                            week_id = date_obj.strftime('%Y-%U')
                                            weeks_with_contributions.add(week_id)
                                    except:
                                        pass
            except:
                pass
        
        # Calcula a sequência máxima de semanas consecutivas
        max_streak = 0
        current_streak = 0
        
        # Gera todas as semanas do último ano
        current_date = datetime.now()
        for i in range(52):
            week_date = current_date - timedelta(weeks=i)
            week_id = week_date.strftime('%Y-%U')
            
            if week_id in weeks_with_contributions:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _calculate_commit_percentage(self, repo_path: str) -> float:
        """
        Calcula a porcentagem de commits do usuário em relação ao total do repositório.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Porcentagem de commits
        """
        contributors = self._get_repository_contributors(repo_path)
        user_email = self._get_current_user_email(repo_path)
        
        user_commits = contributors.get(user_email, 0)
        total_commits = sum(contributors.values())
        
        # Se estamos buscando por um username específico, verifica também 
        # outros possíveis emails associados
        if self.username and user_commits == 0:
            # Tenta encontrar commits do usuário por nome em vez de email
            output = self._run_git_command(repo_path, ['shortlog', '-sne', 'HEAD'])
            for line in output.split('\n'):
                if self.username.lower() in line.lower():
                    parts = re.match(r'^\s*(\d+)\s+(.+?)\s+<(.+?)>$')
    
    def analyze_repository(self, repo_path: str) -> Dict[str, Any]:
        """
        Analisa um único repositório e retorna estatísticas.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Dicionário com estatísticas do repositório
        """
        repo_name = self._get_repository_name(repo_path)
        permissions = self._get_repository_permissions(repo_path)
        lines_changed = self._get_lines_changed(repo_path)
        monthly_contributions = self._get_monthly_contributions(repo_path)
        consecutive_streak = self._get_consecutive_contribution_streak(repo_path)
        commit_percentage = self._calculate_commit_percentage(repo_path)
        
        return {
            'repo_name': repo_name,
            'lines_changed': lines_changed,
            'monthly_contributions': monthly_contributions,
            'consecutive_contribution_streak': consecutive_streak,
            'is_owner': permissions['is_owner'],
            'has_write_permission': permissions['has_write_permission'],
            'commit_percentage': commit_percentage
        }
    
    def analyze_all_repositories(self) -> Dict[str, Dict[str, Any]]:
        """
        Analisa todos os repositórios descobertos e gera estatísticas.
        
        Returns:
            Dicionário com estatísticas de todos os repositórios
        """
        results = {}
        for repo_path in self.repos:
            repo_name = self._get_repository_name(repo_path)
            results[repo_name] = self.analyze_repository(repo_path)
        
        self.results = results
        return results
    
    def check_achievements(self, criteria: Dict[str, Any] = None) -> Dict[str, bool]:
        """
        Verifica se os objetivos foram alcançados com base nos critérios.
        
        Args:
            criteria: Dicionário com os critérios para cada objetivo
                - lines_changed: Número mínimo de linhas alteradas
                - monthly_streak_single: Número de meses com contribuições em um repositório
                - monthly_streak_multiple: Número de meses com contribuições em 2+ repositórios
                - weekly_streak: Sequência mínima de contribuições semanais
                - edit_rights_non_owner: Deve ter direitos de edição em um repositório não próprio
                - commit_percentage: Porcentagem mínima de commits em um repositório não próprio
                
        Returns:
            Dicionário com os objetivos alcançados
        """
        if not self.results:
            self.analyze_all_repositories()
            
        if criteria is None:
            criteria = {
                'lines_changed': 100,  # Valor padrão: 100 linhas alteradas
                'monthly_streak_single': 3,  # Valor padrão: 3 meses seguidos
                'monthly_streak_multiple': 2,  # Valor padrão: 2 meses seguidos em 2+ repos
                'weekly_streak': 4,  # Valor padrão: 4 semanas seguidas
                'edit_rights_non_owner': True,  # Deve ter direitos de edição em repo não próprio
                'commit_percentage': 30  # Valor padrão: 30% dos commits em repo não próprio
            }
        
        # Inicializa os resultados dos objetivos
        achievements = {
            'altered_x_lines': False,
            'monthly_contributions_single_repo': False,
            'monthly_contributions_multiple_repos': False,
            'weekly_contribution_streak': False,
            'edit_rights_non_owner': False,
            'commit_percentage_non_owner': False
        }
        
        # Verifica cada objetivo
        total_lines_changed = sum(repo['lines_changed'] for repo in self.results.values())
        if total_lines_changed >= criteria['lines_changed']:
            achievements['altered_x_lines'] = True
        
        # Verifica contribuições mensais em um único repositório
        for repo_name, repo_data in self.results.items():
            monthly_contribs = repo_data['monthly_contributions']
            if len(monthly_contribs) >= criteria['monthly_streak_single']:
                achievements['monthly_contributions_single_repo'] = True
                break
        
        # Verifica contribuições mensais em múltiplos repositórios
        # Para cada mês, conte quantos repositórios têm contribuições
        monthly_repo_counts = defaultdict(int)
        for repo_name, repo_data in self.results.items():
            for month in repo_data['monthly_contributions'].keys():
                monthly_repo_counts[month] += 1
        
        # Conta meses com contribuições em 2+ repositórios
        months_with_multiple_repos = sum(1 for count in monthly_repo_counts.values() if count >= 2)
        if months_with_multiple_repos >= criteria['monthly_streak_multiple']:
            achievements['monthly_contributions_multiple_repos'] = True
        
        # Verifica sequência de contribuições semanais
        max_weekly_streak = max(
            (repo_data['consecutive_contribution_streak'] for repo_data in self.results.values()),
            default=0
        )
        if max_weekly_streak >= criteria['weekly_streak']:
            achievements['weekly_contribution_streak'] = True
        
        # Verifica direitos de edição em repositório que não é dono
        for repo_name, repo_data in self.results.items():
            if not repo_data['is_owner'] and repo_data['has_write_permission']:
                achievements['edit_rights_non_owner'] = True
                break
        
        # Verifica porcentagem de commits em repositório que não é dono
        for repo_name, repo_data in self.results.items():
            repos = repo_data['commit_percentage']
            if repo_data['commit_percentage'] is None:
                repos = repo_data['commit_percentage'] = 0
            if not repo_data['is_owner'] and repos >= criteria['commit_percentage']:
                achievements['commit_percentage_non_owner'] = True
                break
        
        return achievements
    
    def get_results_as_json(self, criteria: Dict[str, Any] = None) -> str:
        """
        Retorna os resultados em formato JSON.
        
        Args:
            criteria: Critérios para verificação dos objetivos
            
        Returns:
            String JSON com os resultados
        """
        achievements = self.check_achievements(criteria)
        
        result = {
            'achievements': achievements,
            'repository_stats': self.results,
            'criteria_used': criteria
        }
        
        return json.dumps(result, indent=2)


# Função para ser chamada de outros scripts
def check_github_achievements(repositories_path: str, username: str = None, criteria: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Verifica os objetivos do GitHub com base nos critérios fornecidos.
    
    Args:
        repositories_path: Caminho para a pasta que contém os repositórios
        username: Nome de usuário específico do GitHub para analisar (ex: "Bytsuki0")
        criteria: Critérios específicos para verificar os objetivos
        
    Returns:
        Dicionário com os resultados
    """
    analyzer = GitHubStatsAnalyzer(repositories_path, username)
    analyzer.analyze_all_repositories()
    achievements = analyzer.check_achievements(criteria)
    
    return {
        'achievements': achievements,
        'repository_stats': analyzer.results,
        'criteria_used': criteria
    }

def os_user(username):
    if platform.system() == "Windows":
        path = Path(__file__).resolve().parent
        return path / username
    
    if platform.system() == "Linux":
        path = Path(__file__).resolve().parent
        return path / username


def main():

    user = username
    repo_path = os_user(user)
    
    custom_criteria = {
        'lines_changed': 10000,           
        'monthly_streak_single': 6,     
        'monthly_streak_multiple': 3,   
        'weekly_streak': 5,              
        'edit_rights_non_owner': True,   
        'commit_percentage': 25         
    }

    github_username = username 

    analyzer = GitHubStatsAnalyzer(repo_path, github_username)
    results = analyzer.analyze_all_repositories()
    achievements = analyzer.check_achievements(custom_criteria)
    

    print(json.dumps(achievements, indent=2))
    
    with open('github_achievements.json', 'w') as f:
        f.write(analyzer.get_results_as_json(custom_criteria))


if __name__ == "__main__":
    main()
    import os
import subprocess
import json
import re
import time
import stat
import requests
import platform 
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import re
from typing import Dict, List, Tuple, Set, Optional, Union, Any
import gitblame as gb
import configparser as cfgparser

config = cfgparser.ConfigParser()
config.read('config.ini')
username = config['github']['username']
token = config['github']['token']

class GitHubStatsAnalyzer:

    
    def __init__(self, repositories_path: str):

        self.repositories_path = repositories_path
        self.repos = self._discover_repositories()
        self.results = {}
    
    def _discover_repositories(self) -> List[str]:
        repos = []
        
        for root, dirs, _ in os.walk(self.repositories_path):
            if '.git' in dirs:
                repos.append(root)
        
        return repos
    
    def _run_git_command(self, repo_path: str, command: List[str]) -> str:

        full_command = ['git', '-C', repo_path] + command
        result = subprocess.run(full_command, capture_output=True, text=True)
        return result.stdout.strip()
    
    # Obtém o proprietário do repositório a partir da URL remota
    def _get_repository_owner(self, repo_path: str) -> str:
        remote_url = self._run_git_command(repo_path, ['remote', 'get-url', 'origin'])
        
        if 'github.com' in remote_url:
            match = re.search(r'github\.com[:/]([^/]+)', remote_url)
            if match:
                return match.group(1)
        config_user = self._run_git_command(repo_path, ['config', 'user.name'])
        return config_user
    # Obtém o nome do repositório a partir do caminho
    def _get_repository_name(self, repo_path: str) -> str:

        return os.path.basename(repo_path)
    
    def _get_repository_contributors(self, repo_path: str) -> Dict[str, int]:

        output = self._run_git_command(repo_path, ['shortlog', '-sne', 'HEAD'])
        contributors = {}
        
        for line in output.split('\n'):
            if not line.strip():
                continue
                
            parts = re.match(r'^\s*(\d+)\s+(.+?)\s+<(.+?)>$', line)
            if parts:
                commits, name, email = parts.groups()
                contributors[email] = int(commits)
        
        return contributors
    
    def _get_current_user_email(self, repo_path: str) -> str:

        return self._run_git_command(repo_path, ['config', 'user.email'])
    
    def _get_repository_permissions(self, repo_path: str) -> Dict[str, str]:

        user_email = self._get_current_user_email(repo_path)
        owner = self._get_repository_owner(repo_path)
        
        # Verifica se o usuário tem commits no repositório
        contributors = self._get_repository_contributors(repo_path)
        has_commits = user_email in contributors
        
        # Verifica se o usuário tem permissão de escrita (simplificado)
        # Em um cenário real, seria necessário verificar as permissões do GitHub API
        has_write_permission = False
        try:
            # Tenta criar um arquivo temporário e depois remove
            temp_file = os.path.join(repo_path, '.temp_pydrill_test')
            with open(temp_file, 'w') as f:
                f.write('test')
            os.remove(temp_file)
            if username != owner:
                has_write_permission = True
        except:
            has_write_permission = False
        
        return {
            'user_email': user_email,
            'owner': owner,
            'is_owner': user_email == owner,  # Simplificado
            'has_commits': has_commits,
            'commit_count': contributors.get(user_email, 0) if has_commits else 0,
            'has_write_permission': has_write_permission
        }
    # Obtém o número total de linhas alteradas pelo usuário no repositório
    # Isso pode incluir adições e deleções
    def _get_lines_changed(self, repo_path: str) -> int:

        user_email = self._get_current_user_email(repo_path)
        output = self._run_git_command(repo_path, ['log', '--author=' + user_email, '--stat', 'HEAD'])
        
        total_lines = 0
        for line in output.split('\n'):
            match = re.search(r'(\d+) files? changed, (\d+) insertions?\(\+\), (\d+) deletions?\(-\)', line)
            if match:
                _, insertions, deletions = match.groups()
                total_lines += int(insertions) + int(deletions)
        
        return total_lines
    
    # Obtém o número de contribuições mensais do usuário no repositório
    def _get_monthly_contributions(self, repo_path: str, months: int = 12) -> Dict[str, int]:
        
        user_email = self._get_current_user_email(repo_path)
        
        # Calcula a data de início (X meses atrás)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30 * months)

        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        output = self._run_git_command(
            repo_path, 
            ['log', '--author=' + user_email, '--since=' + start_date_str, '--until=' + end_date_str, '--format=%ad', '--date=format:%Y-%m']
        )

        monthly_contributions = defaultdict(int)
        for line in output.split('\n'):
            if line.strip():
                monthly_contributions[line] += 1
        
        return dict(monthly_contributions)
    # Obtém a sequência máxima de contribuições consecutivas por semana no ano
    def _get_consecutive_contribution_streak(self, repo_path: str) -> int:

        user_email = self._get_current_user_email(repo_path)

        one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        output = self._run_git_command(
            repo_path, 
            ['log', '--author=' + user_email, '--since=' + one_year_ago, '--format=%ad', '--date=format:%Y-%U']
        )
        
        # Cria conjunto de semanas com contribuições
        weeks_with_contributions = set()
        for line in output.split('\n'):
            if line.strip():
                weeks_with_contributions.add(line)
        
        # Calcula a sequência máxima de semanas consecutivas
        max_streak = 0
        current_streak = 0
        
        # Gera todas as semanas do último ano
        current_date = datetime.now()
        for i in range(52):
            week_date = current_date - timedelta(weeks=i)
            week_id = week_date.strftime('%Y-%U')
            
            if week_id in weeks_with_contributions:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _calculate_commit_percentage(self, repo_path: str) -> float:
        """
        Calcula a porcentagem de commits do usuário em relação ao total do repositório.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Porcentagem de commits
        """
        contributors = self._get_repository_contributors(repo_path)
        user_email = self._get_current_user_email(repo_path)
        
        user_commits = contributors.get(user_email, 0)
        total_commits = sum(contributors.values())
        
        if total_commits == 0:
            return 0
        
        return (user_commits / total_commits) * 100
    
    def analyze_repository(self, repo_path: str) -> Dict[str, Any]:
        """
        Analisa um único repositório e retorna estatísticas.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Dicionário com estatísticas do repositório
        """
        repo_name = self._get_repository_name(repo_path)
        permissions = self._get_repository_permissions(repo_path)
        lines_changed = self._get_lines_changed(repo_path)
        monthly_contributions = self._get_monthly_contributions(repo_path)
        consecutive_streak = self._get_consecutive_contribution_streak(repo_path)
        commit_percentage = self._calculate_commit_percentage(repo_path)
        
        return {
            'repo_name': repo_name,
            'lines_changed': lines_changed,
            'monthly_contributions': monthly_contributions,
            'consecutive_contribution_streak': consecutive_streak,
            'is_owner': permissions['is_owner'],
            'has_write_permission': permissions['has_write_permission'],
            'commit_percentage': commit_percentage
        }
    
    def analyze_all_repositories(self) -> Dict[str, Dict[str, Any]]:

        results = {}
        for repo_path in self.repos:
            repo_name = self._get_repository_name(repo_path)
            results[repo_name] = self.analyze_repository(repo_path)
        
        self.results = results
        return results
    
    def check_achievements(self, criteria: Dict[str, Any] = None) -> Dict[str, bool]:
        """
        Verifica se os objetivos foram alcançados com base nos critérios.
        
        Args:
            criteria: Dicionário com os critérios para cada objetivo
                - lines_changed: Número mínimo de linhas alteradas
                - monthly_streak_single: Número de meses com contribuições em um repositório
                - monthly_streak_multiple: Número de meses com contribuições em 2+ repositórios
                - weekly_streak: Sequência mínima de contribuições semanais
                - edit_rights_non_owner: Deve ter direitos de edição em um repositório não próprio
                - commit_percentage: Porcentagem mínima de commits em um repositório não próprio
                
        Returns:
            Dicionário com os objetivos alcançados
        """
        if not self.results:
            self.analyze_all_repositories()
            
        if criteria is None:
            criteria = {
                'lines_changed': 100,  # Valor padrão: 100 linhas alteradas
                'monthly_streak_single': 3,  # Valor padrão: 3 meses seguidos
                'monthly_streak_multiple': 2,  # Valor padrão: 2 meses seguidos em 2+ repos
                'weekly_streak': 4,  # Valor padrão: 4 semanas seguidas
                'edit_rights_non_owner': True,  # Deve ter direitos de edição em repo não próprio
                'commit_percentage': 30  # Valor padrão: 30% dos commits em repo não próprio
            }
        
        # Inicializa os resultados dos objetivos
        achievements = {
            'altered_x_lines': False,
            'monthly_contributions_single_repo': False,
            'monthly_contributions_multiple_repos': False,
            'weekly_contribution_streak': False,
            'edit_rights_non_owner': False,
            'commit_percentage_non_owner': False
        }
        
        # Verifica cada objetivo
        total_lines_changed = sum(repo['lines_changed'] for repo in self.results.values())
        if total_lines_changed >= criteria['lines_changed']:
            achievements['altered_x_lines'] = True
        
        # Verifica contribuições mensais em um único repositório
        for repo_name, repo_data in self.results.items():
            monthly_contribs = repo_data['monthly_contributions']
            if len(monthly_contribs) >= criteria['monthly_streak_single']:
                achievements['monthly_contributions_single_repo'] = True
                break
        
        # Verifica contribuições mensais em múltiplos repositórios
        # Para cada mês, conte quantos repositórios têm contribuições
        monthly_repo_counts = defaultdict(int)
        for repo_name, repo_data in self.results.items():
            for month in repo_data['monthly_contributions'].keys():
                monthly_repo_counts[month] += 1
        
        # Conta meses com contribuições em 2+ repositórios
        months_with_multiple_repos = sum(1 for count in monthly_repo_counts.values() if count >= 2)
        if months_with_multiple_repos >= criteria['monthly_streak_multiple']:
            achievements['monthly_contributions_multiple_repos'] = True
        
        # Verifica sequência de contribuições semanais
        max_weekly_streak = max(
            (repo_data['consecutive_contribution_streak'] for repo_data in self.results.values()),
            default=0
        )
        if max_weekly_streak >= criteria['weekly_streak']:
            achievements['weekly_contribution_streak'] = True
        
        # Verifica direitos de edição em repositório que não é dono
        for repo_name, repo_data in self.results.items():
            if not repo_data['is_owner'] and repo_data['has_write_permission']:
                achievements['edit_rights_non_owner'] = True
                break
        
        # Verifica porcentagem de commits em repositório que não é dono
        for repo_name, repo_data in self.results.items():
            if not repo_data['is_owner'] and repo_data['commit_percentage'] >= criteria['commit_percentage']:
                achievements['commit_percentage_non_owner'] = True
                break
        
        return achievements
    
    def get_results_as_json(self, criteria: Dict[str, Any] = None) -> str:

        achievements = self.check_achievements(criteria)
        
        result = {
            'achievements': achievements,
            'repository_stats': self.results,
            'criteria_used': criteria
        }
        
        return json.dumps(result, indent=2)


def check_github_achievements(repositories_path: str, criteria: Dict[str, Any] = None) -> Dict[str, Any]:

    analyzer = GitHubStatsAnalyzer(repositories_path)
    analyzer.analyze_all_repositories()
    achievements = analyzer.check_achievements(criteria)
    
    return {
        'achievements': achievements,
        'repository_stats': analyzer.results,
        'criteria_used': criteria
    }
def os_user(username):
    if platform.system() == "Windows":
        path = Path(__file__).resolve().parent
        return path / username
    
    if platform.system() == "Linux":
        path = Path(__file__).resolve().parent
        return path / username

def main():

    repo_path = os_user(username)
    
    custom_criteria = {
        'lines_changed': 10000,           
        'monthly_streak_single': 6,     
        'monthly_streak_multiple': 3,   
        'weekly_streak': 5,              
        'edit_rights_non_owner': True,   
        'commit_percentage': 25         
    }

    analyzer = GitHubStatsAnalyzer(repo_path)
    results = analyzer.analyze_all_repositories()
    achievements = analyzer.check_achievements(custom_criteria)
    

    print(json.dumps(achievements, indent=2))
    
    with open('github_achievements.json', 'w') as f:
        f.write(analyzer.get_results_as_json(custom_criteria))


if __name__ == "__main__":
    main()
    import os
import csv
import re
import time
import requests
import platform 
import subprocess
import gitblame as gb


gb.data_rows = []

def is_git_repo(path):
    try:
        subprocess.run(["git", "-C", path, "status"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

#todos os comentarios em commits issues e pull requests
def get_user_activity(username, token, repoName, num_events):
    headers = {"Authorization": f"token {token}"}
  
    activity_info = "\n"
    issues_url = f"https://api.github.com/repos/{username}/{repoName}/issues/comments"
    issues_response = requests.get(issues_url, headers=headers)
    
    issues_info = "Comentários em Issues:\n"
    print("\nÚltimos comentários em Issues:")
    
    if issues_response.status_code == 200:
        issues_comments = issues_response.json()
        for comment in issues_comments[:num_events]:
            comment_str = (f"- Comentário: {comment.get('body', 'Sem conteúdo')}\n"
                           f"  Autor: {comment.get('user', {}).get('login', 'Desconhecido')} "
                           f"({comment.get('user', {}).get('html_url', 'Sem URL')})\n"
                           f"  Criado em: {comment.get('created_at', 'Data desconhecida')}\n")
            print(comment_str)
            issues_info += comment_str + "\n"
    else:
        err = f"Erro ao obter comentários em Issues: {issues_response.status_code}"
        print(err)
        issues_info += err
    activity_info += issues_info + "\n"

    pr_comments_url = f"https://api.github.com/repos/{username}/{repoName}/pulls/comments"
    pr_comments_response = requests.get(pr_comments_url, headers=headers)
    
    pr_info = "Comentários em Pull Requests:\n"
    print("\nÚltimos comentários em Pull Requests:")
    if pr_comments_response.status_code == 200:
        pr_comments = pr_comments_response.json()
        for comment in pr_comments[:num_events]:
            comment_str = (f"- Comentário: {comment.get('body', 'Sem conteúdo')}\n"
                           f"  Autor: {comment.get('user', {}).get('login', 'Desconhecido')} "
                           f"({comment.get('user', {}).get('html_url', 'Sem URL')})\n"
                           f"  Criado em: {comment.get('created_at', 'Data desconhecida')}\n")
            print(comment_str)
            pr_info += comment_str + "\n"
    else:
        err = f"Erro ao obter comentários em Pull Requests: {pr_comments_response.status_code}"
        print(err)
        pr_info += err
    activity_info += pr_info + "\n"

    commit_comments_url = f"https://api.github.com/repos/{username}/{repoName}/comments"
    commit_comments_response = requests.get(commit_comments_url, headers=headers)
    
    commit_info = "Comentários em Commits:\n"
    print("\nÚltimos comentários em Commits:")
    if commit_comments_response.status_code == 200:
        commit_comments = commit_comments_response.json()
        for comment in commit_comments[:num_events]:
            comment_str = (f"- Comentário: {comment.get('body', 'Sem conteúdo')}\n"
                           f"  Autor: {comment.get('user', {}).get('login', 'Desconhecido')} "
                           f"({comment.get('user', {}).get('html_url', 'Sem URL')})\n"
                           f"  Criado em: {comment.get('created_at', 'Data desconhecida')}\n")
            print(comment_str)
            commit_info += comment_str + "\n"
    else:
        err = f"Erro ao obter comentários em Commits: {commit_comments_response.status_code}"
        print(err)
        commit_info += err
    activity_info += commit_info


#todos os ultimos e issues e pull requests abertos
def get_user_opened_issues_and_prs(username, token, num_events):
    headers = {"Authorization": f"token {token}"}
    pull = 0
    issues = 0
    resolved_info = "\n"

    issues_url = f"https://api.github.com/search/issues?q=is:issue+author:{username}"
    issues_response = requests.get(issues_url, headers=headers)
    
    issues_resolved = "Issues resolvidas:\n"
    print("\nÚltimas 30 Issues abertas:")
    if issues_response.status_code == 200:
        issues_data = issues_response.json()
        for issue in issues_data.get('items', [])[:num_events]:
            issues += 1
            repo_url = issue['repository_url'].replace("https://api.github.com/repos/", "")
            issue_str = (f"- Issue: {issue.get('title', 'Sem título')}\n"
                         f"  Repositório: {repo_url}\n"
                         f"  Aberto as: {issue.get('created_at', 'Data desconhecida')}\n")
            print(issue_str)
            issues_resolved += issue_str + "\n"
    else:
        err = f"Erro ao buscar Issues: {issues_response.status_code}"
        print(err)
        issues_resolved += err
    resolved_info += issues_resolved + "\n"


    pr_url = f"https://api.github.com/search/issues?q=is:pr+author:{username}"
    pr_response = requests.get(pr_url, headers=headers)
    
    prs_resolved = "Pull Requests:\n"
    print("\nÚltimas 30 Pull Requests abertas:")
    if pr_response.status_code == 200:
        pr_data = pr_response.json()
        for pr in pr_data.get('items', [])[:num_events]:
            pull += 1
            repo_url = pr['repository_url'].replace("https://api.github.com/repos/", "")
            pr_str = (f"- Pull Request: {pr.get('title', 'Sem título')}\n"
                      f"  Repositório: {repo_url}\n"
                      f"  Aberto as: {pr.get('created_at', 'Data desconhecida')}\n")
            print(pr_str)
            prs_resolved += pr_str + "\n"
    else:
        err = f"Erro ao buscar Pull Requests: {pr_response.status_code}"
        print(err)
        prs_resolved += err
    resolved_info += prs_resolved

    return [issues,pull]


#todos os ultimso x issues e pull requests resolvidos
def get_user_resolved_issues_and_prs(username, token, num_events):
    headers = {"Authorization": f"token {token}"}
    resolved_pull = 0
    resolved_issues = 0
    resolved_issues_non_owned = 0
    resolved_pull_non_owned = 0
    merged_prs_count = 0  
    merged_prs_count_non_owned = 0
    resolved_info = "\n"

 
    issues_url = f"https://api.github.com/search/issues?q=is:issue+author:{username}+is:closed"
    issues_response = requests.get(issues_url, headers=headers)
    
    issues_resolved = "Issues resolvidas:\n"
    print("\nÚltimas 30 Issues resolvidas:")
    if issues_response.status_code == 200:
        issues_data = issues_response.json()
        for issue in issues_data.get('items', [])[:num_events]:
            resolved_issues += 1
            repo_url = issue['repository_url'].replace("https://api.github.com/repos/", "")
            issue_str = (f"- Issue: {issue.get('title', 'Sem título')}\n"
                         f"  Repositório: {repo_url}\n"
                         f"  Resolvido em: {issue.get('closed_at', 'Data desconhecida')}\n")
            if None == re.search(username, repo_url):
                resolved_issues_non_owned += 1
            print(issue_str)
            issues_resolved += issue_str + "\n"
    else:
        err = f"Erro ao buscar Issues: {issues_response.status_code}"
        print(err)
        issues_resolved += err
    resolved_info += issues_resolved + "\n"


    pr_url = f"https://api.github.com/search/issues?q=is:pr+author:{username}+is:closed"
    pr_response = requests.get(pr_url, headers=headers)
    
    prs_resolved = "Pull Requests fechadas:\n"
    print("\nÚltimas 30 Pull Requests fechadas:")
    if pr_response.status_code == 200:
        pr_data = pr_response.json()
        for pr in pr_data.get('items', [])[:num_events]:
            resolved_pull += 1
            repo_url = pr['repository_url'].replace("https://api.github.com/repos/", "")
            pr_str = (f"- Pull Request: {pr.get('title', 'Sem título')}\n"
                      f"  Repositório: {repo_url}\n"
                      f"  Fechado em: {pr.get('closed_at', 'Data desconhecida')}\n")
            
            if None == re.search(username, repo_url):
                resolved_pull_non_owned += 1
            print(pr_str)
            prs_resolved += pr_str + "\n"
    else:
        err = f"Erro ao buscar Pull Requests: {pr_response.status_code}"
        print(err)
        prs_resolved += err
    resolved_info += prs_resolved
    
    merged_pr_url = f"https://api.github.com/search/issues?q=is:pr+author:{username}+is:merged"
    merged_pr_response = requests.get(merged_pr_url, headers=headers)
    
    merged_prs_info = "\nPull Requests com merge:\n"
    print("\nPull Requests com merge:")
    if merged_pr_response.status_code == 200:
        merged_pr_data = merged_pr_response.json()
        merged_prs_count = merged_pr_data.get('total_count', 0)
        merged_prs_info += f"Total de PRs com merge: {merged_prs_count}\n"
    
        for pr in merged_pr_data.get('items', [])[:num_events]:
            repo_url = pr['repository_url'].replace("https://api.github.com/repos/", "")
            pr_str = (f"- {pr.get('title', 'Sem título')}\n"
                      f"  Repositório: {repo_url}\n"
                      f"  Merge realizado em: {pr.get('closed_at', 'Data desconhecida')}\n")
            if None == re.search(username, repo_url):
                merged_prs_count_non_owned += 1
            print(pr_str)
            merged_prs_info += pr_str + "\n"
    else:
        err = f"Erro ao buscar PRs com merge: {merged_pr_response.status_code}"
        print(err)
        merged_prs_info += err
    
    resolved_info += merged_prs_info + "\n"

    return [resolved_issues, resolved_pull, merged_prs_count, resolved_issues_non_owned, resolved_pull_non_owned, merged_prs_count_non_owned]



def fila(url, headers, max_retries=10, delay=2):

    retries = 0
    response = requests.get(url, headers=headers)
    while response.status_code == 202 and retries < max_retries:
        time.sleep(delay)
        response = requests.get(url, headers=headers)
        retries += 1
    return response

#dados totais do usuario 

def get_commit_stats_total(username, token):

    headers = {"Authorization": f"token {token}"}
    url = "https://api.github.com/user/repos?per_page=100"
    response = requests.get(url, headers=headers)
    total_commits = 0
    total_lines_changed = 0
    stats_info = "Estatísticas totais (todos os repositórios):\n"
    
    if response.status_code != 200:
        err = f"Erro ao buscar repositórios para estatísticas totais: {response.status_code}"
        print(err)
        stats_info += err
        gb.data_rows.append(("Estatísticas Totais", stats_info))
        return
    
    repos = response.json()
    for repo in repos:
        owner = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")
        stats_url = f"https://api.github.com/repos/{owner}/{repo_name}/stats/contributors"
        stats_response = fila(stats_url, headers)
        if stats_response.status_code != 200:
            msg = f"Não foi possível obter estatísticas para {repo_name} (status: {stats_response.status_code})."
            print(msg)
            stats_info += msg + "\n"
            continue
        stats = stats_response.json()
        if not stats:
            msg = f"Estatísticas não disponíveis para {repo_name}."
            print(msg)
            stats_info += msg + "\n"
            continue
        for contributor in stats:
            if contributor.get("author", {}).get("login") == username:
                commits = contributor.get("total", 0)
                total_commits += commits
                lines_changed = sum(week.get("a", 0) - week.get("d", 0) for week in contributor.get("weeks", []))
                total_lines_changed += lines_changed
                stats_info += (f"{repo_name}: commits = {commits}, linhas alteradas = {lines_changed}\n")
    summary = (f"Total de commits: {total_commits}\n"
               f"Total de linhas alteradas: {total_lines_changed}")
    stats_info += "\n" + summary

    info = [total_commits, total_lines_changed]
    print("\nEstatísticas totais (todos os repositórios em que o usuário participa):")
    print(summary)
    return info


def get_commit_stats_total(username, token):

    headers = {"Authorization": f"token {token}"}
    url = "https://api.github.com/user/repos?per_page=100"
    response = requests.get(url, headers=headers)
    total_commits = 0
    total_lines_changed = 0
    stats_info = "Estatísticas totais (todos os repositórios):\n"
    
    if response.status_code != 200:
        err = f"Erro ao buscar repositórios para estatísticas totais: {response.status_code}"
        print(err)
        stats_info += err
        gb.data_rows.append(("Estatísticas Totais", stats_info))
        return
    
    repos = response.json()
    for repo in repos:
        owner = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")
        stats_url = f"https://api.github.com/repos/{owner}/{repo_name}/stats/contributors"
        stats_response = fila(stats_url, headers)
        if stats_response.status_code != 200:
            msg = f"Não foi possível obter estatísticas para {repo_name} (status: {stats_response.status_code})."
            print(msg)
            stats_info += msg + "\n"
            continue
        stats = stats_response.json()
        if not stats:
            msg = f"Estatísticas não disponíveis para {repo_name}."
            print(msg)
            stats_info += msg + "\n"
            continue
        for contributor in stats:
            if contributor.get("author", {}).get("login") == username:
                commits = contributor.get("total", 0)
                total_commits += commits
                lines_changed = sum(week.get("a", 0) - week.get("d", 0) for week in contributor.get("weeks", []))
                total_lines_changed += lines_changed
                stats_info += (f"{repo_name}: commits = {commits}, linhas alteradas = {lines_changed}\n")
    summary = (f"Total de commits: {total_commits}\n"
               f"Total de linhas alteradas: {total_lines_changed}")
    stats_info += "\n" + summary

    info = [total_commits, total_lines_changed]
    print("\nEstatísticas totais (todos os repositórios em que o usuário participa):")
    print(summary)
    return info


#dados de commits de repositórios que o usuario não é dono

def get_commit_stats_non_owned(username, token):

    headers = {"Authorization": f"token {token}"}
    url = "https://api.github.com/user/repos?per_page=100"
    response = requests.get(url, headers=headers)
    total_commits = 0
    total_lines_changed = 0
    stats_info = "Estatísticas para repositórios NÃO próprios:\n"
    
    if response.status_code != 200:
        err = f"Erro ao buscar repositórios para estatísticas não próprias: {response.status_code}"
        print(err)
        stats_info += err
        gb.data_rows.append(("Estatísticas Repositórios Não Próprios", stats_info))
        return
    
    repos = response.json()
    non_owned_repos = [repo for repo in repos if repo.get("owner", {}).get("login") != username]
    for repo in non_owned_repos:
        owner = repo.get("owner", {}).get("login")
        repo_name = repo.get("name")
        stats_url = f"https://api.github.com/repos/{owner}/{repo_name}/stats/contributors"
        stats_response = fila(stats_url, headers)
        if stats_response.status_code != 200:
            msg = f"Não foi possível obter estatísticas para {owner}/{repo_name} (status: {stats_response.status_code})."
            print(msg)
            stats_info += msg + "\n"
            continue
        stats = stats_response.json()
        if not stats:
            msg = f"Estatísticas não disponíveis para {owner}/{repo_name}."
            print(msg)
            stats_info += msg + "\n"
            continue
        for contributor in stats:
            if contributor.get("author", {}).get("login") == username:
                commits = contributor.get("total", 0)
                total_commits += commits
                lines_changed = sum(week.get("a", 0) - week.get("d", 0) for week in contributor.get("weeks", []))
                total_lines_changed += lines_changed
                stats_info += (f"{repo_name} (não próprio): commits = {commits}, linhas alteradas = {lines_changed}\n")
    summary = (f"Total de commits (não próprios): {total_commits}\n"
               f"Total de linhas alteradas (não próprios): {total_lines_changed}")
    stats_info += "\n" + summary
    print("\nEstatísticas para repositórios que NÃO são de propriedade do usuário:")
    print(summary)
    info = [total_commits, total_lines_changed]
    return info


#Estatisticas de repos do usuario que ele é dono e não é dono

def get_repo_participation_stats(username, token):
    headers = {"Authorization": f"token {token}"}
    url = "https://api.github.com/user/repos?per_page=100"
    response = requests.get(url, headers=headers)
    
    participation_info = ""
    if response.status_code != 200:
        err = f"Erro ao buscar repositórios para estatísticas de participação: {response.status_code}"
        print(err)
        participation_info += err
        gb.data_rows.append(("Participação em Repositórios", participation_info))
        return
    repos = response.json()
    total_repos = len(repos)
    owned_repos = [repo for repo in repos if repo.get("owner", {}).get("login") == username]
    non_owned_repos = [repo for repo in repos if repo.get("owner", {}).get("login") != username]
    participation_info += f"Total de repositórios acessíveis: {total_repos}\n"
    participation_info += f"Repositórios não próprios (participação): {len(non_owned_repos)}\n"
    if non_owned_repos:
        participation_info += "Lista de repositórios:\n"
        print("\nEstatísticas de participação em repositórios:")
        print(f"Total de repositórios acessíveis: {total_repos}")
        print(f"Repositórios não próprios (onde o usuário participa): {len(non_owned_repos)}")
        for repo in non_owned_repos:
            repo_line = f"- {repo.get('full_name')}"
            print(repo_line)
            participation_info += repo_line + "\n"
        print(f"Repositórios próprios: {len(owned_repos)}")
        for repo in owned_repos:
            repo_line = f"- {repo.get('full_name')}"
            print(repo_line)
            participation_info += repo_line + "\n"
    
    all_repos = [[],[]] 
    all_repos[1] = [repo.get("full_name") for repo in repos if repo.get("owner", {}).get("login") != username]
    all_repos[0] = [repo.get("full_name") for repo in repos if repo.get("owner", {}).get("login") == username]
    return all_repos
    import os
import csv
import re
import time
import stat
import requests
import platform 
import subprocess
import shutil
from pathlib import Path
import configparser as cfgparser
import OSSanaliser as f1
import SentimentalAnaliser as f2
import StatusAnaliser as f3




config = cfgparser.ConfigParser()
config.read('config.ini')
username = config['github']['username']
token = config['github']['token']

data_rows = []


#função de calculo preliminar caso passe o usuario é apto para o projeto e ira pra segunda parte do projeto
def preliminary(commits_non_owned,lines_of_code, pull_issues, merge_solved):
    pre_point = 0
    if commits_non_owned[0] > 0:
        pre_point += 1
    if lines_of_code[1] > 150000:
        pre_point += 1
    if pull_issues[0] > 0 or pull_issues[1] > 0:
        pre_point += 1
    if merge_solved[0] > 0 or merge_solved[2] > 0:
        pre_point += 1  

    if pre_point > 1:
        return True
    else:
        return False
    

def get_git_commits_info(num_commits=20, repoPath = ""):
    commits_info = ""
    if f1.is_git_repo(repoPath):
        try:
            log_output = subprocess.check_output(
                ["git", "log", "--pretty=format:%H | %an | %ae | %s", "-n", str(num_commits)],
                text=True
            )
            header = f"\nÚltimos {num_commits} commits:\nCommit Hash | Autor | E-mail | Mensagem\n"
            print(header)
            print(log_output)
            commits_info += header + log_output
        except subprocess.CalledProcessError as e:
            err = f"Erro ao executar o comando Git: {e}"
            print(err)
            commits_info += err
    else:
        err = "Erro: O diretório não é um repositório Git válido."
        print(err)
        commits_info += err
    data_rows.append(("Git Commits", commits_info))

def softskillpoints(repoPath,repoName, n):
    
    repos = f1.get_repo_participation_stats(username, token)
    resolved_issues= f1.get_user_resolved_issues_and_prs(username, token, n)
    
    get_git_commits_info(n, repoPath)
    f1.get_user_activity(username, token, repoName, n)

#linha de codigo para que o programa funcione tanto no meu linux e no meu windows
def os_user(username):
    if platform.system() == "Windows":
        path = Path(__file__).resolve().parent
        return path / username
    
    if platform.system() == "Linux":
        path = Path(__file__).resolve().parent
        return path / username

def force_remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

# Modificar a função main para usar a nova função de análise de sentimentos
def main(): 
    n = 20

    gitUserName = username
    pathProjects = os_user(gitUserName)

    if not os.path.exists(pathProjects):
        os.makedirs(pathProjects)

    repoName = f1.get_repo_participation_stats(username, token)
    repo1 = repoName[0]
    repo2 = repoName[1]
    repos = repo1 + repo2

    for r in repos:
        repo_folder_name = r.split('/')[-1]
        repoPath = os.path.join(pathProjects, repo_folder_name)
        # Sair da pasta para evitar erro ao deletar
        os.chdir(os.path.expanduser("~"))

        if os.path.exists(repoPath):
            shutil.rmtree(repoPath, onerror=force_remove_readonly)

        subprocess.run(["git", "clone", f"https://github.com/{r}.git", repoPath])
   
    pulls_issues = f1.get_user_opened_issues_and_prs(username, token, n)
    resolsed_pull_issues = f1.get_user_resolved_issues_and_prs(username, token, n)
    info = f1.get_commit_stats_total(username, token)
    info_non_owned = f1.get_commit_stats_non_owned(username, token)  

    if preliminary(info_non_owned, info, pulls_issues, resolsed_pull_issues):
        data_rows.append(("Preliminar", "O usuário está apto para o projeto"))
        print("O usuário está apto para o projeto")
        # Substituir a chamada antiga pela nova função que inclui análise de sentimentos
        reposi = "D:/Code/GitBlame/Bytsuki0/Python"
        f2.setup_nltk()
        sentiment_scores = []
        for r in repos:
            sentiment_scores.append(f2.get_user_activity_sentiment(token, r, n))
        print(sentiment_scores)
    else:
        data_rows.append(("Preliminar", "O usuário não está apto para o projeto"))
        print("O usuário não está apto para o projeto")
        exit()


if __name__ == "__main__":
    main()
