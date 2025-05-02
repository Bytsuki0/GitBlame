import os
import csv
import re
import time
import requests
import platform 
import subprocess
import configparser
import nltk
from translate import Translator
from nltk.sentiment import SentimentIntensityAnalyzer



config = configparser.ConfigParser()
config.read('config.ini')
username = "Bytsuki0"
token = "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"

data_rows = []


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
    data_rows.append(("Atividade do usuário", activity_info))


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

    data_rows.append(("Issues e Pull Requests resolvidas", resolved_info))
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
    
    data_rows.append(("Issues e Pull Requests resolvidas", resolved_info))

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
        data_rows.append(("Estatísticas Totais", stats_info))
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
    data_rows.append(("Estatísticas Totais", stats_info))
    return info

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
        data_rows.append(("Estatísticas Totais", stats_info))
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
    data_rows.append(("Estatísticas Totais", stats_info))
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
        data_rows.append(("Estatísticas Repositórios Não Próprios", stats_info))
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
    data_rows.append(("Estatísticas Repositórios Não Próprios", stats_info))
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
        data_rows.append(("Participação em Repositórios", participation_info))
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
    
    data_rows.append(("Participação em Repositórios", participation_info))  
    all_repos = [[],[]] 
    all_repos[1] = [repo.get("full_name") for repo in repos if repo.get("owner", {}).get("login") != username]
    all_repos[0] = [repo.get("full_name") for repo in repos if repo.get("owner", {}).get("login") == username]
    return all_repos



#Escrever todos os dados obtividos entro de um csv ou txt isso é pra ser alterado depois
def write_csv(data_rows, filename=f"github_data{username}.csv"):

    csv_path = os.path.join("/home/tsuki/Documentos/Coding/Python-main/IC git blame", filename)
    try:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Categoria", "Dados"])
            for row in data_rows:
                writer.writerow(row)
        print(f"\nDados gravados com sucesso no arquivo: {csv_path}")
    except Exception as e:
        print(f"Erro ao gravar o CSV: {e}")

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
    if is_git_repo(repoPath):
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
    
    repos = get_repo_participation_stats(username, token)
    resolved_issues= get_user_resolved_issues_and_prs(username, token, n)
    
    get_git_commits_info(n, repoPath)
    get_user_activity(username, token, repoName, n)

#linha de codigo para que o programa funcione tanto no meu linux e no meu windows
def os_user(username):
    if platform.system() == "Windows":
        return f"D:/Code/IC/{username}/"

    if platform.system() == "Linux":
        return f'/home/tsuki/Documentos/Coding/{username}/'


def setup_nltk():
    try:
        nltk.data.find('vader_lexicon')
    except LookupError:
        print("Baixando recursos do NLTK necessários...")
        nltk.download('vader_lexicon')
        print("Download concluído.")

