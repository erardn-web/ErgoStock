import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import (
    get_materiel, get_mouvements, get_personnes, get_historique_materiel,
    update_materiel, add_personne,
    STATUS_COLORS, CATEGORIES, ETATS, upload_photo_to_drive,
    encode_disponibilites, decode_disponibilites, TYPES_PERSONNE
)
from utils.qrcode_utils import generate_qr

st.set_page_config(page_title="Fiche matériel – ErgoStock", page_icon="🔍", layout="wide")
st.title("🔍 Fiche matériel")
st.divider()

@st.cache_data(ttl=30)
def load():
    return get_materiel()

@st.cache_data(ttl=30)
def load_mv():
    return get_mouvements()

@st.cache_data(ttl=60)
def load_personnes():
    return get_personnes()

df_mat = load()

if df_mat.empty:
    st.info("Aucun matériel enregistré.")
    st.stop()

params       = st.query_params
preselect_id = st.session_state.pop("fiche_mat_id", "") or st.query_params.get("mat_id", "")

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

row   = df_mat[df_mat["ID"] == mat_id].iloc[0]
df_mv = load_mv()
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

    # Chez qui est l'objet
    statut_actuel = row.get("Statut", "")
    if statut_actuel in ["En prêt", "En location", "Donné"] and not df_mv.empty:
        derniers = df_mv[
            (df_mv["ID_Matériel"] == mat_id) &
            (df_mv["Type_Mouvement"].isin(["Prêt sortant", "Location", "Don sortant"]))
        ].sort_values("Date", ascending=False)
        if not derniers.empty:
            dernier  = derniers.iloc[0]
            personne = dernier.get("Personne", "")
            contact  = dernier.get("Contact", "")
            retour   = dernier.get("Date_Retour_Prévu", "")
            if personne:
                ligne = f"📍 Actuellement chez : **{personne}**"
                if contact:
                    ligne += f" · 📞 {contact}"
                st.markdown(ligne)
            if retour:
                st.markdown(f"📅 Retour prévu : **{retour}**")

    # Disponibilités
    dispos = decode_disponibilites(row.get("Disponibilités", ""))
    tags = []
    if dispos["tester"]: tags.append("🔬 À tester")
    if dispos["preter"]: tags.append("🤝 À prêter")
    if dispos["donner"]: tags.append("❤️ À donner")
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

    # Infos générales
    st.subheader("📋 Informations générales")
    e1, e2 = st.columns(2)
    with e1:
        new_nom  = st.text_input("Nom", value=row.get("Nom", ""), key=f"edit_nom_{mat_id}")
        new_cat  = st.selectbox("Catégorie", CATEGORIES,
                                index=CATEGORIES.index(row["Catégorie"])
                                if row.get("Catégorie") in CATEGORIES else 0,
                                key=f"edit_cat_{mat_id}")
        new_etat = st.selectbox("État", ETATS,
                                index=ETATS.index(row["État"])
                                if row.get("État") in ETATS else 0,
                                key=f"edit_etat_{mat_id}")
    with e2:
        new_val  = st.text_input("Valeur (€)", value=str(row.get("Valeur_EUR", "")), key=f"edit_val_{mat_id}")

    new_desc  = st.text_area("Description", value=row.get("Description", ""), key=f"edit_desc_{mat_id}")
    new_notes = st.text_area("Notes",       value=row.get("Notes", ""),        key=f"edit_notes_{mat_id}")

    # Disponibilités
    st.divider()
    st.subheader("🏷️ Disponibilités")
    dispos_act = decode_disponibilites(row.get("Disponibilités", ""))
    dc1, dc2, dc3, dc4 = st.columns(4)
    with dc1:
        dispo_tester = st.checkbox("🔬 À tester", value=dispos_act["tester"], key=f"tester_{mat_id}")
    with dc2:
        dispo_preter = st.checkbox("🤝 À prêter", value=dispos_act["preter"], key=f"preter_{mat_id}")
    with dc3:
        dispo_donner = st.checkbox("❤️ À donner", value=dispos_act["donner"], key=f"donner_{mat_id}")
    with dc4:
        dispo_vendre = st.checkbox("💶 À vendre", value=dispos_act["vendre"], key=f"vendre_{mat_id}")

    # Provenance
    st.divider()
    st.subheader("👤 Provenance")
    df_p = load_personnes()

    # Trouver la provenance actuelle depuis l'historique
    provenance_actuelle = ""
    if not df_mv.empty:
        entrants = df_mv[
            (df_mv["ID_Matériel"] == mat_id) &
            (df_mv["Type_Mouvement"].isin(["Don reçu", "Prêt entrant", "Achat"]))
        ].sort_values("Date", ascending=False)
        if not entrants.empty:
            provenance_actuelle = entrants.iloc[0].get("Personne", "")

    if provenance_actuelle:
        st.info(f"📍 Provenance enregistrée : **{provenance_actuelle}**")

    personnes_liste = ["— Aucune / Non renseignée —", "— Nouvelle personne —"]
    if not df_p.empty:
        for _, r in df_p.iterrows():
            if r.get("Type") == "Professionnel":
                label = f"{r['Nom']} (Pro) [{r['ID']}]"
            else:
                label = f"{r['Prénom']} {r['Nom']} ({r['Téléphone']}) [{r['ID']}]"
            personnes_liste.append(label)

    prov_sel = st.selectbox("Modifier la provenance", personnes_liste, key=f"edit_prov_sel_{mat_id}")

    new_p_nom = new_p_prenom = new_p_tel = new_p_email = ""
    new_p_type = "Patient"

    if prov_sel == "— Nouvelle personne —":
        new_p_type = st.selectbox("Type *", TYPES_PERSONNE, key=f"edit_prov_type_{mat_id}")
        if new_p_type == "Professionnel":
            new_p_nom   = st.text_input("Nom de la société *", key=f"edit_prov_nom_{mat_id}")
            new_p_tel   = st.text_input("Téléphone", key=f"edit_prov_tel_{mat_id}")
            new_p_email = st.text_input("Email", key=f"edit_prov_email_{mat_id}")
        else:
            pp1, pp2 = st.columns(2)
            with pp1:
                new_p_nom    = st.text_input("Nom *",    key=f"edit_prov_nom_{mat_id}")
                new_p_tel    = st.text_input("Téléphone", key=f"edit_prov_tel_{mat_id}")
            with pp2:
                new_p_prenom = st.text_input("Prénom",   key=f"edit_prov_prenom_{mat_id}")
                new_p_email  = st.text_input("Email",    key=f"edit_prov_email_{mat_id}")

    # Photo
    st.divider()
    st.subheader("📷 Photo")
    photo_source = st.radio(
        "Source", ["⏭️ Garder l'actuelle", "📸 Prendre une photo", "🔗 URL existante"],
        horizontal=True, key=f"photo_src_edit_{mat_id}"
    )
    new_photo = row.get("Photo_URL", "")
    if photo_source == "📸 Prendre une photo":
        img = st.camera_input("Prenez une photo", key=f"cam_edit_{mat_id}")
        if img:
            with st.spinner("Upload en cours..."):
                new_photo = upload_photo_to_drive(
                    img.getvalue(),
                    f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )
            if new_photo:
                st.success("✅ Photo uploadée !")
                st.image(img, width=200)
    elif photo_source == "🔗 URL existante":
        new_photo = st.text_input("URL Photo", value=row.get("Photo_URL", ""), key=f"edit_photo_url_{mat_id}")

    # Bouton enregistrer en bas
    st.divider()
    if st.button("💾 Enregistrer les modifications", type="primary", use_container_width=True, key=f"btn_save_{mat_id}"):
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
                    dispo_tester, dispo_preter, dispo_donner, dispo_vendre
                ),
            })

            # Mise à jour provenance si nouvelle personne saisie
            if prov_sel == "— Nouvelle personne —" and new_p_nom.strip():
                add_personne({
                    "Nom":       new_p_nom.strip(),
                    "Prénom":    new_p_prenom.strip(),
                    "Téléphone": new_p_tel.strip(),
                    "Email":     new_p_email.strip(),
                    "Type":      new_p_type,
                })

        if ok:
            st.success("✅ Matériel mis à jour.")
            st.cache_data.clear()
        else:
            st.error("❌ Erreur lors de la mise à jour.")
