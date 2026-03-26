import streamlit as st

st.set_page_config(
    page_title="ErgoStock – Cabinet d'ergothérapie",
    page_icon="🏥", layout="wide", initial_sidebar_state="expanded",
)

pg = st.navigation({
    "": [
        st.Page("app_dashboard.py", title="Tableau de bord", icon="🏥"),
    ],
    "── Quotidien ──────────────": [
        st.Page("pages/1_Ajouter_Materiel.py", title="Ajouter du matériel", icon="➕"),
        st.Page("pages/2_Mouvement.py",         title="Mouvement",           icon="🔄"),
        st.Page("pages/3_Fiche_Materiel.py",    title="Fiche matériel",      icon="🔍"),
    ],
    "── Consultation ────────────": [
        st.Page("pages/4_Inventaire.py", title="Inventaire",  icon="📦"),
        st.Page("pages/5_Historique.py", title="Historique",  icon="📜"),
        st.Page("pages/6_Personnes.py",  title="Personnes",   icon="👥"),
        st.Page("pages/7_Scanner_QR.py", title="Scanner QR",  icon="📷"),
    ],
    "── À traiter ───────────────": [
        st.Page("pages/8_Objets_Vendus.py", title="Objets vendus", icon="💼"),
    ],
})
pg.run()
