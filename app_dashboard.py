import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
from utils.gsheets import init_sheets, get_materiel, get_mouvements, STATUS_COLORS

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

st.title("🏥 ErgoStock — Tableau de bord")
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
        st.switch_page("pages/7_Scanner_QR.py")

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

            retards   = df_retours[df_retours["Jours"] < 0]
            imminent  = df_retours[(df_retours["Jours"] >= 0) & (df_retours["Jours"] <= 7)]
            a_venir   = df_retours[df_retours["Jours"] > 7]

            if retards.empty and imminent.empty:
                st.success("✅ Aucun retour en retard ou imminent.")
            
            for _, row in retards.iterrows():
                j = abs(int(row["Jours"]))
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"🔴 **{row['Nom_Matériel']}**")
                        st.markdown(f"👤 {row['Personne']} {('· 📞 ' + row['Contact']) if row.get('Contact') else ''}")
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
                        st.markdown(f"👤 {row['Personne']} {('· 📞 ' + row['Contact']) if row.get('Contact') else ''}")
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

# ── Derniers mouvements ───────────────────────────────────────────────────────
st.subheader("⚡ Derniers mouvements")

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

if df_mv.empty:
    st.info("Aucun mouvement enregistré.")
else:
    recent = df_mv.sort_values("Date", ascending=False).head(10)
    for _, row in recent.iterrows():
        icon = ICONS.get(row.get("Type_Mouvement", ""), "🔄")
        type_mv = row.get("Type_Mouvement", "?")
        nom     = row.get("Nom_Matériel", "?")
        date_mv = row.get("Date", "?")
        personne = row.get("Personne", "")
        contact  = row.get("Contact", "")
        notes    = row.get("Notes", "")
        retour_prevu = row.get("Date_Retour_Prévu", "")
        retour_effectif = row.get("Date_Retour_Effectif", "")

        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"{icon} **{nom}** — {type_mv}")
                if personne:
                    line = f"👤 {personne}"
                    if contact:
                        line += f" · 📞 {contact}"
                    st.markdown(line)
                if retour_prevu:
                    st.markdown(f"📅 Retour prévu : {retour_prevu}")
                if retour_effectif:
                    st.markdown(f"✅ Retour effectif : {retour_effectif}")
                if notes:
                    st.markdown(f"💬 *{notes}*")
            with c2:
                st.markdown(f"**{date_mv}**")

st.divider()
st.caption("ErgoStock • Cabinet d'ergothérapie • Données stockées dans Google Sheets")
