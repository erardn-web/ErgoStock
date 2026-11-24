import streamlit as st
import pandas as pd
from datetime import date, datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.auth import require_login, get_therapeute
require_login()
from utils.gsheets import (
    normalize, add_materiel, update_materiel, add_mouvement,
    get_historique_materiel, upload_photo_to_drive,
    STATUS_COLORS, CATEGORIES, ETATS,
    encode_disponibilites, decode_disponibilites,
)
from utils.qrcode_utils import generate_qr
from utils.ui import (
    ICONS, load_mat, load_mv, load_pers, person_form, person_save, AUCUNE,
)

STATUTS_CHEZ_PERSONNE = ["En prêt", "En location", "Donné", "Vendu"]
TYPES_SORTANTS = ["Prêt sortant", "Location", "Don sortant", "Vente"]
TYPES_ENTRANTS = ["Don reçu", "Prêt entrant", "Achat"]

st.title("📦 Matériel")


def derniere_personne(df_mv, types):
    """Dernière personne liée à chaque matériel pour ces types de mouvement."""
    if df_mv.empty:
        return {}
    d = df_mv[df_mv["Type_Mouvement"].isin(types) & (df_mv["Personne"] != "")].copy()
    if d.empty:
        return {}
    d["_k"] = pd.to_datetime(d["Horodatage"], errors="coerce") if "Horodatage" in d else pd.NaT
    d["_d"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.sort_values(["_k", "_d"], na_position="first")
    return d.groupby("ID_Matériel")["Personne"].last().to_dict()


def photo_widget(prefix, actuelle="", garder=False):
    """Choix de photo (caméra / URL). Retourne l'URL à enregistrer."""
    options = ["⏭️ Garder l'actuelle" if garder else "⏭️ Pas de photo",
               "📸 Prendre une photo", "🔗 URL existante"]
    source = st.radio("Source", options, horizontal=True, key=f"{prefix}_src")
    url = actuelle
    if source == "📸 Prendre une photo":
        img = st.camera_input("Prenez une photo", key=f"{prefix}_cam")
        if img:
            with st.spinner("Upload en cours..."):
                url = upload_photo_to_drive(
                    img.getvalue(),
                    f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )
            if url:
                st.success("✅ Photo uploadée !")
                st.image(img, width=200)
    elif source == "🔗 URL existante":
        url = st.text_input("URL de la photo", value=actuelle, key=f"{prefix}_url")
    return url


def dispos_widget(prefix, valeurs=None):
    v = valeurs or {"tester": False, "preter": False, "donner": False, "vendre": False}
    c1, c2, c3, c4 = st.columns(4)
    with c1: t = st.checkbox("🔬 À tester", value=v["tester"], key=f"{prefix}_tester")
    with c2: p = st.checkbox("🤝 À prêter", value=v["preter"], key=f"{prefix}_preter")
    with c3: d = st.checkbox("❤️ À donner", value=v["donner"], key=f"{prefix}_donner")
    with c4: s = st.checkbox("💶 À vendre", value=v["vendre"], key=f"{prefix}_vendre")
    return encode_disponibilites(t, p, d, s)


# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 1 — Liste & fiche
# ══════════════════════════════════════════════════════════════════════════════
def liste_et_fiche():
    df_mat = load_mat()
    if df_mat.empty:
        st.info("Aucun matériel enregistré. Utilisez l'onglet « Nouveau matériel ».")
        return

    df_mv = load_mv()
    chez = derniere_personne(df_mv, TYPES_SORTANTS)
    prov = derniere_personne(df_mv, TYPES_ENTRANTS)
    df_mat = df_mat.copy()
    df_mat["Chez"] = df_mat.apply(
        lambda r: chez.get(r["ID"], "") if r.get("Statut") in STATUTS_CHEZ_PERSONNE else "",
        axis=1)
    df_mat["Provenance"] = df_mat["ID"].apply(lambda i: prov.get(i, ""))

    # Arrivée depuis une autre page (Historique, Accueil…)
    if st.session_state.get("fiche_mat_id"):
        st.session_state["fiche_actif"] = st.session_state.pop("fiche_mat_id")

    with st.expander("🔍 Rechercher", expanded=True):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        with fc1:
            search = st.text_input("Recherche (nom, ID…)", "", key="m_search")
        with fc2:
            search_pers = st.text_input("Personne (détenteur ou provenance)", "", key="m_pers")
        with fc3:
            statuts = ["Tous"] + sorted(df_mat["Statut"].dropna().unique().tolist())
            f_statut = st.selectbox("Statut", statuts, key="m_statut")
        with fc4:
            cats = ["Toutes"] + sorted(df_mat["Catégorie"].dropna().unique().tolist())
            f_cat = st.selectbox("Catégorie", cats, key="m_cat")
        with fc5:
            etats = ["Tous"] + sorted(df_mat["État"].dropna().unique().tolist())
            f_etat = st.selectbox("État", etats, key="m_etat")

    filtered = df_mat.copy()
    if search_pers.strip():
        q = normalize(search_pers.strip())
        filtered = filtered[(filtered["Chez"] + " " + filtered["Provenance"])
                            .apply(lambda x: q in normalize(x))]
    if search:
        q = normalize(search)
        filtered = filtered[
            filtered["Nom"].apply(lambda x: q in normalize(x)) |
            filtered["ID"].apply(lambda x: q in normalize(x)) |
            filtered["Description"].apply(lambda x: q in normalize(x))
        ]
    if f_statut != "Tous":
        filtered = filtered[filtered["Statut"] == f_statut]
    if f_cat != "Toutes":
        filtered = filtered[filtered["Catégorie"] == f_cat]
    if f_etat != "Tous":
        filtered = filtered[filtered["État"] == f_etat]

    hc1, hc2 = st.columns([3, 1])
    with hc1:
        st.caption(f"**{len(filtered)}** article(s)")
    with hc2:
        mode = st.radio("Affichage", ["🗂️ Tableau", "🖼️ Galerie"], horizontal=True,
                        key="m_mode", label_visibility="collapsed")

    if mode == "🗂️ Tableau":
        display_df = filtered[["ID", "Nom", "Catégorie", "État", "Statut", "Chez", "Provenance"]].copy()
        display_df["Statut"] = display_df["Statut"].apply(
            lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s}")
        selected = st.dataframe(
            display_df, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", height=200,
        )
        rows = selected["selection"]["rows"] if selected else []
        if rows:
            sid = filtered.iloc[rows[0]]["ID"]
            if sid != st.session_state.get("_fiche_last_sel"):
                st.session_state["_fiche_last_sel"] = sid
                st.session_state["fiche_actif"] = sid
        else:
            st.session_state["_fiche_last_sel"] = None
    else:
        items = filtered.to_dict("records")
        for i in range(0, len(items), 3):
            cols = st.columns(3)
            for j, item in enumerate(items[i:i + 3]):
                with cols[j]:
                    st.markdown(f"**{STATUS_COLORS.get(item.get('Statut', ''), '⚪')} {item.get('Nom', '?')}**")
                    photo = item.get("Photo_URL", "")
                    if photo and photo.startswith("http"):
                        st.image(photo, use_container_width=True)
                    st.caption(f"{item.get('Catégorie', '')} · {item.get('État', '')} · {item.get('Statut', '')}")
                    if st.button("🔍 Voir la fiche", key=f"gal_{item['ID']}"):
                        st.session_state["fiche_actif"] = item["ID"]

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exporter la sélection (CSV)", data=csv,
                       file_name="inventaire_ergostock.csv", mime="text/csv")

    mat_id = st.session_state.get("fiche_actif")
    if not mat_id or mat_id not in df_mat["ID"].values:
        st.info("👆 Cliquez sur un article pour voir sa fiche.")
        return

    fiche(df_mat[df_mat["ID"] == mat_id].iloc[0], mat_id, df_mv)


