"""Streamlit app: college football win probability (Logistic V1)."""

import json
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(page_title="CFB Win Probability", page_icon="🏈")


@st.cache_resource
def load_model():
    return joblib.load(APP_DIR / "model.joblib")


@st.cache_data
def load_ratings():
    return pd.read_csv(APP_DIR / "team_ratings.csv").set_index("team")


@st.cache_data
def load_metrics():
    return json.loads((APP_DIR / "metrics.json").read_text())


bundle = load_model()
model, features = bundle["model"], bundle["features"]
ratings = load_ratings()
season = int(ratings["season"].iloc[0])
teams = list(ratings.index)

st.title("🏈 College Football Win Probability")
st.write(
    "Pick two teams to get the home team's chance of winning, then optionally "
    "adjust the inputs the model uses."
)

col_home, col_away = st.columns(2)
home = col_home.selectbox("Home team", teams, index=teams.index("Ohio State") if "Ohio State" in teams else 0)
away = col_away.selectbox("Away team", teams, index=teams.index("Michigan") if "Michigan" in teams else 1)

if home == away:
    st.warning("Choose two different teams.")
    st.stop()

h, a = ratings.loc[home], ratings.loc[away]

with st.expander("Model inputs (prefilled from the latest data, editable)", expanded=False):
    st.caption(
        f"Prefilled with {season} season averages and each team's most recent Elo. "
        "PPA = predicted points added per play; for defense, lower is better."
    )
    st.info(
        "**Want current numbers?** The prefilled values are a snapshot and may be out of date. "
        "Look up each team's live offensive PPA, defensive PPA allowed, and Elo on "
        "[collegefootballdata.com/teams](https://collegefootballdata.com/teams), "
        "then type them into the fields below."
    )
    c1, c2 = st.columns(2)
    # Keys include team names so values reset when the selection changes.
    home_off = c1.number_input(f"{home} offensive PPA", value=float(h.off_ppa), step=0.01, format="%.3f", key=f"ho_{home}")
    away_off = c2.number_input(f"{away} offensive PPA", value=float(a.off_ppa), step=0.01, format="%.3f", key=f"ao_{away}")
    home_def = c1.number_input(f"{home} defensive PPA allowed", value=float(h.def_ppa_allowed), step=0.01, format="%.3f", key=f"hd_{home}")
    away_def = c2.number_input(f"{away} defensive PPA allowed", value=float(a.def_ppa_allowed), step=0.01, format="%.3f", key=f"ad_{away}")
    home_elo = c1.number_input(f"{home} Elo", value=float(h.elo), step=10.0, format="%.0f", key=f"he_{home}")
    away_elo = c2.number_input(f"{away} Elo", value=float(a.elo), step=10.0, format="%.0f", key=f"ae_{away}")

row = pd.DataFrame([{
    "home_off_ppa": home_off,
    "away_off_ppa": away_off,
    "home_def_ppa_allowed": home_def,
    "away_def_ppa_allowed": away_def,
    "pregame_elo_diff": home_elo - away_elo,
}])[features]

p_home = float(model.predict_proba(row)[0, 1])

st.subheader("Prediction")
m1, m2 = st.columns(2)
m1.metric(f"{home} (home)", f"{p_home:.1%}")
m2.metric(f"{away} (away)", f"{1 - p_home:.1%}")
st.progress(p_home)
st.caption(f"Predicted winner: **{home if p_home >= 0.5 else away}**")

with st.expander("What's driving this prediction?"):
    contrib = pd.Series(model.coef_[0] * row.iloc[0].values, index=features, name="log-odds contribution")
    st.bar_chart(contrib)
    st.caption(
        f"Positive values favor the home team. Intercept (home-field effect): {model.intercept_[0]:+.2f} log-odds."
    )

with st.expander("About this model"):
    mt = load_metrics()
    st.markdown(
        f"""
**Logistic regression** on five pregame features: both teams' offensive PPA, both
teams' defensive PPA allowed, and the pregame Elo difference (home minus away).

Trained on {mt['train_games']:,} games from 2021-2024 and tested on {mt['test_games']:,}
games from 2025: **{mt['accuracy']:.1%} accuracy**, ROC AUC {mt['roc_auc']:.3f},
log loss {mt['log_loss']:.3f}. For comparison, always picking the home team is right about 58% of the time.

**Limitations**
- Covers FBS teams only (Elo is only available for them).
- It assumes the first team is at home. Neutral-site games are not modeled separately.
- Training used rolling in-season averages; the prefilled values here are full-season
  averages, so treat early-season or post-injury situations with caution.
- Not betting advice.

Data: [CollegeFootballData.com](https://collegefootballdata.com). Live team stats: [collegefootballdata.com/teams](https://collegefootballdata.com/teams).
"""
    )
