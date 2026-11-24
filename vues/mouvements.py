import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.auth import require_login, get_therapeute
require_login()
from utils.gsheets import (
    normalize, add_mouvement, update_materiel,
    TYPES_MOUVEMENT, STATUS_COLORS, ETATS,
)
from utils.ui import (ICONS, load_mat, load_mv, load_pers, person_form, person_save,
                      nom_affiche, derniere_personne)

st.title("🔄 Mouvements")

TRANSITIONS = {
    "Disponible":    ["Prêt sortant", "Location", "Vente", "Don sortant",
                      "Mis en réparation", "Hors service"],
    "En prêt":       ["Retour", "Vente", "Don sortant", "Mis en réparation",
                      "Location", "Hors service"],
    "En location":   ["Retour", "Vente", "Don sortant", "Mis en réparation",
                      "Prêt sortant", "Hors service"],
    "En réparation": ["Retour de réparation", "Prêt sortant", "Location",
                      "Vente", "Don sortant", "Hors service"],
    "Vendu":         TYPES_MOUVEMENT,
    "Donné":         TYPES_MOUVEMENT,
    "Hors service":  TYPES_MOUVEMENT,
}
DEPUIS_REPARATION = ["Retour de réparation", "Prêt sortant", "Location", "Vente", "Don sortant"]


# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 1 — Enregistrer un mouvement
# ══════════════════════════════════════════════════════════════════════════════
def choisir_materiel(df_mat):
    """Étape 1 : choisir l'article (fiche, scan QR ou tableau). Retourne l'ID ou None."""
    # Arrivée depuis la fiche matériel
    if st.session_state.get("mouvement_mat_id"):
        st.session_state["mouvement_mat_id_actif"] = st.session_state.pop("mouvement_mat_id")

    actif = st.session_state.get("mouvement_mat_id_actif", "")
    if actif and actif in df_mat["ID"].values:
        nom = df_mat[df_mat["ID"] == actif].iloc[0]["Nom"]
        st.info(f"📦 Article sélectionné : **{nom}**")
        if st.button("🔄 Changer d'article", key="mv_change"):
            del st.session_state["mouvement_mat_id_actif"]
            st.rerun()
        return actif

    st.subheader("1️⃣ Sélectionner le matériel")

    # Scan QR (caméra activée seulement à la demande)
    if st.toggle("📷 Scanner un QR code", key="mv_scan_toggle"):
        try:
            from streamlit_qrcode_scanner import qrcode_scanner
        except ImportError:
            st.error("La librairie de scan QR n'est pas installée.")
        else:
            qr = qrcode_scanner(key="qr_scanner")
            if qr:
                raw = qr.strip()
                scanned = raw.replace("ERGO-STOCK:", "").strip() if raw.startswith("ERGO-STOCK:") \
                    else raw.split("mat_id=")[-1].strip()
                if scanned in df_mat["ID"].values:
                    st.session_state["mouvement_mat_id_actif"] = scanned
                    st.rerun()
                else:
                    st.error(f"❌ Matériel non trouvé pour le code : `{scanned}`")
            else:
                st.caption("Pointez la caméra vers le QR code collé sur le matériel.")

    with st.expander("🔍 Filtres", expanded=True):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            search = st.text_input("Recherche (nom, ID…)", "", key="mv_search")
        with fc2:
            statuts = ["Tous"] + sorted(df_mat["Statut"].dropna().unique().tolist())
            f_statut = st.selectbox("Statut", statuts, key="mv_f_statut")
        with fc3:
            cats = ["Toutes"] + sorted(df_mat["Catégorie"].dropna().unique().tolist())
            f_cat = st.selectbox("Catégorie", cats, key="mv_f_cat")

    filtered = df_mat.copy()
    if search:
        q = normalize(search)
        filtered = filtered[filtered["Nom"].apply(lambda x: q in normalize(x)) |
                            filtered["ID"].apply(lambda x: q in normalize(x))]
    if f_statut != "Tous":
        filtered = filtered[filtered["Statut"] == f_statut]
    if f_cat != "Toutes":
        filtered = filtered[filtered["Catégorie"] == f_cat]

    st.caption(f"**{len(filtered)}** article(s)")
    display_df = filtered[["ID", "Nom", "Catégorie", "État", "Statut"]].copy()
    display_df["Statut"] = display_df["Statut"].apply(
        lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s}")
    selected = st.dataframe(
        display_df, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", height=250,
    )
    if not selected or not selected["selection"]["rows"]:
        st.info("👆 Cliquez sur un article dans le tableau pour continuer.")
        return None
    return filtered.iloc[selected["selection"]["rows"][0]]["ID"]


