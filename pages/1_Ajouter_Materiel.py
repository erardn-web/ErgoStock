import streamlit as st
from datetime import date
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    add_materiel, upload_photo_to_drive,
    CATEGORIES, ETATS, DISPONIBILITES_OPTIONS, encode_disponibilites
)

st.set_page_config(page_title="Ajouter du matériel – ErgoStock", page_icon="➕", layout="centered")
st.title("➕ Ajouter du matériel")
st.divider()

# ── Photo (hors formulaire pour éviter le double submit) ─────────────────────
st.subheader("📷 Photo")
photo_source = st.radio(
    "Source de la photo", ["📸 Prendre une photo", "🔗 Coller une URL", "⏭️ Pas de photo"],
    horizontal=True
)

photo_url = ""
if photo_source == "📸 Prendre une photo":
    img = st.camera_input("Prenez une photo du matériel")
    if img:
        with st.spinner("Upload en cours…"):
            photo_url = upload_photo_to_drive(
                img.getvalue(),
                f"photo_{date.today().strftime('%Y%m%d_%H%M%S')}.jpg"
            )
        if photo_url:
            st.success("✅ Photo uploadée !")
elif photo_source == "🔗 Coller une URL":
    photo_url = st.text_input("URL de la photo")
    if photo_url:
        st.image(photo_url, width=200)

st.divider()

# ── Formulaire principal ──────────────────────────────────────────────────────
st.subheader("📋 Informations")

with st.form("form_add_materiel"):
    c1, c2 = st.columns(2)
    with c1:
        nom  = st.text_input("Nom du matériel *")
        cat  = st.selectbox("Catégorie *", CATEGORIES)
        etat = st.selectbox("État *", ETATS)
    with c2:
        date_acq  = st.date_input("Date d'acquisition", value=date.today())
        mode_acq  = st.selectbox("Mode d'acquisition", ["Achat", "Don reçu", "Prêt entrant", "Autre"])
        valeur    = st.text_input("Valeur (€)")

    desc  = st.text_area("Description")

    st.markdown("**🏷️ Disponibilités**")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        dispo_tester = st.checkbox("🔬 À tester")
    with dc2:
        dispo_preter = st.checkbox("🤝 À prêter")
    with dc3:
        dispo_vendre = st.checkbox("💶 À vendre")

    notes = st.text_area("Notes")

    submit = st.form_submit_button("💾 Enregistrer le matériel", type="primary", use_container_width=True)

if submit:
    if not nom.strip():
        st.error("Le nom du matériel est obligatoire.")
    else:
        dispos_selected = []
        if dispo_tester: dispos_selected.append("À tester")
        if dispo_preter: dispos_selected.append("À prêter")
        if dispo_vendre: dispos_selected.append("À vendre")

        with st.spinner("Enregistrement…"):
            mat_id = add_materiel({
                "Nom":              nom.strip(),
                "Catégorie":        cat,
                "Description":      desc.strip(),
                "État":             etat,
                "Photo_URL":        photo_url,
                "Date_Acquisition": str(date_acq),
                "Mode_Acquisition": mode_acq,
                "Valeur_EUR":       valeur.strip(),
                "Disponibilités":   encode_disponibilites(dispos_selected),
                "Notes":            notes.strip(),
            })

        st.success(f"✅ Matériel **{nom}** enregistré avec l'ID `{mat_id}`.")
        st.cache_data.clear()
