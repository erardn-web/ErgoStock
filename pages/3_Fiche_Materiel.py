import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    get_materiel, get_historique_materiel, update_materiel,
    STATUS_COLORS, CATEGORIES, ETATS, upload_photo_to_drive,
    encode_disponibilites, decode_disponibilites
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

params       = st.query_params
preselect_id = params.get("mat_id", "")

with st.expander("🔍 Rechercher un article", expanded=True):
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
        filtered["ID"].str.contains(search, case=False, na=False) |
        filtered["Description"].str.contains(search, case=False, na=False)
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

mat_id = None
if preselect_id and preselect_id in df_mat["ID"].values and not (
    selected and selected["selection"]["rows"]
):
    mat_id = preselect_id
elif selected and selected["selection"]["rows"]:
    idx    = selected["selection"]["rows"][0]
    mat_id = filtered.iloc[idx]["ID"]
    st.query_params["mat_id"] = mat_id

if not mat_id:
    st.info("👆 Cliquez sur un article pour voir sa fiche.")
    st.stop()

row = df_mat[df_mat["ID"] == mat_id].iloc[0]
st.divider()

# ── Fiche ──────────────────────────────────────────────────────────────────────
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

    # Affichage disponibilités
    dispos = decode_disponibilites(row.get("Disponibilités", ""))
    tags = []
    if dispos["tester"]: tags.append("🔬 À tester")
    if dispos["preter"]: tags.append("🤝 À prêter")
    if dispos["vendre"]: tags.append("💶 À vendre")
    if tags:
        st.markdown("**Disponibilités :** " + "  ".join([f"**{t}**" for t in tags]))

with col_qr:
    st.subheader("🔲 QR Code")
    qr_bytes = generate_qr(f"ERGO-STOCK:{mat_id}")
    st.image(qr_bytes, width=200)
    st.download_button(
        "⬇️ Télécharger le QR Code",
        data=qr_bytes,
        file_name=f"qr_{mat_id}.png",
        mime="image/png",
    )
    st.caption("Format 23×23mm — compatible Brother DK-11221")

# ── Bouton mouvement ───────────────────────────────────────────────────────────
st.divider()
if st.button("🔄 Enregistrer un mouvement pour cet article", type="primary", use_container_width=True):
    st.session_state["mouvement_mat_id"] = mat_id
    st.switch_page("pages/2_Mouvement.py")

st.divider()

# ── Historique ─────────────────────────────────────────────────────────────────
st.subheader("📜 Historique de cet article")
hist = get_historique_materiel(mat_id)
if hist.empty:
    st.info("Aucun mouvement enregistré pour cet article.")
else:
    ICONS = {
        "Prêt sortant": "📤", "Retour": "📥", "Achat": "🛒",
        "Don reçu": "🎁", "Prêt entrant": "📦", "Location": "🔵",
        "Vente": "💶", "Don sortant": "❤️", "Mis en réparation": "🔧",
        "Retour de réparation": "✅", "Hors service": "❌",
    }
    hist["Type_Mouvement"] = hist["Type_Mouvement"].apply(
        lambda t: f"{ICONS.get(t, '🔄')} {t}"
    )
    cols = [c for c in ["Date", "Type_Mouvement", "Personne", "Contact",
                         "Date_Retour_Prévu", "Date_Retour_Effectif", "Notes"]
            if c in hist.columns]
    st.dataframe(hist[cols], use_container_width=True, hide_index=True)

st.divider()

# ── Édition ────────────────────────────────────────────────────────────────────
with st.expander("✏️ Modifier les informations"):

    # Disponibilités HORS formulaire
    dispos_act = decode_disponibilites(row.get("Disponibilités", ""))
    st.markdown("**🏷️ Disponibilités**")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        dispo_tester = st.checkbox("🔬 À tester", value=dispos_act["tester"], key=f"tester_{mat_id}")
    with dc2:
        dispo_preter = st.checkbox("🤝 À prêter", value=dispos_act["preter"], key=f"preter_{mat_id}")
    with dc3:
        dispo_vendre = st.checkbox("💶 À vendre", value=dispos_act["vendre"], key=f"vendre_{mat_id}")

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
            new_val = st.text_input("Valeur (€)", value=str(row.get("Valeur_EUR", "")))

        new_desc  = st.text_area("Description", value=row.get("Description", ""))
        new_notes = st.text_area("Notes",       value=row.get("Notes", ""))
        save_btn  = st.form_submit_button("💾 Enregistrer les modifications", type="primary")

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
                "Nom":            new_nom,
                "Catégorie":      new_cat,
                "État":           new_etat,
                "Photo_URL":      new_photo,
                "Valeur_EUR":     new_val,
                "Description":    new_desc,
                "Notes":          new_notes,
                "Disponibilités": encode_disponibilites(
                    st.session_state.get(f"tester_{mat_id}", False),
                    st.session_state.get(f"preter_{mat_id}", False),
                    st.session_state.get(f"vendre_{mat_id}", False),
                ),
            })
        if ok:
            st.success("✅ Matériel mis à jour.")
            st.cache_data.clear()
        else:
            st.error("❌ Erreur lors de la mise à jour.")
