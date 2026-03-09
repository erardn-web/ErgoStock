import streamlit as st
from datetime import date
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    get_materiel, get_personnes, add_mouvement, add_personne,
    update_materiel, STATUS_COLORS, ETATS, TYPES_PERSONNE
)

st.set_page_config(
    page_title="Scanner QR – ErgoStock",
    page_icon="📷",
    layout="centered"
)
st.title("📷 Scanner un QR Code")
st.caption("Pointez la caméra vers le QR code collé sur le matériel.")
st.divider()

try:
    from streamlit_qrcode_scanner import qrcode_scanner
except ImportError:
    st.error("La librairie de scan QR n'est pas installée.")
    st.stop()

qr_data = qrcode_scanner(key="qr_scanner")

if not qr_data:
    st.info("👆 Activez la caméra et scannez un QR code ErgoStock.")
    st.markdown("""
    **Comment utiliser :**
    1. Autorisez l'accès à la caméra si demandé
    2. Pointez vers le QR code collé sur le matériel
    3. Le matériel sera reconnu automatiquement
    4. Enregistrez votre mouvement
    """)
    st.stop()

raw    = qr_data.strip()
mat_id = None
if raw.startswith("ERGO-STOCK:"):
    mat_id = raw.replace("ERGO-STOCK:", "").strip()
elif "mat_id=" in raw:
    mat_id = raw.split("mat_id=")[-1].strip()
else:
    mat_id = raw.strip()

@st.cache_data(ttl=30)
def load_mat():
    return get_materiel()

@st.cache_data(ttl=30)
def load_pers():
    return get_personnes()

with st.spinner("Recherche du matériel..."):
    df_mat = load_mat()

if df_mat.empty:
    st.error("Aucun matériel dans la base.")
    st.stop()

found = df_mat[df_mat["ID"] == mat_id]
if found.empty:
    st.error(f"❌ Matériel non trouvé pour le code : `{mat_id}`")
    st.stop()

row = found.iloc[0]

st.success("✅ Matériel identifié !")
st.divider()

col1, col2 = st.columns([1, 2])
with col1:
    photo = row.get("Photo_URL", "")
    if photo and photo.startswith("http"):
        st.image(photo, use_container_width=True)
    else:
        st.markdown(
            "<div style='background:#f0f2f6;border-radius:8px;"
            "padding:30px;text-align:center;font-size:2rem;'>📦</div>",
            unsafe_allow_html=True
        )
with col2:
    st.markdown(f"## {row['Nom']}")
    st.markdown(f"**ID :** `{row['ID']}`")
    st.markdown(f"**Catégorie :** {row.get('Catégorie', '')}")
    st.markdown(f"**État :** {row.get('État', '')}")
    statut = row.get('Statut', '')
    st.markdown(f"**Statut :** {STATUS_COLORS.get(statut, '⚪')} **{statut}**")

st.divider()
st.subheader("⚡ Enregistrer un mouvement rapide")

statut_actuel = row.get("Statut", "Disponible")
if statut_actuel == "Disponible":
    types_possibles = ["Prêt sortant", "Location", "Vente", "Don sortant", "Mis en réparation"]
elif statut_actuel in ["En prêt", "En location"]:
    types_possibles = ["Retour"]
elif statut_actuel == "En réparation":
    types_possibles = ["Retour de réparation", "Hors service"]
else:
    types_possibles = ["Prêt sortant", "Retour", "Location", "Vente", "Don sortant"]

type_mv = st.selectbox("Type de mouvement", types_possibles)
date_mv = st.date_input("Date", value=date.today())

need_retour = type_mv in ["Prêt sortant", "Location"]
date_retour = None
if need_retour:
    date_retour = st.date_input("Date de retour prévue", value=None)

new_etat = None
if type_mv in ["Retour", "Retour de réparation"]:
    st.markdown("**📋 État au retour**")
    etat_idx = ETATS.index(row["État"]) if row.get("État") in ETATS else 0
    new_etat = st.selectbox("État constaté", ETATS, index=etat_idx)
    if new_etat != row["État"]:
        st.warning(f"⚠️ **{row['État']}** → **{new_etat}**")

need_person  = type_mv not in ["Hors service", "Retour de réparation"]
p_nom_final  = ""
p_contact    = ""
personne_sel = None

if need_person:
    st.markdown("**👤 Personne concernée**")
    df_p = load_pers()

    personnes_liste = ["— Nouvelle personne —"]
    if not df_p.empty:
        for _, r in df_p.iterrows():
            if r.get("Type") == "Professionnel":
                label = f"{r['Nom']} (Pro) [{r['ID']}]"
            else:
                label = f"{r['Prénom']} {r['Nom']} ({r['Téléphone']}) [{r['ID']}]"
            personnes_liste.append(label)

    personne_sel = st.selectbox("Personne", personnes_liste)
    p_nom = p_prenom = p_tel = ""
    p_type_new = "Patient"

    if personne_sel == "— Nouvelle personne —":
        p_type_new = st.selectbox("Type", TYPES_PERSONNE, key="qr_type_new")
        if p_type_new == "Professionnel":
            p_nom    = st.text_input("Nom de la société *")
            p_prenom = ""
            p_tel    = st.text_input("Téléphone")
        else:
            c1, c2 = st.columns(2)
            with c1:
                p_nom = st.text_input("Nom *")
                p_tel = st.text_input("Téléphone")
            with c2:
                p_prenom = st.text_input("Prénom")
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

notes_mv = st.text_area("Notes", placeholder="Observations…")

if st.button("💾 Enregistrer", type="primary", use_container_width=True):
    errors = []
    if need_person and personne_sel == "— Nouvelle personne —" and not p_nom.strip():
        errors.append("Le nom est obligatoire.")
    if errors:
        for e in errors: st.error(e)
    else:
        with st.spinner("Enregistrement..."):
            if need_person and personne_sel == "— Nouvelle personne —" and p_nom.strip():
                add_personne({
                    "Nom": p_nom.strip(), "Prénom": p_prenom.strip(),
                    "Téléphone": p_tel.strip(), "Type": p_type_new,
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

        st.success(f"✅ **{type_mv}** enregistré pour **{row['Nom']}** !")
        st.balloons()
        st.cache_data.clear()
