import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import init_sheets, get_materiel, get_mouvements, update_materiel, STATUS_COLORS
from utils.auth import require_login
require_login()


st.markdown("""
<style>
.qr-card {
    background: linear-gradient(135deg, #FF4B4B, #ff7676);
    border-radius: 14px;
    padding: 20px 28px;
    display: flex;
    align-items: center;
    gap: 18px;
    box-shadow: 0 4px 16px rgba(255,75,75,0.3);
    margin-bottom: 8px;
}
.qr-card span.icon { font-size: 2.5rem; }
.qr-card div { color: white; }
.qr-card div h3 { margin: 0; font-size: 1.2rem; }
.qr-card div p  { margin: 0; font-size: 0.85rem; opacity: 0.85; }
</style>
""", unsafe_allow_html=True)

if "sheets_ok" not in st.session_state:
    ok, msg = init_sheets()
    st.session_state["sheets_ok"] = ok
    st.session_state["sheets_msg"] = msg

if not st.session_state["sheets_ok"]:
    st.error(st.session_state["sheets_msg"])
    st.stop()

st.title("🏥 ErgoStock")
st.caption(f"Mis à jour le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
st.divider()

@st.cache_data(ttl=60)
def load_data():
    return get_materiel(), get_mouvements()

with st.spinner("Chargement des données…"):
    df_mat, df_mv = load_data()

# ── Bouton QR scanner ─────────────────────────────────────────────────────────
qr_col, _ = st.columns([1, 2])
with qr_col:
    st.markdown("""
    <div class="qr-card">
        <span class="icon">📷</span>
        <div>
            <h3>Scanner un QR Code</h3>
            <p>Identifier un article et enregistrer un mouvement</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("📷 Ouvrir le scanner", type="primary", use_container_width=True):
        st.session_state["mv_scan_toggle"] = True
        st.switch_page("vues/mouvements.py")

st.divider()

# ── Retours en retard ou proches ──────────────────────────────────────────────
st.subheader("⏰ Retours en retard ou à venir")

if not df_mv.empty and not df_mat.empty:
    today = datetime.now().date()
    ids_sortis = set(df_mat[df_mat["Statut"].isin(["En prêt", "En location"])]["ID"])

    df_retours = df_mv[
        df_mv["Type_Mouvement"].isin(["Prêt sortant", "Location"]) &
        df_mv["Date_Retour_Prévu"].notna() &
        (df_mv["Date_Retour_Prévu"] != "") &
        df_mv["ID_Matériel"].isin(ids_sortis)
    ].copy()

    if not df_retours.empty:
        try:
            df_retours["Date_Retour_Prévu"] = pd.to_datetime(
                df_retours["Date_Retour_Prévu"], errors="coerce"
            )
            df_retours = df_retours.dropna(subset=["Date_Retour_Prévu"])
            df_retours["Jours"] = df_retours["Date_Retour_Prévu"].dt.date.apply(
                lambda d: (d - today).days
            )
            df_retours = df_retours.sort_values("Jours")

            retards  = df_retours[df_retours["Jours"] < 0]
            imminent = df_retours[(df_retours["Jours"] >= 0) & (df_retours["Jours"] <= 7)]
            a_venir  = df_retours[df_retours["Jours"] > 7]

            if retards.empty and imminent.empty:
                st.success("✅ Aucun retour en retard ou imminent.")

            for _, row in retards.iterrows():
                j = abs(int(row["Jours"]))
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"🔴 **{row['Nom_Matériel']}**")
                        st.markdown(f"👤 {row['Personne']}" + (f" · 📞 {row['Contact']}" if row.get('Contact') else ""))
                        st.markdown(f"📅 Prévu le {row['Date_Retour_Prévu'].strftime('%d/%m/%Y')}")
                    with c2:
                        st.markdown(f"**En retard**")
                        st.markdown(f"**de {j} jour(s)**")

            for _, row in imminent.iterrows():
                j = int(row["Jours"])
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"🟠 **{row['Nom_Matériel']}**")
                        st.markdown(f"👤 {row['Personne']}" + (f" · 📞 {row['Contact']}" if row.get('Contact') else ""))
                        st.markdown(f"📅 Prévu le {row['Date_Retour_Prévu'].strftime('%d/%m/%Y')}")
                    with c2:
                        if j == 0:
                            st.markdown("**Aujourd'hui !**")
                        else:
                            st.markdown(f"**Dans {j} jour(s)**")

            if not a_venir.empty:
                with st.expander(f"📅 Retours à venir ({len(a_venir)} article(s))"):
                    for _, row in a_venir.iterrows():
                        j = int(row["Jours"])
                        st.markdown(
                            f"🟡 **{row['Nom_Matériel']}** — "
                            f"👤 {row['Personne']} — "
                            f"📅 {row['Date_Retour_Prévu'].strftime('%d/%m/%Y')} "
                            f"*(dans {j} jours)*"
                        )

        except Exception as e:
            st.info(f"Impossible de calculer les retards : {e}")
    else:
        st.info("Aucun prêt en cours avec date de retour renseignée.")
else:
    st.info("Aucun mouvement enregistré.")

st.divider()

# ── Objets vendus à traiter ───────────────────────────────────────────────────
def objets_vendus(df_mat, df_mv):
    vendus = df_mat[df_mat["Statut"] == "Vendu"].copy()
    if "Archivé" not in vendus.columns:
        vendus["Archivé"] = ""
    a_traiter = vendus[vendus["Archivé"] != "oui"].copy()
    archives  = vendus[vendus["Archivé"] == "oui"].copy()

    if not df_mv.empty:
        ventes = (
            df_mv[df_mv["Type_Mouvement"] == "Vente"]
            .sort_values("Date", ascending=False)
            .drop_duplicates(subset="ID_Matériel", keep="first")
            [["ID_Matériel", "Date", "Personne", "Contact", "Notes"]]
            .rename(columns={"Date": "Date_Vente", "Personne": "Acheteur",
                             "Contact": "Contact_Acheteur", "Notes": "Notes_Vente"})
        )
        a_traiter = a_traiter.merge(ventes, left_on="ID", right_on="ID_Matériel", how="left")
        archives  = archives.merge(ventes,  left_on="ID", right_on="ID_Matériel", how="left")

    st.subheader(f"💼 Objets vendus à traiter ({len(a_traiter)})")
    if a_traiter.empty:
        st.success("✅ Rien à traiter.")
    for _, row in a_traiter.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                st.markdown(f"**📦 {row['Nom']}**  \n`{row['ID']}` · {row.get('Catégorie', '')}")
                if row.get("Date_Vente"):
                    st.markdown(f"📅 Vendu le **{row['Date_Vente']}**")
                if row.get("Acheteur"):
                    ligne = f"👤 **{row['Acheteur']}**"
                    if row.get("Contact_Acheteur"):
                        ligne += f" · 📞 {row['Contact_Acheteur']}"
                    st.markdown(ligne)
                if row.get("Notes_Vente"):
                    st.markdown(f"💬 *{row['Notes_Vente']}*")
            with c2:
                action = st.multiselect(
                    "Action",
                    ["✅ Fournisseur informé", "✅ Remplacement commandé",
                     "✅ Aucune action requise", "✅ Autre action effectuée"],
                    key=f"action_{row['ID']}",
                    placeholder="Action(s) effectuée(s)…",
                    label_visibility="collapsed")
                note_action = st.text_input("Note", key=f"note_{row['ID']}",
                                            placeholder="Détail (optionnel)",
                                            label_visibility="collapsed")
            with c3:
                if st.button("📁 Archiver", key=f"archive_{row['ID']}", type="primary",
                             use_container_width=True, disabled=(len(action) == 0)):
                    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")
                    note_finale = f"{', '.join(action)} — {horodatage}"
                    if note_action.strip():
                        note_finale += f" — {note_action.strip()}"
                    nouvelle = f"{row.get('Notes', '')}\n[VENTE ARCHIVÉE] {note_finale}".strip()
                    update_materiel(row["ID"], {"Archivé": "oui", "Notes": nouvelle})
                    st.cache_data.clear()
                    st.rerun()

    with st.expander(f"📁 Objets archivés ({len(archives)})"):
        if archives.empty:
            st.info("Aucun objet archivé.")
        else:
            cols_show = [c for c in ["Nom", "Catégorie", "État", "Date_Vente", "Acheteur",
                                     "Valeur_EUR", "Notes"] if c in archives.columns]
            st.dataframe(archives[cols_show], use_container_width=True, hide_index=True)
            options = {f"{r['Nom']} [{r['ID']}]": r["ID"] for _, r in archives.iterrows()}
            c1, c2 = st.columns([3, 1])
            with c1:
                choix = st.selectbox("Désarchiver", list(options.keys()),
                                     label_visibility="collapsed", key="desarchive_sel")
            with c2:
                if st.button("↩️ Désarchiver", use_container_width=True, key="desarchive_btn"):
                    update_materiel(options[choix], {"Archivé": ""})
                    st.cache_data.clear()
                    st.rerun()


if not df_mat.empty:
    objets_vendus(df_mat, df_mv)

st.divider()
st.caption("ErgoStock • Cabinet d'ergothérapie • Données stockées dans Google Sheets")
