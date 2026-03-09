import streamlit as st
from datetime import date
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    get_materiel, get_personnes, get_mouvements, add_mouvement, add_personne,
    update_materiel, TYPES_MOUVEMENT, STATUS_COLORS, ETATS, TYPES_PERSONNE
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

@st.cache_data(ttl=60)
def load_mv():
    return get_mouvements()

with st.spinner("Chargement…"):
    try:
        df_mat = load_mat()
        df_p   = load_pers()
        df_mv  = load_mv()
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets : {e}")
        st.stop()

if df_mat.empty:
    st.warning("Aucun matériel enregistré. Commencez par ajouter du matériel.")
    st.stop()

# ── Étape 1 : Sélection du matériel ──────────────────────────────────────────
st.subheader("1️⃣ Sélectionner le matériel")

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

display_df = filtered[["ID", "Nom", "Catégorie", "État", "Statut"]].copy()
display_df["Statut"] = display_df["Statut"].apply(lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s}")

selected = st.dataframe(
    display_df, use_container_width=True, hide_index=True,
    on_select="rerun", selection_mode="single-row",
)

if not selected or not selected["selection"]["rows"]:
    st.info("👆 Cliquez sur un article dans le tableau pour continuer.")
    st.stop()

idx    = selected["selection"]["rows"][0]
mat_id = filtered.iloc[idx]["ID"]
row    = df_mat[df_mat["ID"] == mat_id].iloc[0]

st.divider()

c1, c2, c3 = st.columns(3)
c1.metric("Nom", row["Nom"])
c2.metric("Statut", f"{STATUS_COLORS.get(row['Statut'], '⚪')} {row['Statut']}")
c3.metric("État actuel", row["État"])

if row.get("Photo_URL", ""):
    with st.expander("📷 Photo"):
        st.image(row["Photo_URL"], width=200)

st.divider()

# ── Étape 2 : Type de mouvement ───────────────────────────────────────────────
st.subheader("2️⃣ Type de mouvement")

statut_actuel = row["Statut"]
if statut_actuel == "Disponible":
    types_possibles = ["Prêt sortant", "Location", "Vente", "Don sortant",
                       "Mis en réparation", "Hors service"]
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

# État au retour
new_etat = None
if type_mv in ["Retour", "Retour de réparation"]:
    st.divider()
    st.markdown("**📋 État du matériel au retour**")
    etat_actuel_idx = ETATS.index(row["État"]) if row.get("État") in ETATS else 0
    new_etat = st.selectbox(
        "État constaté au retour", ETATS, index=etat_actuel_idx,
        help="Modifiez si l'état du matériel a changé"
    )
    if new_etat != row["État"]:
        st.warning(f"⚠️ L'état passera de **{row['État']}** → **{new_etat}**")
    else:
        st.success(f"✅ État inchangé : **{new_etat}**")

st.divider()

# ── Étape 3 : Personne ────────────────────────────────────────────────────────
need_person  = type_mv not in ["Hors service", "Retour de réparation"]
p_nom_final  = ""
p_contact    = ""
personne_sel = None

if need_person:
    st.subheader("3️⃣ Personne concernée")

    # ── Si retour : chercher la personne du dernier mouvement sortant ─────────
    is_retour = type_mv == "Retour"
    personne_retour_nom     = ""
    personne_retour_contact = ""

    if is_retour and not df_mv.empty:
        types_sortants = ["Prêt sortant", "Location"]
        derniers_sortants = df_mv[
            (df_mv["ID_Matériel"] == mat_id) &
            (df_mv["Type_Mouvement"].isin(types_sortants))
        ].sort_values("Date", ascending=False)

        if not derniers_sortants.empty:
            dernier = derniers_sortants.iloc[0]
            personne_retour_nom     = dernier.get("Personne", "")
            personne_retour_contact = dernier.get("Contact", "")

    if is_retour and personne_retour_nom:
        # Retour : personne pré-remplie, non modifiable
        st.info(f"👤 **{personne_retour_nom}**" +
                (f" · 📞 {personne_retour_contact}" if personne_retour_contact else ""))
        p_nom_final = personne_retour_nom
        p_contact   = personne_retour_contact

    else:
        # Autres mouvements ou retour sans historique : sélection libre
        personnes_liste = ["— Nouvelle personne —"]
        if not df_p.empty:
            for _, r in df_p.iterrows():
                if r.get("Type") == "Professionnel":
                    label = f"{r['Nom']} (Pro) [{r['ID']}]"
                else:
                    label = f"{r['Prénom']} {r['Nom']} ({r['Téléphone']}) [{r['ID']}]"
                personnes_liste.append(label)

        personne_sel = st.selectbox("Sélectionner une personne", personnes_liste)
        p_nom = p_prenom = p_tel = p_email = ""
        p_type_new = "Patient"

        if personne_sel == "— Nouvelle personne —":
            p_type_new = st.selectbox("Type", TYPES_PERSONNE, key="mv_type_new")
            if p_type_new == "Professionnel":
                p_nom    = st.text_input("Nom de la société *")
                p_prenom = ""
                p_tel    = st.text_input("Téléphone")
                p_email  = st.text_input("Email")
            else:
                pc1, pc2 = st.columns(2)
                with pc1:
                    p_nom   = st.text_input("Nom *")
                    p_tel   = st.text_input("Téléphone")
                with pc2:
                    p_prenom = st.text_input("Prénom")
                    p_email  = st.text_input("Email")
        else:
            p_id_sel = personne_sel.split("[")[-1].rstrip("]")
            if not df_p.empty:
                p_row = df_p[df_p["ID"] == p_id_sel]
                if not p_row.empty:
                    pr = p_row.iloc[0]
                    if pr.get("Type") == "Professionnel":
                        p_nom_final = pr.get("Nom", "")
                    else:
                        p_nom_final = f"{pr.get('Prénom','')} {pr.get('Nom','')}".strip()
                    p_contact = pr.get("Téléphone", "")

st.divider()
notes_mv = st.text_area("💬 Notes / Observations", "")

if st.button("💾 Enregistrer le mouvement", type="primary", use_container_width=True):
    errors = []
    if need_person and not is_retour and personne_sel == "— Nouvelle personne —" and not p_nom.strip():
        errors.append("Le nom est obligatoire.")
    if errors:
        for e in errors: st.error(e)
    else:
        with st.spinner("Enregistrement…"):
            if need_person and not is_retour and personne_sel == "— Nouvelle personne —" and p_nom.strip():
                add_personne({
                    "Nom": p_nom.strip(), "Prénom": p_prenom.strip(),
                    "Téléphone": p_tel.strip(), "Email": p_email.strip(),
                    "Type": p_type_new,
                })
                if p_type_new == "Professionnel":
                    p_nom_final = p_nom.strip()
                else:
                    p_nom_final = f"{p_prenom} {p_nom}".strip()
                p_contact = p_tel.strip()

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

            if new_etat and new_etat != row["État"]:
                update_materiel(mat_id, {"État": new_etat})

        st.success(
            f"✅ Mouvement **{type_mv}** enregistré pour **{row['Nom']}**"
            + (f" — {p_nom_final}" if need_person and p_nom_final else "")
            + (f" — État mis à jour : **{new_etat}**" if new_etat and new_etat != row["État"] else "")
        )
        st.cache_data.clear()