def enregistrer():
    df_mat = load_mat()
    df_p = load_pers()
    df_mv = load_mv()

    if df_mat.empty:
        st.warning("Aucun matériel enregistré.")
        return

    mat_id = choisir_materiel(df_mat)
    if not mat_id:
        return

    row = df_mat[df_mat["ID"] == mat_id].iloc[0]
    k = f"mv_{mat_id}"

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Nom", row["Nom"])
    c2.metric("Statut", f"{STATUS_COLORS.get(row['Statut'], '⚪')} {row['Statut']}")
    c3.metric("État actuel", row["État"])
    if row.get("Photo_URL", ""):
        with st.expander("📷 Photo"):
            st.image(row["Photo_URL"], width=200)

    st.divider()
    st.subheader("2️⃣ Type de mouvement")
    statut_actuel = row["Statut"]
    types_possibles = list(TRANSITIONS.get(statut_actuel, TYPES_MOUVEMENT))
    # Matériel emprunté : possibilité de le rendre au prêteur
    emprunte = row.get("Mode_Acquisition") == "Prêt entrant" or (
        not df_mv.empty and not df_mv[(df_mv["ID_Matériel"] == mat_id) &
                                      (df_mv["Type_Mouvement"] == "Prêt entrant")].empty)
    if emprunte and statut_actuel in ["Disponible", "En réparation", "Hors service"]:
        types_possibles.insert(types_possibles.index("Hors service") if "Hors service" in types_possibles
                               else len(types_possibles), "Rendu au prêteur")
    if "Rendu au prêteur" in types_possibles and not emprunte:
        types_possibles.remove("Rendu au prêteur")
    type_mv = st.selectbox("Type de mouvement", types_possibles, key=f"{k}_type")
    date_mv = st.date_input("Date du mouvement", value=date.today(), key=f"{k}_date")

    date_retour = None
    if type_mv in ["Prêt sortant", "Location"]:
        date_retour = st.date_input("📅 Date de retour prévue", value=None, key=f"{k}_retour")

    new_etat = None
    if type_mv in ["Retour", "Retour de réparation"] or (
            statut_actuel == "En réparation" and type_mv in DEPUIS_REPARATION):
        st.divider()
        st.markdown("**📋 État du matériel**")
        idx = ETATS.index(row["État"]) if row.get("État") in ETATS else 0
        new_etat = st.selectbox("État constaté", ETATS, index=idx, key=f"{k}_etat",
                                help="Modifiez si l'état du matériel a changé")
        if new_etat != row["État"]:
            st.warning(f"⚠️ L'état passera de **{row['État']}** → **{new_etat}**")
        else:
            st.success(f"✅ État inchangé : **{new_etat}**")

    st.divider()
    need_person = type_mv not in ["Hors service", "Retour de réparation"]
    is_retour = type_mv == "Retour"
    p_res = {"mode": "none", "nom": "", "contact": "", "new": None, "error": None}

    if need_person:
        st.subheader("3️⃣ Personne concernée")
        dernier_nom = dernier_contact = ""
        if not df_mv.empty:
            sortants = df_mv[(df_mv["ID_Matériel"] == mat_id) &
                             (df_mv["Type_Mouvement"].isin(["Prêt sortant", "Location"]))
                             ].sort_values("Date", ascending=False)
            if not sortants.empty:
                dernier_nom = sortants.iloc[0].get("Personne", "")
                dernier_contact = sortants.iloc[0].get("Contact", "")

        preteur = ""
        if type_mv == "Rendu au prêteur" and not df_mv.empty:
            ent = df_mv[(df_mv["ID_Matériel"] == mat_id) &
                        (df_mv["Type_Mouvement"] == "Prêt entrant") &
                        (df_mv["Personne"] != "")].sort_values("Date", ascending=False)
            if not ent.empty:
                preteur = ent.iloc[0]["Personne"].replace(" (Pro)", "")

        if is_retour and dernier_nom:
            st.info(f"👤 **{dernier_nom}**" + (f" · 📞 {dernier_contact}" if dernier_contact else ""))
            p_res = {"mode": "existing", "nom": dernier_nom, "contact": dernier_contact,
                     "new": None, "error": None}
        else:
            default = preteur or (dernier_nom if statut_actuel in ["En prêt", "En location"] else "")
            p_res = person_form(df_p, f"{k}_pers_{type_mv}", default_name=default,
                                titre="Sélectionner une personne")

    st.divider()
    notes_mv = st.text_area("💬 Notes / Observations", "", key=f"{k}_notes")

    if st.button("💾 Enregistrer le mouvement", type="primary",
                 use_container_width=True, key=f"{k}_save"):
        if need_person and p_res["error"]:
            st.error(p_res["error"])
            return
        with st.spinner("Enregistrement…"):
            p_nom, p_contact = person_save(p_res) if need_person else ("", "")
            add_mouvement({
                "ID_Matériel": mat_id, "Nom_Matériel": row["Nom"],
                "Date": str(date_mv), "Type_Mouvement": type_mv,
                "Personne": p_nom, "Contact": p_contact,
                "Date_Retour_Prévu": str(date_retour) if date_retour else "",
                "Date_Retour_Effectif": str(date_mv) if is_retour else "",
                "Notes": notes_mv, "Thérapeute": get_therapeute(),
            })
            if new_etat and new_etat != row["État"]:
                update_materiel(mat_id, {"État": new_etat})

        st.session_state.pop("mouvement_mat_id_actif", None)
        st.success(
            f"✅ Mouvement **{type_mv}** enregistré pour **{row['Nom']}**"
            + (f" — {p_nom}" if p_nom else "")
            + (f" — État mis à jour : **{new_etat}**" if new_etat and new_etat != row["État"] else ""))
        st.cache_data.clear()


# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 2 — Historique
# ══════════════════════════════════════════════════════════════════════════════
def historique():
    df_mv = load_mv()
    if df_mv.empty:
        st.info("Aucun mouvement enregistré pour le moment.")
        return

    with st.expander("🔍 Filtres", expanded=True):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        with fc1:
            search = st.text_input("Recherche (nom, personne…)", "", key="h_search")
        with fc2:
            f_type = st.selectbox("Type de mouvement", ["Tous"] + TYPES_MOUVEMENT, key="h_type")
        with fc3:
            f_ther = st.text_input("Thérapeute", "", key="h_ther")
        with fc4:
            d_debut = st.date_input("Date de début", value=date.today() - timedelta(days=90), key="h_debut")
        with fc5:
            d_fin = st.date_input("Date de fin", value=date.today(), key="h_fin")

    filtered = df_mv.copy()
    filtered["Date_dt"] = pd.to_datetime(filtered["Date"], errors="coerce")
    filtered = filtered[(filtered["Date_dt"].dt.date >= d_debut) &
                        (filtered["Date_dt"].dt.date <= d_fin)]

    if search:
        q = normalize(search)
        filtered = filtered[
            filtered["Nom_Matériel"].apply(lambda x: q in normalize(x)) |
            filtered["Personne"].apply(lambda x: q in normalize(x)) |
            filtered["ID_Matériel"].apply(lambda x: q in normalize(x))]
    if f_ther.strip():
        q = normalize(f_ther.strip())
        filtered = filtered[filtered["Thérapeute"].apply(lambda x: q in normalize(x))]
    if f_type != "Tous":
        filtered = filtered[filtered["Type_Mouvement"] == f_type]

    if "Horodatage" in filtered.columns and filtered["Horodatage"].astype(bool).any():
        filtered["_sort"] = pd.to_datetime(filtered["Horodatage"], errors="coerce")
        filtered = filtered.sort_values("_sort", ascending=False).drop(columns=["_sort"])
    else:
        filtered = filtered.sort_values("Date", ascending=False)

    st.caption(f"**{len(filtered)}** mouvement(s) affiché(s)")

    display = filtered.copy()
    display["Type_Mouvement"] = display["Type_Mouvement"].apply(
        lambda t: f"{ICONS.get(t, '🔄')} {t}")
    cols_show = [c for c in ["Date", "Nom_Matériel", "Type_Mouvement", "Thérapeute", "Personne",
                             "Contact", "Date_Retour_Prévu", "Date_Retour_Effectif", "Notes"]
                 if c in display.columns]
    st.dataframe(
        display[cols_show].rename(columns={
            "Nom_Matériel": "Matériel", "Type_Mouvement": "Mouvement",
            "Date_Retour_Prévu": "Retour prévu", "Date_Retour_Effectif": "Retour effectif"}),
        use_container_width=True, hide_index=True)

    if not filtered.empty:
        noms = {r["ID_Matériel"]: r["Nom_Matériel"]
                for _, r in filtered.drop_duplicates(subset="ID_Matériel").iterrows()
                if r["ID_Matériel"]}
        options = {f"[{i}] {n}": i for i, n in noms.items()}
        if options:
            st.markdown("**🔍 Voir la fiche d'un article :**")
            c1, c2 = st.columns([3, 1])
            with c1:
                choix = st.selectbox("Sélectionner un article", list(options.keys()),
                                     label_visibility="collapsed", key="h_fiche_sel")
            with c2:
                if st.button("🔍 Voir la fiche", type="primary", use_container_width=True, key="h_fiche_btn"):
                    st.session_state["fiche_mat_id"] = options[choix]
                    st.switch_page("vues/materiel.py")

    csv = filtered.drop(columns=["Date_dt"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exporter l'historique (CSV)", data=csv,
                       file_name="historique_ergostock.csv", mime="text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# ONGLET 3 — Mouvement groupé
# ══════════════════════════════════════════════════════════════════════════════
def groupe():
    st.caption("Applique le même mouvement à plusieurs articles d'un coup "
               "(ex. rendre à Buma tout ce qui vient de chez eux).")
    df_mat = load_mat()
    df_p = load_pers()
    df_mv = load_mv()
    if df_mat.empty:
        st.info("Aucun matériel enregistré.")
        return

    prov = derniere_personne(df_mv, ["Don reçu", "Prêt entrant", "Achat"])
    df = df_mat.copy()
    df["Provenance"] = df["ID"].apply(lambda i: prov.get(i, ""))

    fc1, fc2 = st.columns(2)
    with fc1:
        f_prov = st.text_input("Provenance (personne / société)", "", key="g_prov",
                               placeholder="ex : Buma")
    with fc2:
        statuts = sorted(df["Statut"].dropna().unique().tolist())
        f_statut = st.multiselect("Statut", statuts,
                                  default=["Disponible"] if "Disponible" in statuts else [],
                                  key="g_statut")
    if f_prov.strip():
        q = normalize(f_prov.strip())
        df = df[df["Provenance"].apply(lambda x: q in normalize(x))]
    if f_statut:
        df = df[df["Statut"].isin(f_statut)]

    st.caption(f"**{len(df)}** article(s) — cochez ceux à traiter")
    if df.empty:
        return
    aff = df[["ID", "Nom", "Catégorie", "Statut", "Provenance"]].copy()
    aff["Statut"] = aff["Statut"].apply(lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s}")
    sel = st.dataframe(aff, use_container_width=True, hide_index=True,
                       on_select="rerun", selection_mode="multi-row", key="g_table")
    rows = sel["selection"]["rows"] if sel else []
    if not rows:
        st.info("👆 Sélectionnez un ou plusieurs articles dans le tableau.")
        return
    choisis = df.iloc[rows]
    st.success(f"{len(choisis)} article(s) sélectionné(s) : " + ", ".join(choisis["Nom"].tolist()))

    st.divider()
    types = ["Rendu au prêteur", "Retour", "Vente", "Don sortant", "Prêt sortant",
             "Location", "Mis en réparation", "Hors service"]
    type_mv = st.selectbox("Mouvement à appliquer", types, key="g_type")
    date_mv = st.date_input("Date", value=date.today(), key="g_date")

    need_person = type_mv != "Hors service"
    p_res = {"mode": "none", "nom": "", "contact": "", "new": None, "error": None}
    if need_person:
        default = f_prov.strip() if type_mv == "Rendu au prêteur" else ""
        p_res = person_form(df_p, f"g_pers_{type_mv}", default_name=default,
                            titre="Personne concernée")
    notes = st.text_area("Notes", "", key="g_notes")

    if st.button(f"💾 Appliquer « {type_mv} » à {len(choisis)} article(s)",
                 type="primary", use_container_width=True, key="g_save"):
        if need_person and p_res["error"]:
            st.error(p_res["error"])
            return
        with st.spinner("Enregistrement…"):
            p_nom, p_contact = person_save(p_res) if need_person else ("", "")
            for _, r in choisis.iterrows():
                add_mouvement({
                    "ID_Matériel": r["ID"], "Nom_Matériel": r["Nom"],
                    "Date": str(date_mv), "Type_Mouvement": type_mv,
                    "Personne": p_nom, "Contact": p_contact,
                    "Date_Retour_Effectif": str(date_mv) if type_mv == "Retour" else "",
                    "Notes": notes, "Thérapeute": get_therapeute(),
                })
        st.success(f"✅ « {type_mv} » enregistré pour {len(choisis)} article(s).")
        st.cache_data.clear()


tab_enreg, tab_group, tab_hist = st.tabs(["🔄 Enregistrer", "📦 Mouvement groupé", "📜 Historique"])
with tab_enreg:
    enregistrer()
with tab_group:
    groupe()
with tab_hist:
    historique()