# analise de sentimentos de todos os comentarios
def get_user_activity_sentiment(username, token, repoName, num_events):
    setup_nltk()
    headers = {"Authorization": f"token {token}"}
    sia = SentimentIntensityAnalyzer()
    
    activity_info = "\n"
    sentiment_scores = {
        "issues_comments": [],
        "pr_comments": [],
        "commit_comments": []
    }
    
  
    issues_url = f"https://api.github.com/repos/{username}/{repoName}/issues/comments"
    issues_response = requests.get(issues_url, headers=headers)
    
    issues_info = "Comentários em Issues:\n"
    print("\nÚltimos comentários em Issues:")
    
    if issues_response.status_code == 200:
        issues_comments = issues_response.json()
        for comment in issues_comments[:num_events]:
            comment_body = comment.get('body', 'Sem conteúdo')
            translator = Translator(from_lang="pt", to_lang="en")
            translated_body = translator.translate(comment_body)
            sentiment = sia.polarity_scores(comment_body)
            sentiment_scores["issues_comments"].append(sentiment['compound'])
            
            comment_str = (f"- Comentário: {comment_body}\n"
                       f"  Autor: {comment.get('user', {}).get('login', 'Desconhecido')} "
                       f"({comment.get('user', {}).get('html_url', 'Sem URL')})\n"
                       f"  Criado em: {comment.get('created_at', 'Data desconhecida')}\n"
                       f"  Sentimento: {sentiment['compound']:.2f} "
                       f"({'Positivo' if sentiment['compound'] > 0.05 else 'Negativo' if sentiment['compound'] < -0.05 else 'Neutro'})\n")
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
            comment_body = comment.get('body', 'Sem conteúdo')
            sentiment = sia.polarity_scores(comment_body)
            sentiment_scores["pr_comments"].append(sentiment['compound'])
            
            comment_str = (f"- Comentário: {comment_body}\n"
                       f"  Autor: {comment.get('user', {}).get('login', 'Desconhecido')} "
                       f"({comment.get('user', {}).get('html_url', 'Sem URL')})\n"
                       f"  Criado em: {comment.get('created_at', 'Data desconhecida')}\n"
                       f"  Sentimento: {sentiment['compound']:.2f} "
                       f"({'Positivo' if sentiment['compound'] > 0.05 else 'Negativo' if sentiment['compound'] < -0.05 else 'Neutro'})\n")
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
            comment_body = comment.get('body', 'Sem conteúdo')
            sentiment = sia.polarity_scores(comment_body)
            sentiment_scores["commit_comments"].append(sentiment['compound'])
            
            comment_str = (f"- Comentário: {comment_body}\n"
                       f"  Autor: {comment.get('user', {}).get('login', 'Desconhecido')} "
                       f"({comment.get('user', {}).get('html_url', 'Sem URL')})\n"
                       f"  Criado em: {comment.get('created_at', 'Data desconhecida')}\n"
                       f"  Sentimento: {sentiment['compound']:.2f} "
                       f"({'Positivo' if sentiment['compound'] > 0.05 else 'Negativo' if sentiment['compound'] < -0.05 else 'Neutro'})\n")
            print(comment_str)
            commit_info += comment_str + "\n"
    else:
        err = f"Erro ao obter comentários em Commits: {commit_comments_response.status_code}"
        print(err)
        commit_info += err
    activity_info += commit_info


    discussions_url = f"https://api.github.com/repos/{username}/{repoName}/discussions/comments"
    discussions_response = requests.get(discussions_url, headers=headers)
    

    if discussions_response.status_code == 200:
        discussions_info = "\nComentários em Discussões:\n"
        print("\nÚltimos comentários em Discussões:")
        discussions_comments = discussions_response.json()
        sentiment_scores["discussions_comments"] = []
        
        for comment in discussions_comments[:num_events]:
            comment_body = comment.get('body', 'Sem conteúdo')
            sentiment = sia.polarity_scores(comment_body)
            sentiment_scores["discussions_comments"].append(sentiment['compound'])
            
            comment_str = (f"- Comentário: {comment_body}\n"
                       f"  Autor: {comment.get('user', {}).get('login', 'Desconhecido')} "
                       f"({comment.get('user', {}).get('html_url', 'Sem URL')})\n"
                       f"  Criado em: {comment.get('created_at', 'Data desconhecida')}\n"
                       f"  Sentimento: {sentiment['compound']:.2f} "
                       f"({'Positivo' if sentiment['compound'] > 0.05 else 'Negativo' if sentiment['compound'] < -0.05 else 'Neutro'})\n")
            print(comment_str)
            discussions_info += comment_str + "\n"
        
        activity_info += discussions_info
    elif discussions_response.status_code != 404:  # Se não for 404 (não encontrado), é um erro diferente
        err = f"Erro ao obter comentários em Discussões: {discussions_response.status_code}"
        print(err)
        activity_info += err + "\n"

 
    sentiment_averages = {}
    for category, scores in sentiment_scores.items():
        if scores:  
            sentiment_averages[category] = sum(scores) / len(scores)
        else:
            sentiment_averages[category] = 0.0
    
 
    all_scores = []
    for scores in sentiment_scores.values():
        all_scores.extend(scores)
    
    sentiment_averages["geral"] = sum(all_scores) / len(all_scores) if all_scores else 0.0

    print("\nMédias de sentimento por categoria:")
    for category, avg_score in sentiment_averages.items():
        sentiment_type = "Positivo" if avg_score > 0.05 else "Negativo" if avg_score < -0.05 else "Neutro"
        print(f"{category}: {avg_score:.2f} ({sentiment_type})")
    
    # Adicionar médias de sentimento à saída
    sentiment_summary = "\nMédias de sentimento por categoria:\n"
    for category, avg_score in sentiment_averages.items():
        sentiment_type = "Positivo" if avg_score > 0.05 else "Negativo" if avg_score < -0.05 else "Neutro"
        sentiment_summary += f"{category}: {avg_score:.2f} ({sentiment_type})\n"
    
    activity_info += sentiment_summary
    data_rows.append(("Atividade do usuário com análise de sentimentos", activity_info))
    data_rows.append(("Médias de sentimento", sentiment_averages))
    
    return sentiment_averages

# Modificar a função main para usar a nova função de análise de sentimentos
def main(): 
    n = 20

    gitUserName = "Bytsuki0"
    repoName = "Python" 
    pathProjects = os_user(gitUserName)
    
    if not os.path.exists(pathProjects):
        os.makedirs(pathProjects)
    repoPath = os.path.join(pathProjects, repoName)

    
    if not os.path.exists(repoPath):
        subprocess.run(["git", "clone", f"https://github.com/{gitUserName}/{repoName}.git", repoPath])
    os.chdir(repoPath)

    pulls_issues = []
    pulls_issues = get_user_opened_issues_and_prs(username, token, n)
    resolsed_pull_issues = []
    resolsed_pull_issues = get_user_resolved_issues_and_prs(username, token, n)
    info = get_commit_stats_total(username, token)
    info_non_owned = get_commit_stats_non_owned(username, token)  

    
    if preliminary(info_non_owned, info, pulls_issues, resolsed_pull_issues):
        data_rows.append(("Preliminar", "O usuário está apto para o projeto"))
        print("O usuário está apto para o projeto")
        # Substituir a chamada antiga pela nova função que inclui análise de sentimentos
        sentiment_scores = get_user_activity_sentiment(username, token, repoName, n)

    else:
        data_rows.append(("Preliminar", "O usuário não está apto para o projeto"))
        print("O usuário não está apto para o projeto")
        exit()

    write_csv(data_rows)

if __name__ == "__main__":
    main()
