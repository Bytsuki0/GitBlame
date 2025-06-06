import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

import OSSanaliser
from StatusAnaliser import GitHubStatsAnalyzerAllTime
import SentimentalAnaliser

import configparser


cfg = configparser.ConfigParser()
cfg.read("config.ini")
USERNAME = cfg["github"].get("username", "").strip()
TOKEN    = cfg["github"].get("token", "").strip()

if not (USERNAME and TOKEN):
    st.error("Preencha seu username e token GitHub.")
    st.stop()

@st.cache_data(ttl=3600)
def load_participation_stats(username: str):
    """
    Chama OSSanaliser.get_repo_participation_stats(username)
    Retorna: (owned_list, non_owned_list)
    """
    return OSSanaliser.get_repo_participation_stats(username)


@st.cache_data(ttl=3600)
def load_status_per_repo(username: str, token: str):
    """
    Instancia GitHubStatsAnalyzerAllTime e chama analyze_all().
    Retorna: dict { reponame: { ..., "Total_commits": int, ... }, ... }
    """
    analyzer = GitHubStatsAnalyzerAllTime(username, token)
    return analyzer.analyze_all()


@st.cache_data(ttl=3600)
def load_sentiment_for_repos(repo_list, num_events=10):
    """
    Para cada full repo (formato 'username/reponame'), chama
    SentimentalAnaliser.get_user_activity_sentiment.
    Retorna: dict { "username/reponame": sentiment_float }
    """
    SentimentalAnaliser.setup_nltk()
    result = {}
    for full_name in repo_list:
        score = SentimentalAnaliser.get_user_activity_sentiment(full_name, num_events)
        result[full_name] = score
    return result


# ────────────────────────────────────────────────────────────────────────


def main():
    st.title("📊 GitBlame Dashboard")
    st.markdown(
        """
        Dashboard:
        1. Quantos repositórios você possui vs. quantos você colabora.
        2. Distribuição percentual de commits por repositório.
        3. Sentimento médio (Issues / PRs / Commits) em cada repositório.
        """
    )
    st.write("---")

    st.subheader("1. Seus repositórios: Próprios vs. Colaborações")
    with st.spinner("Carregando lista de repositórios..."):
        owned_repos, non_owned_repos = load_participation_stats(USERNAME)

    st.write(
        f"- Você possui **{len(owned_repos)}** repositórios.\n"
        f"- Você colabora em **{len(non_owned_repos)}** repositórios."
    )

    df_participation = pd.DataFrame({
        "Tipo": ["Próprios", "Colaborando"],
        "Quantidade": [len(owned_repos), len(non_owned_repos)]
    })

    fig1, ax1 = plt.subplots()
    ax1.pie(
        df_participation["Quantidade"],
        labels=df_participation["Tipo"],
        autopct="%1.1f%%",
        startangle=90
    )
    ax1.axis("equal")
    st.pyplot(fig1)

    st.write("---")

    st.subheader("2. Distribuição de commits por repositório")
    with st.spinner("Buscando estatísticas de commits por repositório..."):
        status_per_repo = load_status_per_repo(USERNAME, TOKEN)

    commit_data = {"Repositório": [], "Total_Commits": []}
    for repo_name, stats in status_per_repo.items():
        commit_data["Repositório"].append(repo_name)
        commit_data["Total_Commits"].append(stats.get("Total_commits", 0))

    df_commits = pd.DataFrame(commit_data)
    total_all_commits = df_commits["Total_Commits"].sum()

    if total_all_commits == 0:
        st.warning("⚠️ Nenhum commit encontrado (soma total de commits = 0).")
    else:
        df_commits["Percentual"] = df_commits["Total_Commits"] / total_all_commits * 100
        df_commits = df_commits.sort_values("Total_Commits", ascending=False).reset_index(drop=True)

        st.write("Tabela: commits por repositório")
        st.dataframe(df_commits[["Repositório", "Total_Commits", "Percentual"]])

        top_n = 5
        df_top = df_commits.head(top_n).copy()
        if len(df_commits) > top_n:
            others = df_commits.iloc[top_n:]
            outros_row = pd.DataFrame([{
                "Repositório": "Outros",
                "Total_Commits": others["Total_Commits"].sum(),
                "Percentual":   others["Percentual"].sum()
            }])
            df_top = pd.concat([df_top, outros_row], ignore_index=True)


        fig2, ax2 = plt.subplots()
        ax2.pie(
            df_top["Percentual"],
            labels=df_top["Repositório"],
            autopct="%1.1f%%",
            startangle=90
        )
        ax2.axis("equal")
        st.pyplot(fig2)

    st.write("---")


    st.subheader("3. Sentimento médio (Issues/PRs/Commits) por repositório")


    repo_full_names = [ f"{USERNAME}/{repo_name}" for repo_name in status_per_repo.keys() ]
    with st.spinner("Calculando sentimento nos comentários (pode demorar um pouco)..."):
        sentiment_dict = load_sentiment_for_repos(repo_full_names, num_events=10)
    df_sentiment = pd.DataFrame({
        "Repositório": [full.split("/")[1] for full in sentiment_dict.keys()],
        "Sentimento": list(sentiment_dict.values())
    })
    df_sentiment = df_sentiment.sort_values("Sentimento", ascending=False).reset_index(drop=True)
    st.write("Tabela: sentimento médio (quanto mais próximo de +1, mais positivo).")
    st.dataframe(df_sentiment)

    if not df_sentiment.empty:
        fig3, ax3 = plt.subplots(figsize=(8, max(4, 0.5 * len(df_sentiment))))
        ax3.barh(df_sentiment["Repositório"], df_sentiment["Sentimento"])
        ax3.set_xlabel("Sentimento (–1 a +1)")
        ax3.set_xlim([-1,1])
        ax3.axvline(x=0, color='red', linestyle='--', linewidth=2)
        ax3.set_ylabel("Repositório")
        ax3.set_title("Sentimento médio dos comentários por repositório")
        st.pyplot(fig3)

if __name__ == "__main__":
    main()

