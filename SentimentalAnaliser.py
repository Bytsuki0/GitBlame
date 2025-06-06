import os
import time
import requests
import nltk
from translate import Translator
from nltk.sentiment import SentimentIntensityAnalyzer
import configparser as cfgparser


def setup_nltk():
    try:
        nltk.data.find('vader_lexicon')
    except LookupError:
        print("Baixando recursos do NLTK necessários...")
        nltk.download('vader_lexicon')
        print("Download concluído.")

# Inicialização única de tradutor e analisador de sentimento
translator = Translator(from_lang="pt", to_lang="en")
sia        = SentimentIntensityAnalyzer()

# Sessão HTTP com possível autenticação GitHub
session = requests.Session()
config = cfgparser.ConfigParser()
config.read('config.ini')
username = config['github']['username']
token = config['github']['token']
if token:
    session.headers.update({"Authorization": f"token {token}"})
else:
    print("⚠️  Atenção: variável GITHUB_TOKEN não definida — você ficará limitado a 60 requisições/hora.")


def safe_get(url, max_retries=3, backoff_factor=2):
    """
    Tenta obter a URL até max_retries vezes; em caso de 429, faz backoff exponencial.
    Retorna o objeto Response ou None se falhar.
    """
    for attempt in range(max_retries):
        resp = session.get(url)
        if resp.status_code == 429:
            wait = backoff_factor ** attempt
            print(f"429 recebido, aguardando {wait}s antes da próxima tentativa...")
            time.sleep(wait)
            continue
        return resp
    print(f"❌ Falha ao obter {url} após {max_retries} tentativas")
    return None


def get_user_activity_sentiment(repo_full_name, num_events=10):
    """
    Coleta comentários de issues, PRs, commits e discussões de um repositório GitHub
    e retorna a média geral de sentimento (em escala de -1 a 1).

    Parâmetros:
      - repo_full_name: str no formato "usuario/repositorio"
      - num_events: número máximo de comentários por categoria

    Retorna:
      - float: média composta dos escores de sentimento.
    """
    # Extract username and repo
    username, repo = repo_full_name.split("/")

    # Endpoints públicos para cada tipo de comentário
    endpoints = {
        "issues_comments":      f"https://api.github.com/repos/{username}/{repo}/issues/comments",
        "pr_comments":          f"https://api.github.com/repos/{username}/{repo}/pulls/comments",
        "commit_comments":      f"https://api.github.com/repos/{username}/{repo}/comments"
    }

    sentiment_scores = {key: [] for key in endpoints}

    # Para cada categoria, faz a requisição e processa os comentários
    for key, url in endpoints.items():
        resp = safe_get(url)
        if resp and resp.status_code == 200:
            comments = resp.json()[:num_events]
            for c in comments:
                body = c.get('body', '') or ''
                # Traduz para inglês antes de analisar
                text_en = translator.translate(body)
                score = sia.polarity_scores(text_en)['compound']
                sentiment_scores[key].append(score)
        else:
            status = resp.status_code if resp else 'erro'
            print(f"Aviso: não foi possível obter {key} (status {status})")

    # Cálculo das médias por categoria e geral
    all_scores = []
    averages = {}
    for cat, scores in sentiment_scores.items():
        avg = sum(scores) / len(scores) if scores else 0.0
        averages[cat] = avg
        all_scores.extend(scores)

    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0
    averages['geral'] = overall

    # Exibir resumo
    for cat, avg in averages.items():
        label = "Positivo" if avg > 0.05 else "Negativo" if avg < -0.05 else "Neutro"

    return overall


if __name__ == '__main__':
    setup_nltk()
    repo = input("Informe 'usuario/repositorio' no GitHub: ")
    print("Analisando sentimento...")
    score = get_user_activity_sentiment(repo, num_events=10)
    print(f"Sentimento geral: {score:.2f}")
