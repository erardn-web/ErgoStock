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

@st.cache_data(ttl=60)
def load_personnes():
    return get_personnes()

modes_acquisition = ["Achat", "Don reçu", "Prêt entrant"]

# Mode d'acquisition HORS formulaire pour rendu dynamique de la section Provenance
mode = st.selectbox("Mode d'acquisition *", modes_acquisition, key="mode_acq")

with st.form("form_add_materiel", clear_on_submit=True):
    st.subheader("📋 Informations générales")
    c1, c2 = st.columns(2)
    with c1:
        nom       = st.text_input("Nom du matériel *", placeholder="ex : Pince de préhension")
        categorie = st.selectbox("Catégorie *", CATEGORIES)
        etat      = st.selectbox("État *", ETATS)
    with c2:
        date_acq = st.date_input("Date d'acquisition *", value=date.today())
        valeur   = st.number_input("Valeur (€)", min_value=0.0, step=0.5, value=0.0)

    description = st.text_area("Description", placeholder="Marque, référence, caractéristiques…")
    notes       = st.text_area("Notes internes", placeholder="Observations…")

    # Provenance — visible uniquement si Don reçu ou Prêt entrant
    personne_sel = "— Nouvelle personne —"
    p_nom = p_prenom = p_tel = ""
    p_type_new = "Patient"

    if mode in ["Don reçu", "Prêt entrant"]:
        st.divider()
        st.markdown("**👤 Provenance**")
        df_p = load_personnes()
        personnes_liste = ["— Nouvelle personne —"]
        if not df_p.empty:
            for _, r in df_p.iterrows():
                if r.get("Type") == "Professionnel":
                    label = f"{r['Nom']} (Pro) [{r['ID']}]"
                else:
                    label = f"{r['Prénom']} {r['Nom']} ({r['ID']})"
                personnes_liste.append(label)

        personne_sel = st.selectbox("Personne (donateur / prêteur)", personnes_liste)

        if personne_sel == "— Nouvelle personne —":
            pc1, pc2 = st.columns(2)
            with pc1:
                p_nom = st.text_input("Nom")
                p_tel = st.text_input("Téléphone")
            with pc2:
                p_prenom = st.text_input("Prénom")

    submitted = st.form_submit_button("💾 Enregistrer le matériel", type="primary", use_container_width=True)

# Type de personne HORS formulaire (dynamique selon sélection)
p_type_new = "Patient"
if mode in ["Don reçu", "Prêt entrant"] and personne_sel == "— Nouvelle personne —":
    p_type_new = st.selectbox("Type de personne", TYPES_PERSONNE, key="acq_type")

# Photo en dernier
st.divider()
st.markdown("**📷 Photo du matériel**")
photo_source = st.radio("Source", ["⏭️ Pas de photo", "📸 Prendre une photo", "🔗 URL existante"], horizontal=True)

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
elif photo_source == "🔗 URL existante":
    photo_url = st.text_input("URL de la photo", placeholder="https://...")

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

            personne_contact   = ""
            personne_nom_final = ""

            if mode in ["Don reçu", "Prêt entrant"]:
                if personne_sel != "— Nouvelle personne —":
                    personne_nom_final = personne_sel.split(" [")[0]
                elif p_nom.strip():
                    add_personne({
                        "Nom": p_nom.strip(), "Prénom": p_prenom.strip(),
                        "Téléphone": p_tel.strip(), "Type": p_type_new,
                    })
                    if p_type_new == "Professionnel":
                        personne_nom_final = p_nom.strip()
                    else:
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
        qr_bytes = generate_qr(f"ERGO-STOCK:{mat_id}")
        st.image(qr_bytes, caption=f"QR Code – {nom} ({mat_id})", width=250)
        st.download_button(
            "⬇️ Télécharger le QR Code (PNG)",
            data=qr_bytes,
            file_name=f"qr_{mat_id}.png",
            mime="image/png",
        )
        st.info("💡 Imprimez ce QR code et collez-le sur le matériel.")
