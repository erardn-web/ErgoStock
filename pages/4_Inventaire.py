import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import get_materiel, STATUS_COLORS

st.set_page_config(page_title="Inventaire – ErgoStock", page_icon="📦", layout="wide")
st.title("📦 Inventaire du matériel")
st.divider()

@st.cache_data(ttl=30)
def load():
    return get_materiel()

with st.spinner("Chargement…"):
    df = load()

if df.empty:
    st.info("Aucun matériel enregistré. Utilisez Ajouter du matériel pour commencer.")
    st.stop()

with st.expander("🔍 Filtres", expanded=True):
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        search = st.text_input("Recherche (nom, description…)", "")
    with fc2:
        statuts = ["Tous"] + sorted(df["Statut"].dropna().unique().tolist())
        filtre_statut = st.selectbox("Statut", statuts)
    with fc3:
        cats = ["Toutes"] + sorted(df["Catégorie"].dropna().unique().tolist())
        filtre_cat = st.selectbox("Catégorie", cats)
    with fc4:
        etats = ["Tous"] + sorted(df["État"].dropna().unique().tolist())
        filtre_etat = st.selectbox("État", etats)

filtered = df.copy()
if search:
    mask = (
        filtered["Nom"].str.contains(search, case=False, na=False) |
        filtered["Description"].str.contains(search, case=False, na=False) |
        filtered["ID"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if filtre_statut != "Tous":
    filtered = filtered[filtered["Statut"] == filtre_statut]
if filtre_cat != "Toutes":
    filtered = filtered[filtered["Catégorie"] == filtre_cat]
if filtre_etat != "Tous":
    filtered = filtered[filtered["État"] == filtre_etat]

st.caption(f"**{len(filtered)}** article(s) affiché(s)")

view_mode = st.radio("Affichage", ["🗂️ Tableau", "🖼️ Galerie"], horizontal=True)

if view_mode == "🗂️ Tableau":
    display_df = filtered[["ID", "Nom", "Catégorie", "État", "Statut",
                             "Date_Acquisition", "Mode_Acquisition", "Valeur_EUR"]].copy()
    display_df["Statut"] = display_df["Statut"].apply(
        lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s}"
    )
    selected = st.dataframe(
        display_df, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row",
    )
    if selected and selected["selection"]["rows"]:
        idx    = selected["selection"]["rows"][0]
        mat_id = filtered.iloc[idx]["ID"]
        st.query_params["mat_id"] = mat_id
        st.switch_page("pages/3_Fiche_Materiel.py")

else:
    cols_per_row = 3
    items = filtered.to_dict("records")
    for i in range(0, len(items), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, item in enumerate(items[i:i+cols_per_row]):
            with cols[j]:
                st.markdown(f"### {STATUS_COLORS.get(item.get('Statut',''), '⚪')} {item.get('Nom','?')}")
                photo = item.get("Photo_URL", "")
                if photo and photo.startswith("http"):
                    st.image(photo, use_container_width=True)
                else:
                    st.markdown("*Pas de photo*")
                st.caption(
                    f"**ID :** {item.get('ID','')}  \n"
                    f"**Catégorie :** {item.get('Catégorie','')}  \n"
                    f"**État :** {item.get('État','')}  \n"
                    f"**Statut :** {item.get('Statut','')}"
                )
                if st.button("🔍 Voir la fiche", key=f"btn_{item['ID']}"):
                    st.query_params["mat_id"] = item["ID"]
                    st.switch_page("pages/3_Fiche_Materiel.py")

st.divider()
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Exporter la sélection (CSV)",
    data=csv, file_name="inventaire_ergostock.csv", mime="text/csv",
)
