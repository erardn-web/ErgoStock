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
