import os
import csv
import re
import time
import requests
import platform 
import subprocess
import configparser
import gitblame as gb
import requests
import nltk
from translate import Translator
from nltk.sentiment import SentimentIntensityAnalyzer

gb.data_rows = []


def setup_nltk():
    try:
        nltk.data.find('vader_lexicon')
    except LookupError:
        print("Baixando recursos do NLTK necessários...")
        nltk.download('vader_lexicon')
        print("Download concluído.")

def get_user_activity_sentiment(repo_full_name, num_events=10):
    # Preparação
    sia = SentimentIntensityAnalyzer()
    username, repo = repo_full_name.split("/")
    sentiment_scores = {
        "issues_comments": [],
        "pr_comments": [],
        "commit_comments": [],
        "discussions_comments": []
    }

    # URLs públicas (sem cabeçalhos de auth)
    endpoints = {
        "issues_comments": f"https://api.github.com/repos/{username}/{repo}/issues/comments",
        "pr_comments":     f"https://api.github.com/repos/{username}/{repo}/pulls/comments",
        "commit_comments": f"https://api.github.com/repos/{username}/{repo}/comments",
        "discussions_comments": f"https://api.github.com/repos/{username}/{repo}/discussions/comments"
    }

    for key, url in endpoints.items():
        resp = requests.get(url)
        if resp.status_code == 200:
            comments = resp.json()[:num_events]
            for c in comments:
                body = c.get('body', '')
                # traduzindo para inglês antes de analisar
                translated = Translator(from_lang="pt", to_lang="en").translate(body)
                score = sia.polarity_scores(translated)['compound']
                sentiment_scores[key].append(score)
        else:
            print(f"Aviso: não foi possível obter {key} (status {resp.status_code})")

    # Cálculo de médias
    averages = {}
    all_scores = []
    for cat, scores in sentiment_scores.items():
        avg = sum(scores) / len(scores) if scores else 0.0
        averages[cat] = avg
        all_scores += scores
    averages["geral"] = sum(all_scores) / len(all_scores) if all_scores else 0.0

    # Exibição resumida
    for cat, avg in averages.items():
        tipo = ("Positivo"  if avg >  0.05 else
                "Negativo"  if avg < -0.05 else
                "Neutro")
        print(f"{cat}: {avg:.2f} ({tipo})")

    return averages["geral"]
