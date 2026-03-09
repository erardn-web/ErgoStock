import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
from utils.gsheets import init_sheets, get_materiel, get_mouvements, STATUS_COLORS

st.set_page_config(
    page_title="ErgoStock – Cabinet d'ergothérapie",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

total       = len(df_mat)
disponible  = len(df_mat[df_mat["Statut"] == "Disponible"])  if not df_mat.empty else 0
en_pret     = len(df_mat[df_mat["Statut"] == "En prêt"])     if not df_mat.empty else 0
en_location = len(df_mat[df_mat["Statut"] == "En location"]) if not df_mat.empty else 0
vendu       = len(df_mat[df_mat["Statut"] == "Vendu"])       if not df_mat.empty else 0
donne       = len(df_mat[df_mat["Statut"] == "Donné"])       if not df_mat.empty else 0
reparation  = len(df_mat[df_mat["Statut"] == "En réparation"]) if not df_mat.empty else 0

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("📦 Total matériel", total)
with col2:
    st.metric("🟢 Disponible", disponible)
with col3:
    st.metric("🟡 En prêt", en_pret)
with col4:
    st.metric("🔵 En location", en_location)
with col5:
    st.metric("🔴 Vendu / Donné", vendu + donne)
with col6:
    st.metric("🟠 En réparation", reparation)

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("📋 Matériel actuellement sorti")
    sorti = df_mat[df_mat["Statut"].isin(["En prêt", "En location"])] if not df_mat.empty else pd.DataFrame()

    if sorti.empty:
        st.info("Aucun matériel actuellement sorti.")
    else:
        if not df_mv.empty:
            last_mv = (df_mv
                .sort_values("Date", ascending=False)
                .drop_duplicates(subset="ID_Matériel", keep="first")
                [["ID_Matériel", "Personne", "Contact", "Date_Retour_Prévu"]]
            )
            sorti = sorti.merge(last_mv, left_on="ID", right_on="ID_Matériel", how="left")

        cols_show = ["Statut", "Nom", "Catégorie", "Personne", "Contact", "Date_Retour_Prévu"]
        cols_show = [c for c in cols_show if c in sorti.columns]
        st.dataframe(
            sorti[cols_show].rename(columns={
                "Statut": "État",
                "Date_Retour_Prévu": "Retour prévu"
            }),
            use_container_width=True,
            hide_index=True,
        )

with right:
    st.subheader("⚡ Derniers mouvements")
    if df_mv.empty:
        st.info("Aucun mouvement enregistré.")
    else:
        recent = df_mv.sort_values("Date", ascending=False).head(8)
        for _, row in recent.iterrows():
            icon = {
                "Prêt sortant":  "📤",
                "Retour":        "📥",
                "Achat":         "🛒",
                "Don reçu":      "🎁",
                "Location":      "🔵",
                "Vente":         "💶",
                "Don sortant":   "❤️",
            }.get(row.get("Type_Mouvement", ""), "🔄")
            st.markdown(
                f"{icon} **{row.get('Nom_Matériel','?')}** — "
                f"{row.get('Type_Mouvement','?')} "
                f"*({row.get('Date','?')})*"
            )

st.divider()

st.subheader("⏰ Retours en retard ou proches")
if not df_mv.empty:
    today = datetime.now().date()
    df_retours = df_mv[
        df_mv["Type_Mouvement"].isin(["Prêt sortant", "Location"]) &
        df_mv["Date_Retour_Prévu"].notna() &
        (df_mv["Date_Retour_Prévu"] != "")
    ].copy()

    if not df_retours.empty:
        try:
            df_retours["Date_Retour_Prévu"] = pd.to_datetime(df_retours["Date_Retour_Prévu"], errors="coerce")
            df_retours = df_retours.dropna(subset=["Date_Retour_Prévu"])
            df_retours["Jours restants"] = df_retours["Date_Retour_Prévu"].dt.date.apply(lambda d: (d - today).days)
            alerte = df_retours[df_retours["Jours restants"] <= 7].sort_values("Jours restants")
            if not alerte.empty:
                if not df_mat.empty:
                    ids_sortis = set(df_mat[df_mat["Statut"].isin(["En prêt","En location"])]["ID"])
                    alerte = alerte[alerte["ID_Matériel"].isin(ids_sortis)]
                for _, row in alerte.iterrows():
                    j = int(row["Jours restants"])
                    color = "🔴" if j < 0 else ("🟠" if j <= 3 else "🟡")
                    msg = f"**{row['Nom_Matériel']}** — {row['Personne']} — "
                    if j < 0:
                        msg += f"{color} En retard de {abs(j)} jour(s)"
                    else:
                        msg += f"{color} Retour dans {j} jour(s) ({row['Date_Retour_Prévu'].strftime('%d/%m/%Y')})"
                    st.markdown(msg)
            else:
                st.success("✅ Aucun retour en retard ou imminent.")
        except Exception:
            st.info("Impossible de calculer les retards.")
    else:
        st.info("Aucune date de retour renseignée.")
else:
    st.info("Aucun mouvement enregistré.")

st.divider()
st.caption("ErgoStock • Cabinet d'ergothérapie • Données stockées dans Google Sheets")
