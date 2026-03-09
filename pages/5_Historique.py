import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import get_mouvements, TYPES_MOUVEMENT

st.set_page_config(page_title="Historique – ErgoStock", page_icon="📜", layout="wide")
st.title("📜 Historique des mouvements")
st.divider()

@st.cache_data(ttl=30)
def load():
    return get_mouvements()

with st.spinner("Chargement…"):
    df_mv = load()

if df_mv.empty:
    st.info("Aucun mouvement enregistré pour le moment.")
    st.stop()

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

ICONS = {
    "Prêt sortant": "📤", "Retour": "📥", "Achat": "🛒",
    "Don reçu": "🎁", "Prêt entrant": "📦", "Location": "🔵",
    "Vente": "💶", "Don sortant": "❤️", "Mis en réparation": "🔧",
    "Retour de réparation": "✅", "Hors service": "❌",
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
        "Nom_Matériel": "Matériel", "Type_Mouvement": "Mouvement",
        "Date_Retour_Prévu": "Retour prévu", "Date_Retour_Effectif": "Retour effectif",
    }),
    use_container_width=True, hide_index=True,
)

# Lien vers fiche matériel
st.divider()
st.markdown("**🔍 Voir la fiche d'un article :**")

if not filtered.empty:
    noms_par_id = {
        row["ID_Matériel"]: row["Nom_Matériel"]
        for _, row in filtered.drop_duplicates(subset="ID_Matériel").iterrows()
        if row["ID_Matériel"]
    }
    options = {f"[{id}] {nom}": id for id, nom in noms_par_id.items()}
    if options:
        col1, col2 = st.columns([3, 1])
        with col1:
            choix = st.selectbox("Sélectionner un article", list(options.keys()),
                                  label_visibility="collapsed")
        with col2:
            if st.button("🔍 Voir la fiche", type="primary", use_container_width=True):
                st.query_params["mat_id"] = options[choix]
                st.switch_page("pages/3_Fiche_Materiel.py")

st.divider()
csv = filtered.drop(columns=["Date_dt"], errors="ignore").to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Exporter l'historique (CSV)",
    data=csv, file_name="historique_ergostock.csv", mime="text/csv",
)
