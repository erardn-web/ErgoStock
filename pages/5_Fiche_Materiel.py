import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    get_materiel, get_historique_materiel, update_materiel,
    STATUS_COLORS, CATEGORIES, ETATS, upload_photo_to_drive
)
from utils.qrcode_utils import generate_qr

st.set_page_config(page_title="Fiche matériel – ErgoStock", page_icon="🔍", layout="wide")
st.title("🔍 Fiche matériel")
st.divider()

@st.cache_data(ttl=30)
def load():
    return get_materiel()

df_mat = load()

if df_mat.empty:
    st.info("Aucun matériel enregistré.")
    st.stop()

params = st.query_params
preselect_id = params.get("mat_id", "")

mat_options = {
    f"[{r['ID']}] {r['Nom']}": r['ID']
    for _, r in df_mat.iterrows()
}

default_idx = 0
if preselect_id:
    keys = list(mat_options.keys())
    ids  = list(mat_options.values())
    if preselect_id in ids:
        default_idx = ids.index(preselect_id)

mat_label = st.selectbox("Choisir un article", list(mat_options.keys()), index=default_idx)
mat_id = mat_options[mat_label]
row = df_mat[df_mat["ID"] == mat_id].iloc[0]

st.divider()

col_photo, col_info, col_qr = st.columns([2, 3, 2])

with col_photo:
    st.subheader("📷 Photo")
    photo = row.get("Photo_URL", "")
    if photo and photo.startswith("http"):
        st.image(photo, use_container_width=True)
    else:
        st.markdown(
            "<div style='background:#f0f2f6;border-radius:8px;padding:40px;"
            "text-align:center;color:#999;'>Pas de photo</div>",
            unsafe_allow_html=True,
        )

with col_info:
    st.subheader(f"{STATUS_COLORS.get(row['Statut'], '⚪')} {row['Nom']}")
    st.markdown(f"**ID :** `{row['ID']}`")
    data_display = {
        "Catégorie":          row.get("Catégorie", ""),
        "Description":        row.get("Description", ""),
        "État":               row.get("État", ""),
        "Statut":             row.get("Statut", ""),
        "Date d'acquisition": row.get("Date_Acquisition", ""),
        "Mode d'acquisition": row.get("Mode_Acquisition", ""),
        "Valeur (€)":         row.get("Valeur_EUR", ""),
        "Notes":              row.get("Notes", ""),
    }
    for k, v in data_display.items():
        if v:
            st.markdown(f"**{k} :** {v}")

with col_qr:
    st.subheader("🔲 QR Code")
    qr_bytes = generate_qr(f"ERGO-STOCK:{mat_id}", size=250)
    st.image(qr_bytes, width=200)
    st.download_button(
        "⬇️ Télécharger le QR Code",
        data=qr_bytes,
        file_name=f"qr_{mat_id}.png",
        mime="image/png",
    )
    st.caption("Collez cette étiquette sur le matériel.")

st.divider()

st.subheader("📜 Historique de cet article")
hist = get_historique_materiel(mat_id)
if hist.empty:
    st.info("Aucun mouvement enregistré pour cet article.")
else:
    ICONS = {
        "Prêt sortant":         "📤",
        "Retour":               "📥",
        "Achat":                "🛒",
        "Don reçu":             "🎁",
        "Prêt entrant":         "📦",
        "Location":             "🔵",
        "Vente":                "💶",
        "Don sortant":          "❤️",
        "Mis en réparation":    "🔧",
        "Retour de réparation": "✅",
        "Hors service":         "❌",
    }
    hist["Type_Mouvement"] = hist["Type_Mouvement"].apply(
        lambda t: f"{ICONS.get(t, '🔄')} {t}"
    )
    cols = [c for c in ["Date", "Type_Mouvement", "Personne", "Contact",
                         "Date_Retour_Prévu", "Date_Retour_Effectif", "Notes"]
            if c in hist.columns]
    st.dataframe(hist[cols], use_container_width=True, hide_index=True)

st.divider()

with st.expander("✏️ Modifier les informations"):
    with st.form("form_edit"):
        e1, e2 = st.columns(2)
        with e1:
            new_nom  = st.text_input("Nom", value=row.get("Nom", ""))
            new_cat  = st.selectbox("Catégorie", CATEGORIES,
                                    index=CATEGORIES.index(row["Catégorie"])
                                    if row.get("Catégorie") in CATEGORIES else 0)
            new_etat = st.selectbox("État", ETATS,
                                    index=ETATS.index(row["État"])
                                    if row.get("État") in ETATS else 0)
        with e2:
            new_val   = st.text_input("Valeur (€)", value=str(row.get("Valeur_EUR", "")))

        new_desc  = st.text_area("Description", value=row.get("Description", ""))
        new_notes = st.text_area("Notes", value=row.get("Notes", ""))
        save_btn  = st.form_submit_button("💾 Enregistrer les modifications", type="primary")

    # Photo en dehors du formulaire
    st.markdown("**📷 Modifier la photo**")
    photo_source = st.radio(
        "Source", ["📸 Prendre une photo", "🔗 URL existante"],
        horizontal=True, key="photo_src_edit"
    )
    new_photo = row.get("Photo_URL", "")
    if photo_source == "📸 Prendre une photo":
        img = st.camera_input("Prenez une photo", key="cam_edit")
        if img:
            with st.spinner("Upload en cours..."):
                new_photo = upload_photo_to_drive(
                    img.getvalue(),
                    f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )
            if new_photo:
                st.success("✅ Photo uploadée !")
                st.image(img, width=200)
    else:
        new_photo = st.text_input("URL Photo", value=row.get("Photo_URL", ""))

    if save_btn:
        with st.spinner("Mise à jour…"):
            ok = update_materiel(mat_id, {
                "Nom":         new_nom,
                "Catégorie":   new_cat,
                "État":        new_etat,
                "Photo_URL":   new_photo,
                "Valeur_EUR":  new_val,
                "Description": new_desc,
                "Notes":       new_notes,
            })
        if ok:
            st.success("✅ Matériel mis à jour.")
            st.cache_data.clear()
        else:
            st.error("❌ Erreur lors de la mise à jour.")
