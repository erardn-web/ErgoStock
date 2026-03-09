import streamlit as st
from datetime import date, datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    add_materiel, CATEGORIES, ETATS,
    TYPES_MOUVEMENT, add_mouvement, get_personnes,
    upload_photo_to_drive
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
        nom = st.text_input("Nom du matériel *", placeholder="ex : Pince de préhension")
        categorie = st.selectbox("Catégorie *", CATEGORIES)
        etat = st.selectbox("État *", ETATS)
    with c2:
        mode = st.selectbox("Mode d'acquisition *", modes_acquisition)
        date_acq = st.date_input("Date d'acquisition *", value=date.today())
        valeur = st.number_input("Valeur (€)", min_value=0.0, step=0.5, value=0.0)

    description = st.text_area("Description", placeholder="Marque, référence, caractéristiques…")
    notes = st.text_area("Notes internes", placeholder="Observations, condition d'utilisation…")

    submitted = st.form_submit_button("💾 Enregistrer le matériel", type="primary")

# Photo en dehors du formulaire pour éviter les conflits avec camera_input
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
    personnes_liste += [
        f"{r['Prénom']} {r['Nom']} ({r['ID']})"
        for _, r in df_p.iterrows()
    ]

personne_sel = st.selectbox("Personne (donateur / prêteur)", personnes_liste)
p_nom = p_prenom = p_tel = ""
if personne_sel == "— Nouvelle personne —":
    pc1, pc2 = st.columns(2)
    with pc1:
        p_nom    = st.text_input("Nom")
        p_tel    = st.text_input("Téléphone")
    with pc2:
        p_prenom = st.text_input("Prénom")

if submitted:
    if not nom.strip():
        st.error("Le nom du matériel est obligatoire.")
    else:
        with st.spinner("Enregistrement en cours…"):
            mat_id = add_materiel({
                "Nom":              nom.strip(),
                "Catégorie":        categorie,
                "Description":      description,
                "État":             etat,
                "Photo_URL":        photo_url.strip(),
                "Date_Acquisition": str(date_acq),
                "Mode_Acquisition": mode,
                "Valeur_EUR":       valeur if valeur > 0 else "",
                "Notes":            notes,
            })

            personne_contact = ""
            personne_nom_final = ""
            if mode in ["Don reçu", "Prêt entrant"]:
                if personne_sel != "— Nouvelle personne —":
                    personne_nom_final = personne_sel
                elif p_nom.strip():
                    from utils.gsheets import add_personne
                    add_personne({
                        "Nom":       p_nom.strip(),
                        "Prénom":    p_prenom.strip(),
                        "Téléphone": p_tel.strip(),
                        "Type":      "Donateur" if mode == "Don reçu" else "Prêteur",
                    })
                    personne_nom_final = f"{p_prenom} {p_nom}".strip()
                    personne_contact = p_tel.strip()

                add_mouvement({
                    "ID_Matériel":    mat_id,
                    "Nom_Matériel":   nom.strip(),
                    "Date":           str(date_acq),
                    "Type_Mouvement": mode,
                    "Personne":       personne_nom_final,
                    "Contact":        personne_contact,
                    "Notes":          notes,
                })

        st.success(f"✅ Matériel **{nom}** ajouté avec l'ID **{mat_id}**")

        st.subheader("🔲 QR Code généré")
        qr_bytes = generate_qr(f"ERGO-STOCK:{mat_id}", size=250)
        st.image(qr_bytes, caption=f"QR Code – {nom} ({mat_id})", width=250)
        st.download_button(
            "⬇️ Télécharger le QR Code (PNG)",
            data=qr_bytes,
            file_name=f"qr_{mat_id}.png",
            mime="image/png",
        )
        st.info("💡 Imprimez ce QR code et collez-le sur le matériel.")
