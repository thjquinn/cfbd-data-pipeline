"""Train the final model (Logistic V1) and save it for the Streamlit app.

Features, split and settings match notebooks/baseline_model.ipynb:
train on 2021-2024, validate on 2025.
"""

import json
from pathlib import Path

import joblib
import pandas as pd
from config import get_engine
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

FEATURES = [
    "home_off_ppa",
    "away_off_ppa",
    "home_def_ppa_allowed",
    "away_def_ppa_allowed",
    "pregame_elo_diff",
]

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def main():
    df = pd.read_sql(
        "SELECT * FROM vw_game_model_features_v2 ORDER BY season, week",
        get_engine(),
    )

    model_df = df.dropna(subset=FEATURES + ["home_win"]).copy()

    train = model_df["season"] < 2025
    valid = model_df["season"] == 2025

    model = LogisticRegression(max_iter=1000)
    model.fit(model_df.loc[train, FEATURES], model_df.loc[train, "home_win"])

    y_valid = model_df.loc[valid, "home_win"]
    prob = model.predict_proba(model_df.loc[valid, FEATURES])[:, 1]

    metrics = {
        "train_games": int(train.sum()),
        "test_games": int(valid.sum()),
        "accuracy": accuracy_score(y_valid, prob > 0.5),
        "roc_auc": roc_auc_score(y_valid, prob),
        "log_loss": log_loss(y_valid, prob),
    }

    APP_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES}, APP_DIR / "model.joblib")
    (APP_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    print(json.dumps(metrics, indent=2))
    print(dict(zip(FEATURES, model.coef_[0].round(3))), model.intercept_.round(3))


if __name__ == "__main__":
    main()
