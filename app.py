import streamlit as st
from utils.auth import login_page, sidebar_user

st.set_page_config(
    page_title="ErgoStock – Cabinet d'ergothérapie",
    page_icon="🏥", layout="wide", initial_sidebar_state="expanded",
)

# ── Login avant tout ──────────────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    login_page()
    st.stop()

sidebar_user()

# ── Navigation : 4 pages ──────────────────────────────────────────────────────
pg = st.navigation([
    st.Page("vues/accueil.py",    title="Accueil",    icon="🏠"),
    st.Page("vues/materiel.py",   title="Matériel",   icon="📦"),
    st.Page("vues/mouvements.py", title="Mouvements", icon="🔄"),
    st.Page("vues/personnes.py",  title="Personnes",  icon="👥"),
])
pg.run()