def fiche(row, mat_id, df_mv):
    st.divider()
    top1, top2 = st.columns([5, 1])
    with top2:
        if st.button("✖ Fermer la fiche", key="fiche_close", use_container_width=True):
            st.session_state.pop("fiche_actif", None)
            st.rerun()

    col_photo, col_info, col_qr = st.columns([2, 3, 2])
    with col_photo:
        photo = row.get("Photo_URL", "")
        if photo and photo.startswith("http"):
            st.image(photo, use_container_width=True)
        else:
            st.markdown(
                "<div style='background:#f0f2f6;border-radius:8px;padding:40px;"
                "text-align:center;color:#999;'>Pas de photo</div>",
                unsafe_allow_html=True)

    with col_info:
        st.subheader(f"{STATUS_COLORS.get(row['Statut'], '⚪')} {row['Nom']}")
        st.markdown(f"**ID :** `{row['ID']}`")
        for k, v in {
            "Catégorie": row.get("Catégorie", ""),
            "Description": row.get("Description", ""),
            "État": row.get("État", ""),
            "Statut": row.get("Statut", ""),
            "Date d'acquisition": row.get("Date_Acquisition", ""),
            "Mode d'acquisition": row.get("Mode_Acquisition", ""),
            "Valeur (€)": row.get("Valeur_EUR", ""),
            "Notes": row.get("Notes", ""),
        }.items():
            if v:
                st.markdown(f"**{k} :** {v}")

        if row.get("Statut") in ["En prêt", "En location", "Donné"] and not df_mv.empty:
            derniers = df_mv[
                (df_mv["ID_Matériel"] == mat_id) &
                (df_mv["Type_Mouvement"].isin(["Prêt sortant", "Location", "Don sortant"]))
            ].sort_values("Date", ascending=False)
            if not derniers.empty:
                d = derniers.iloc[0]
                if d.get("Personne"):
                    ligne = f"📍 Actuellement chez : **{d['Personne']}**"
                    if d.get("Contact"):
                        ligne += f" · 📞 {d['Contact']}"
                    st.markdown(ligne)
                if d.get("Date_Retour_Prévu"):
                    st.markdown(f"📅 Retour prévu : **{d['Date_Retour_Prévu']}**")

        dispos = decode_disponibilites(row.get("Disponibilités", ""))
        tags = [t for k, t in [("tester", "🔬 À tester"), ("preter", "🤝 À prêter"),
                               ("donner", "❤️ À donner"), ("vendre", "💶 À vendre")] if dispos[k]]
        if tags:
            st.markdown("**Disponibilités :** " + "  ".join(f"**{t}**" for t in tags))

    with col_qr:
        qr_bytes = generate_qr(f"ERGO-STOCK:{mat_id}")
        st.image(qr_bytes, width=180)
        st.download_button("⬇️ QR Code", data=qr_bytes,
                           file_name=f"qr_{mat_id}.png", mime="image/png")
        st.caption("23×23 mm — Brother DK-11221")

    if st.button("🔄 Enregistrer un mouvement pour cet article", type="primary",
                 use_container_width=True, key="fiche_mouv"):
        st.session_state["mouvement_mat_id"] = mat_id
        st.switch_page("vues/mouvements.py")

    st.markdown("##### 📜 Historique de cet article")
    hist = get_historique_materiel(mat_id)
    if hist.empty:
        st.info("Aucun mouvement enregistré pour cet article.")
    else:
        hist["Type_Mouvement"] = hist["Type_Mouvement"].apply(
            lambda t: f"{ICONS.get(t, '🔄')} {t}")
        cols = [c for c in ["Date", "Type_Mouvement", "Thérapeute", "Personne", "Contact",
                            "Date_Retour_Prévu", "Date_Retour_Effectif", "Notes"]
                if c in hist.columns]
        st.dataframe(hist[cols], use_container_width=True, hide_index=True)

    with st.expander("✏️ Modifier les informations"):
        edition(row, mat_id, df_mv)


