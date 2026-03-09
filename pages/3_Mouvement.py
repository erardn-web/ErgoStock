import streamlit as st
from datetime import date
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    get_materiel, get_personnes, add_mouvement, add_personne,
    TYPES_MOUVEMENT, STATUS_COLORS
)

st.set_page_config(page_title="Mouvement – ErgoStock", page_icon="🔄", layout="centered")
st.title("🔄 Enregistrer un mouvement")
st.divider()

@st.cache_data(ttl=60)
def load_mat():
    return get_materiel()

@st.cache_data(ttl=60)
def load_pers():
    return get_personnes()

with st.spinner("Chargement du matériel..."):
    try:
        df_mat = load_mat()
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets : {e}")
        st.stop()

with st.spinner("Chargement des personnes..."):
    try:
        df_p = load_pers()
    except Exception as e:
        df_p = __import__('pandas').DataFrame()

if df_mat.empty:
    st.warning("Aucun matériel enregistré. Commencez par ajouter du matériel.")
    st.stop()

# ── Étape 1 : Sélection du matériel avec filtres ──────────────────────────────
st.subheader("1️⃣ Sélectionner le matériel")

import pandas as pd

with st.expander("🔍 Filtres", expanded=True):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        search = st.text_input("Recherche (nom, ID…)", "")
    with fc2:
        statuts = ["Tous"] + sorted(df_mat["Statut"].dropna().unique().tolist())
        filtre_statut = st.selectbox("Statut", statuts)
    with fc3:
        cats = ["Toutes"] + sorted(df_mat["Catégorie"].dropna().unique().tolist())
        filtre_cat = st.selectbox("Catégorie", cats)

filtered = df_mat.copy()
if search:
    mask = (
        filtered["Nom"].str.contains(search, case=False, na=False) |
        filtered["ID"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if filtre_statut != "Tous":
    filtered = filtered[filtered["Statut"] == filtre_statut]
if filtre_cat != "Toutes":
    filtered = filtered[filtered["Catégorie"] == filtre_cat]

st.caption(f"**{len(filtered)}** article(s)")

# Tableau cliquable
display_df = filtered[["ID", "Nom", "Catégorie", "État", "Statut"]].copy()
display_df["Statut"] = display_df["Statut"].apply(
    lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s}"
)

selected = st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
)

# Vérifier si une ligne est sélectionnée
if not selected or not selected["selection"]["rows"]:
    st.info("👆 Cliquez sur un article dans le tableau pour continuer.")
    st.stop()

idx = selected["selection"]["rows"][0]
mat_id = filtered.iloc[idx]["ID"]
row = df_mat[df_mat["ID"] == mat_id].iloc[0]

st.divider()

# Infos article sélectionné
c1, c2, c3 = st.columns(3)
c1.metric("Nom", row["Nom"])
c2.metric("Statut", f"{STATUS_COLORS.get(row['Statut'], '⚪')} {row['Statut']}")
c3.metric("Catégorie", row["Catégorie"])

if row.get("Photo_URL", ""):
    with st.expander("📷 Photo"):
        st.image(row["Photo_URL"], width=200)

st.divider()

# ── Étape 2 : Type de mouvement ───────────────────────────────────────────────
st.subheader("2️⃣ Type de mouvement")

statut_actuel = row["Statut"]
if statut_actuel == "Disponible":
    types_possibles = ["Prêt sortant", "Location", "Vente", "Don sortant", "Mis en réparation", "Hors service"]
elif statut_actuel in ["En prêt", "En location"]:
    types_possibles = ["Retour"]
elif statut_actuel == "En réparation":
    types_possibles = ["Retour de réparation", "Hors service"]
else:
    types_possibles = TYPES_MOUVEMENT

type_mv = st.selectbox("Type de mouvement", types_possibles)
date_mv = st.date_input("Date du mouvement", value=date.today())

need_retour = type_mv in ["Prêt sortant", "Location"]
date_retour = None
if need_retour:
    date_retour = st.date_input("📅 Date de retour prévue", value=None)

st.divider()

# ── Étape 3 : Personne ────────────────────────────────────────────────────────
need_person = type_mv not in ["Hors service", "Retour de réparation"]
p_nom_final = ""
p_contact = ""

if need_person:
    st.subheader("3️⃣ Personne concernée")

    personnes_liste = ["— Nouvelle personne —"]
    if not df_p.empty:
        personnes_liste += [
            f"{r['Prénom']} {r['Nom']} ({r['Téléphone']}) [{r['ID']}]"
            for _, r in df_p.iterrows()
        ]

    personne_sel = st.selectbox("Sélectionner une personne", personnes_liste)

    if personne_sel == "— Nouvelle personne —":
        pc1, pc2 = st.columns(2)
        with pc1:
            p_nom    = st.text_input("Nom *")
            p_tel    = st.text_input("Téléphone")
            p_email  = st.text_input("Email")
        with pc2:
            p_prenom = st.text_input("Prénom")
            p_type   = st.selectbox("Type", ["Patient", "Famille", "Professionnel", "Autre"])
    else:
        p_id_sel = personne_sel.split("[")[-1].rstrip("]")
        p_row = df_p[df_p["ID"] == p_id_sel] if not df_p.empty else None
        if p_row is not None and not p_row.empty:
            p_nom_final = f"{p_row.iloc[0].get('Prénom','')} {p_row.iloc[0].get('Nom','')}".strip()
            p_contact   = p_row.iloc[0].get("Téléphone", "")

st.divider()

notes_mv = st.text_area("💬 Notes / Observations", "")

if st.button("💾 Enregistrer le mouvement", type="primary", use_container_width=True):
    errors = []
    if need_person and personne_sel == "— Nouvelle personne —" and not p_nom.strip():
        errors.append("Le nom de la personne est obligatoire.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        with st.spinner("Enregistrement…"):
            if need_person and personne_sel == "— Nouvelle personne —" and p_nom.strip():
                add_personne({
                    "Nom":       p_nom.strip(),
                    "Prénom":    p_prenom.strip(),
                    "Téléphone": p_tel.strip(),
                    "Email":     p_email.strip(),
                    "Type":      p_type,
                })
                p_nom_final = f"{p_prenom} {p_nom}".strip()
                p_contact   = p_tel.strip()

            add_mouvement({
                "ID_Matériel":          mat_id,
                "Nom_Matériel":         row["Nom"],
                "Date":                 str(date_mv),
                "Type_Mouvement":       type_mv,
                "Personne":             p_nom_final if need_person else "",
                "Contact":              p_contact   if need_person else "",
                "Date_Retour_Prévu":    str(date_retour) if date_retour else "",
                "Date_Retour_Effectif": str(date_mv) if type_mv == "Retour" else "",
                "Notes":                notes_mv,
            })

        st.success(
            f"✅ Mouvement **{type_mv}** enregistré pour **{row['Nom']}**"
            + (f" — {p_nom_final}" if need_person and p_nom_final else "")
        )
        st.cache_data.clear()
