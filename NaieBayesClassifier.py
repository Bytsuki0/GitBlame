import os
import json
import ast
import joblib
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report

CSV_PATH = Path(r"D:/Code/GitBlame/programmer_profiles.json.csv")
OUT_DIR = Path(r"D:/Code/GitBlame/model_out")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_profile_str(s):
    """
    Try several ways to convert the CSV cell into a Python dict:
     1) json.loads
     2) ast.literal_eval (accepts single quotes / python literals)
     3) strip outer quotes and replace doubled quotes -> json.loads
    Returns a dict (empty dict on failure).
    """
    if s is None:
        return {}
    if isinstance(s, dict):
        return s
    s = str(s).strip()
    if s == "" or s.lower() == "nan":
        return {}
    # try json
    try:
        return json.loads(s)
    except Exception:
        pass
    # try python literal
    try:
        return ast.literal_eval(s)
    except Exception:
        pass
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s2 = s[1:-1]
        s2 = s2.replace('""', '"')
        try:
            return json.loads(s2)
        except Exception:
            try:
                return ast.literal_eval(s2)
            except Exception:
                return {}
    return {}


if not CSV_PATH.exists():
    raise FileNotFoundError(f"CSV not found: {CSV_PATH}")


df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)  # keep strings


if 'profile' not in df.columns or 'programmer_type' not in df.columns:
    df = pd.read_csv(CSV_PATH, header=None, names=['profile', 'programmer_type'], dtype=str, keep_default_na=False)


df['profile_dict'] = df['profile'].apply(parse_profile_str)

all_languages = sorted({lang for d in df['profile_dict'] for lang in d.keys()})

feature_cols = []
for lang in all_languages:
    feature_cols.append(f"{lang}_lines")
    feature_cols.append(f"{lang}_projects")

def flatten_profile(d):
    row = []
    for lang in all_languages:
        v = d.get(lang)
        if isinstance(v, (list, tuple)) and len(v) >= 1:
            try:
                row.append(float(v[0]))
            except Exception:
                row.append(0.0)
        else:
            row.append(0.0)

        if isinstance(v, (list, tuple)) and len(v) >= 2:
            try:
                row.append(float(v[1]))
            except Exception:
                row.append(0.0)
        else:
            row.append(0.0)
    return row

X_list = df['profile_dict'].apply(flatten_profile).tolist()
X = pd.DataFrame(X_list, columns=feature_cols)
y = df['programmer_type'].astype(str)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)


try:
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
except ValueError:
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )


model = GaussianNB()
model.fit(X_train, y_train)

preds = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, preds))
print("Classification report:")
print(classification_report(y_test, preds, zero_division=0))

joblib.dump(model, OUT_DIR / "naive_bayes_programmer.pkl")
joblib.dump(scaler, OUT_DIR / "scaler_programmer.pkl")
(OUT_DIR / "feature_columns.json").write_text(json.dumps(feature_cols, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Saved model, scaler and feature_columns to {OUT_DIR}")

def predict_from_profile_string(profile_str):
    prof = parse_profile_str(profile_str)
    vec = flatten_profile(prof)
    import numpy as np
    v = np.array(vec).reshape(1, -1)
    v_scaled = scaler.transform(v)
    return model.predict(v_scaled)[0]


sample = '{"Go": [241388, 261], "Just": [54643, 9], "Dockerfile": [27748, 6], "PLpgSQL": [19499, 1], "Python": [3629, 57], "Shell": [12242, 155], "PHP": [21, 0]}'
print("Demo sample prediction ->", predict_from_profile_string(sample))