def edition(row, mat_id, df_mv):
    k = f"edit_{mat_id}"
    st.subheader("📋 Informations générales")
    e1, e2 = st.columns(2)
    with e1:
        new_nom = st.text_input("Nom", value=row.get("Nom", ""), key=f"{k}_nom")
        new_cat = st.selectbox("Catégorie", CATEGORIES,
                               index=CATEGORIES.index(row["Catégorie"])
                               if row.get("Catégorie") in CATEGORIES else 0, key=f"{k}_cat")
        new_etat = st.selectbox("État", ETATS,
                                index=ETATS.index(row["État"])
                                if row.get("État") in ETATS else 0, key=f"{k}_etat")
    with e2:
        new_val = st.text_input("Valeur (€)", value=str(row.get("Valeur_EUR", "")), key=f"{k}_val")
    new_desc = st.text_area("Description", value=row.get("Description", ""), key=f"{k}_desc")
    new_notes = st.text_area("Notes", value=row.get("Notes", ""), key=f"{k}_notes")

    st.divider()
    st.subheader("🏷️ Disponibilités")
    dispo_code = dispos_widget(f"{k}_dispo", decode_disponibilites(row.get("Disponibilités", "")))

    st.divider()
    st.subheader("👤 Provenance")
    if not df_mv.empty:
        entrants = df_mv[(df_mv["ID_Matériel"] == mat_id) &
                         (df_mv["Type_Mouvement"].isin(TYPES_ENTRANTS))
                         ].sort_values("Date", ascending=False)
        if not entrants.empty and entrants.iloc[0].get("Personne"):
            st.info(f"📍 Provenance enregistrée : **{entrants.iloc[0]['Personne']}**")
    prov = person_form(load_pers(), f"{k}_prov", allow_none=True, titre="Modifier la provenance")

    st.divider()
    st.subheader("📷 Photo")
    new_photo = photo_widget(f"{k}_photo", row.get("Photo_URL", ""), garder=True)

    st.divider()
    if st.button("💾 Enregistrer les modifications", type="primary",
                 use_container_width=True, key=f"{k}_save"):
        if prov["error"]:
            st.error(prov["error"])
            return
        with st.spinner("Mise à jour…"):
            ok = update_materiel(mat_id, {
                "Nom": new_nom, "Catégorie": new_cat, "État": new_etat,
                "Photo_URL": new_photo, "Valeur_EUR": new_val,
                "Description": new_desc, "Notes": new_notes,
                "Disponibilités": dispo_code,
            })
            person_save(prov)
        if ok:
            st.success("✅ Matériel mis à jour.")
            st.cache_data.clear()
        else:
            st.error("❌ Erreur lors de la mise à jour.")


# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 2 — Nouveau matériel
# ══════════════════════════════════════════════════════════════════════════════
def nouveau():
    df_p = load_pers()

    st.subheader("📋 Informations générales")
    c1, c2 = st.columns(2)
    with c1:
        nom = st.text_input("Nom du matériel *", placeholder="ex : Pince de préhension", key="new_nom")
        categorie = st.selectbox("Catégorie *", CATEGORIES, key="new_cat")
        etat = st.selectbox("État *", ETATS, key="new_etat")
    with c2:
        mode = st.selectbox("Mode d'acquisition *", ["Achat", "Don reçu", "Prêt entrant"], key="new_mode")
        date_acq = st.date_input("Date d'acquisition *", value=date.today(), key="new_date")
        valeur = st.number_input("Valeur (€)", min_value=0.0, step=0.5, value=0.0, key="new_val")
    description = st.text_area("Description", placeholder="Marque, référence, caractéristiques…", key="new_desc")
    notes = st.text_area("Notes internes", placeholder="Observations…", key="new_notes")

    st.divider()
    st.subheader("🏷️ Disponibilités")
    dispo_code = dispos_widget("new_dispo")

    st.divider()
    st.subheader("👤 Provenance")
    prov = person_form(df_p, "new_prov", allow_none=True, titre="Personne existante")

    st.divider()
    st.subheader("📷 Photo du matériel")
    photo_url = photo_widget("new_photo")

    st.divider()
    if st.button("💾 Enregistrer le matériel", type="primary",
                 use_container_width=True, key="new_save"):
        if not nom.strip():
            st.error("Le nom du matériel est obligatoire.")
            return
        if prov["error"]:
            st.error(prov["error"])
            return
        with st.spinner("Enregistrement en cours…"):
            mat_id = add_materiel({
                "Nom": nom.strip(), "Catégorie": categorie, "Description": description,
                "État": etat, "Photo_URL": photo_url.strip(),
                "Date_Acquisition": str(date_acq), "Mode_Acquisition": mode,
                "Valeur_EUR": valeur if valeur > 0 else "", "Notes": notes,
                "Disponibilités": dispo_code,
            })
            p_nom, p_contact = person_save(prov)
            if p_nom or mode in ["Don reçu", "Prêt entrant"]:
                add_mouvement({
                    "ID_Matériel": mat_id, "Nom_Matériel": nom.strip(),
                    "Date": str(date_acq), "Type_Mouvement": mode,
                    "Personne": p_nom, "Contact": p_contact,
                    "Notes": notes, "Thérapeute": get_therapeute(),
                })
        st.success(f"✅ Matériel **{nom}** ajouté avec l'ID **{mat_id}**")
        qr_bytes = generate_qr(f"ERGO-STOCK:{mat_id}")
        st.image(qr_bytes, caption=f"QR Code – {nom} ({mat_id})", width=250)
        st.download_button("⬇️ Télécharger le QR Code (PNG)", data=qr_bytes,
                           file_name=f"qr_{mat_id}.png", mime="image/png")
        st.info("💡 Imprimez ce QR code et collez-le sur le matériel.")
        st.cache_data.clear()


tab_liste, tab_new = st.tabs(["📋 Liste & fiche", "➕ Nouveau matériel"])
with tab_liste:
    liste_et_fiche()
with tab_new:
    nouveau()
