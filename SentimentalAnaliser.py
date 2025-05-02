import os
import csv
import re
import time
import requests
import platform 
import subprocess
import configparser
import gitblame as gb
import nltk
import translate
from translate import Translator
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk import download

gb.data_rows = []

def setup_nltk():
    try:
        nltk.data.find('vader_lexicon')
    except LookupError:
        print("Baixando recursos do NLTK necessários...")
        nltk.download('vader_lexicon')
        print("Download concluído.")

# analise de sentimentos de todos os comentarios
def get_user_activity_sentiment(token, repoName, num_events):
    username = repoName.split("/")[0]
    repoName = repoName.split("/")[1]
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
            print(f"Traduzido: {translated_body}")
            sentiment = sia.polarity_scores(translated_body)
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
    

    sentiment = sentiment_averages["geral"]
    return sentiment