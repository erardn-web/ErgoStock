import streamlit as st
from datetime import date, datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    add_materiel, CATEGORIES, ETATS,
    add_mouvement, get_personnes, add_personne,
    upload_photo_to_drive, TYPES_PERSONNE
)
from utils.qrcode_utils import generate_qr

st.set_page_config(page_title="Ajouter – ErgoStock", page_icon="➕", layout="centered")
st.title("➕ Ajouter du matériel")
st.divider()

modes_acquisition = ["Achat", "Don reçu", "Prêt entrant"]

with st.form("form_add_materiel", clear_on_submit=True):
    st.subheader("📋 Informations générales")
    c1, c2 = st.columns(2)
    with c1:
        nom       = st.text_input("Nom du matériel *", placeholder="ex : Pince de préhension")
        categorie = st.selectbox("Catégorie *", CATEGORIES)
        etat      = st.selectbox("État *", ETATS)
    with c2:
        mode     = st.selectbox("Mode d'acquisition *", modes_acquisition)
        date_acq = st.date_input("Date d'acquisition *", value=date.today())
        valeur   = st.number_input("Valeur (€)", min_value=0.0, step=0.5, value=0.0)

    description = st.text_area("Description", placeholder="Marque, référence, caractéristiques…")
    notes       = st.text_area("Notes internes", placeholder="Observations…")
    submitted   = st.form_submit_button("💾 Enregistrer le matériel", type="primary")

# Photo en dehors du formulaire
st.divider()
st.markdown("**📷 Photo du matériel**")
photo_source = st.radio("Source", ["📸 Prendre une photo", "🔗 URL existante"], horizontal=True)

photo_url = ""
if photo_source == "📸 Prendre une photo":
    img = st.camera_input("Prenez une photo")
    if img:
        with st.spinner("Upload en cours..."):
            photo_url = upload_photo_to_drive(
                img.getvalue(),
                f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            )
        if photo_url:
            st.success("✅ Photo uploadée !")
            st.image(img, width=200)
else:
    photo_url = st.text_input("URL de la photo", placeholder="https://...")

st.divider()
st.subheader("👤 Provenance (si don ou prêt entrant)")

@st.cache_data(ttl=60)
def load_personnes():
    return get_personnes()

df_p = load_personnes()
personnes_liste = ["— Nouvelle personne —"]
if not df_p.empty:
    for _, r in df_p.iterrows():
        if r.get("Type") == "Professionnel":
            l
