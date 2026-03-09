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

@st.cache_data(ttl=30)
def load():
    return get_materiel(), get_personnes()

df_mat, df_p = load()

if df_mat.empty:
    st.warning("Aucun matériel enregistré. Commencez par ajouter du matériel.")
    st.stop()

# ── Recherche du matériel ──────────────────────────────────────────────────────
st.subheader("1️⃣ Sélectionner le matériel")
search_mat = st.text_input("Rechercher par nom ou ID", "")

if search_mat:
    mask = (
        df_mat["Nom"].str.contains(search_mat, case=False, na=False) |
        df_mat["ID"].str.contains(search_mat, case=False, na=False)
    )
    df_filtered = df_mat[mask]
else:
    df_filtered = df_mat

if df_filtered.empty:
    st.info("Aucun résultat.")
    st.stop()

mat_options = {
    f"{STATUS_COLORS.get(r['Statut'], '⚪')} [{r['ID']}] {r['Nom']} — {r['Statut']}": r['ID']
    for _, r in df_filtered.iterrows()
}
mat_label = st.selectbox("Matériel", list(mat_options.keys()))
mat_id = mat_options[mat_label]
mat_row = df_mat[df_mat["ID"] == mat_id].iloc[0]

# Infos matériel
c1, c2, c3 = st.columns(3)
c1.metric("Nom", mat_row["Nom"])
c2.metric("Statut actuel", f"{STATUS_COLORS.get(mat_row['Statut'], '⚪')} {mat_row['Statut']}")
c3.metric("Catégorie", mat_row["Catégorie"])

if mat_row.get("Photo_URL", ""):
    with st.expander("📷 Photo"):
        st.image(mat_row["Photo_URL"], width=200)

st.divider()

# ── Type de mouvement ──────────────────────────────────────────────────────────
st.subheader("2️⃣ Type de mouvement")

# Filtrer les types selon le statut actuel
statut_actuel = mat_row["Statut"]
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

st.divider()

# ── Personne ───────────────────────────────────────────────────────────────────
need_person = type_mv not in ["Hors service", "Retour de réparation"]

if need_person:
    st.subheader("3️⃣ Personne concernée")
    personnes_liste = ["— Nouvelle personne —"]
    if not df_p.empty:
        personnes_liste += [
            f"{r['Prénom']} {r['Nom']} ({r['Téléphone']}) [{r['ID']}]"
            for _, r in df_p.iterrows()
        ]

    personne_sel = st.selectbox("Sélectionner une personne", personnes_liste)
    p_id_sel = ""
    p_nom_final = ""
    p_contact = ""

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
        p_row = df_p[df_p["ID"] == p_id_sel].iloc[0] if not df_p.empty else None
        if p_row is not None:
            p_nom_final = f"{p_row.get('Prénom','')} {p_row.get('Nom','')}".strip()
            p_contact   = p_row.get("Téléphone", "")

st.divider()

notes_mv = st.text_area("💬 Notes / Observations", "")

if st.button("💾 Enregistrer le mouvement", type="primary"):
    # Validation
    errors = []
    if need_person and personne_sel == "— Nouvelle personne —" and not p_nom.strip():
        errors.append("Le nom de la personne est obligatoire.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        with st.spinner("Enregistrement…"):
            # Créer la personne si nouvelle
            if need_person and personne_sel == "— Nouvelle personne —" and p_nom.strip():
                new_p_id = add_personne({
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
                "Nom_Matériel":         mat_row["Nom"],
                "Date":                 str(date_mv),
                "Type_Mouvement":       type_mv,
                "Personne":             p_nom_final if need_person else "",
                "Contact":              p_contact   if need_person else "",
                "Date_Retour_Prévu":    str(date_retour) if date_retour else "",
                "Date_Retour_Effectif": str(date_mv) if type_mv == "Retour" else "",
                "Notes":                notes_mv,
            })

        st.success(
            f"✅ Mouvement **{type_mv}** enregistré pour **{mat_row['Nom']}**"
            + (f" — Personne : {p_nom_final}" if need_person and p_nom_final else "")
        )
        st.cache_data.clear()
