import os
import subprocess
import json
from datetime import datetime, timedelta
from collections import defaultdict
import re
from typing import Dict, List, Tuple, Set, Optional, Union, Any

class GitHubStatsAnalyzer:
    """
    Classe para analisar estatísticas de contribuição em repositórios Git
    usando PyDrill para processar os dados.
    """
    
    def __init__(self, repositories_path: str):
        """
        Inicializa o analisador de estatísticas do GitHub.
        
        Args:
            repositories_path: Caminho para a pasta que contém os repositórios a serem analisados
        """
        self.repositories_path = repositories_path
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
            match = re.search(r'github\.com[:/]([^/]+)', remote_url)
            if match:
                return match.group(1)
        
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
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Email do usuário atual
        """
        return self._run_git_command(repo_path, ['config', 'user.email'])
    
    def _get_repository_permissions(self, repo_path: str) -> Dict[str, str]:
        """
        Verifica as permissões do usuário atual no repositório.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Dicionário com informações de permissão
        """
        user_email = self._get_current_user_email(repo_path)
        owner = self._get_repository_owner(repo_path)
        
        # Verifica se o usuário tem commits no repositório
        contributors = self._get_repository_contributors(repo_path)
        has_commits = user_email in contributors
        
        # Verifica se o usuário tem permissão de escrita (simplificado)
        # Em um cenário real, seria necessário verificar as permissões do GitHub API
        try:
            # Tenta criar um arquivo temporário e depois remove
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
            'is_owner': user_email == owner,  # Simplificado
            'has_commits': has_commits,
            'commit_count': contributors.get(user_email, 0) if has_commits else 0,
            'has_write_permission': has_write_permission
        }
    
    def _get_lines_changed(self, repo_path: str) -> int:
        """
        Calcula o total de linhas alteradas pelo usuário atual no repositório.
        
        Args:
            repo_path: Caminho para o repositório
            
        Returns:
            Número total de linhas alteradas
        """
        user_email = self._get_current_user_email(repo_path)
        output = self._run_git_command(repo_path, ['log', '--author=' + user_email, '--stat', 'HEAD'])
        
        total_lines = 0
        for line in output.split('\n'):
            match = re.search(r'(\d+) files? changed, (\d+) insertions?\(\+\), (\d+) deletions?\(-\)', line)
            if match:
                _, insertions, deletions = match.groups()
                total_lines += int(insertions) + int(deletions)
        
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
        
        # Obtém todos os commits do usuário
        output = self._run_git_command(
            repo_path, 
            ['log', '--author=' + user_email, '--since=' + start_date_str, '--until=' + end_date_str, '--format=%ad', '--date=format:%Y-%m']
        )
        
        # Agrupa por mês
        monthly_contributions = defaultdict(int)
        for line in output.split('\n'):
            if line.strip():
                monthly_contributions[line] += 1
        
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
        
        # Obtém todos os commits do usuário no último ano
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
            if not repo_data['is_owner'] and repo_data['commit_percentage'] >= criteria['commit_percentage']:
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
def check_github_achievements(repositories_path: str, criteria: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Verifica os objetivos do GitHub com base nos critérios fornecidos.
    
    Args:
        repositories_path: Caminho para a pasta que contém os repositórios
        criteria: Critérios específicos para verificar os objetivos
        
    Returns:
        Dicionário com os resultados
    """
    analyzer = GitHubStatsAnalyzer(repositories_path)
    analyzer.analyze_all_repositories()
    achievements = analyzer.check_achievements(criteria)
    
    return {
        'achievements': achievements,
        'repository_stats': analyzer.results,
        'criteria_used': criteria
    }


# Exemplo de uso
if __name__ == "__main__":
    # Caminho para a pasta que contém os repositórios
    repo_path = "D:\Code\GitBlame\Python"
    
    # Critérios personalizados
    custom_criteria = {
        'lines_changed': 500,             # Alterou 500+ linhas em um repositório
        'monthly_streak_single': 6,       # Participou de um repositório por 6+ meses
        'monthly_streak_multiple': 3,     # Participou de 2+ repositórios por 3+ meses
        'weekly_streak': 5,               # Sequência de 5+ contribuições semanais
        'edit_rights_non_owner': True,    # Tem direitos de edição em repo não próprio
        'commit_percentage': 25           # Tem 25%+ dos commits em repo não próprio
    }
    
    # Executa a análise
    analyzer = GitHubStatsAnalyzer(repo_path)
    results = analyzer.analyze_all_repositories()
    achievements = analyzer.check_achievements(custom_criteria)
    
    # Exibe os resultados
    print(json.dumps(achievements, indent=2))
    
    # Para exportar os resultados completos para um arquivo
    with open('github_achievements.json', 'w') as f:
        f.write(analyzer.get_results_as_json(custom_criteria))