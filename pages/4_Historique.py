import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import get_mouvements, get_materiel, TYPES_MOUVEMENT

st.set_page_config(page_title="Historique – ErgoStock", page_icon="📜", layout="wide")
st.title("📜 Historique des mouvements")
st.divider()

@st.cache_data(ttl=30)
def load():
    return get_mouvements(), get_materiel()

with st.spinner("Chargement…"):
    df_mv, df_mat = load()

if df_mv.empty:
    st.info("Aucun mouvement enregistré pour le moment.")
    st.stop()

# ── Filtres ────────────────────────────────────────────────────────────────────
with st.expander("🔍 Filtres", expanded=True):
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        search = st.text_input("Recherche (nom, personne…)", "")
    with fc2:
        types_options = ["Tous"] + TYPES_MOUVEMENT
        filtre_type = st.selectbox("Type de mouvement", types_options)
    with fc3:
        date_debut = st.date_input("Date de début", value=date.today() - timedelta(days=90))
    with fc4:
        date_fin = st.date_input("Date de fin", value=date.today())

filtered = df_mv.copy()

# Filtre date
try:
    filtered["Date_dt"] = pd.to_datetime(filtered["Date"], errors="coerce")
    filtered = filtered[
        (filtered["Date_dt"].dt.date >= date_debut) &
        (filtered["Date_dt"].dt.date <= date_fin)
    ]
except Exception:
    pass

if search:
    mask = (
        filtered["Nom_Matériel"].str.contains(search, case=False, na=False) |
        filtered["Personne"].str.contains(search, case=False, na=False) |
        filtered["ID_Matériel"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

if filtre_type != "Tous":
    filtered = filtered[filtered["Type_Mouvement"] == filtre_type]

filtered = filtered.sort_values("Date", ascending=False)
st.caption(f"**{len(filtered)}** mouvement(s) affiché(s)")

# ── Tableau ────────────────────────────────────────────────────────────────────
ICONS = {
    "Prêt sortant":         "📤",
    "Retour":               "📥",
    "Achat":                "🛒",
    "Don reçu":             "🎁",
    "Prêt entrant":         "📦",
    "Location":             "🔵",
    "Vente":                "💶",
    "Don sortant":          "❤️",
    "Mis en réparation":    "🔧",
    "Retour de réparation": "✅",
    "Hors service":         "❌",
}

display = filtered.copy()
display["Type_Mouvement"] = display["Type_Mouvement"].apply(
    lambda t: f"{ICONS.get(t, '🔄')} {t}"
)

cols_show = [c for c in [
    "Date", "Nom_Matériel", "Type_Mouvement", "Personne",
    "Contact", "Date_Retour_Prévu", "Date_Retour_Effectif", "Notes"
] if c in display.columns]

st.dataframe(
    display[cols_show].rename(columns={
        "Nom_Matériel":         "Matériel",
        "Type_Mouvement":       "Mouvement",
        "Date_Retour_Prévu":    "Retour prévu",
        "Date_Retour_Effectif": "Retour effectif",
    }),
    use_container_width=True,
    hide_index=True,
)

# ── Stats rapides ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("📊 Statistiques sur la période")
if not filtered.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        prets = len(filtered[filtered["Type_Mouvement"].str.contains("Prêt sortant", na=False)])
        st.metric("Prêts sortants", prets)
    with col2:
        retours = len(filtered[filtered["Type_Mouvement"].str.contains("Retour", na=False)])
        st.metric("Retours", retours)
    with col3:
        ventes = len(filtered[filtered["Type_Mouvement"].str.contains("Vente", na=False)])
        st.metric("Ventes", ventes)

    st.bar_chart(
        filtered["Type_Mouvement"].str.replace(r"^[^ ]+ ", "", regex=True)
                                  .value_counts()
    )

# ── Export ─────────────────────────────────────────────────────────────────────
st.divider()
csv = filtered.drop(columns=["Date_dt"], errors="ignore").to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Exporter l'historique (CSV)",
    data=csv,
    file_name="historique_ergostock.csv",
    mime="text/csv",
)
