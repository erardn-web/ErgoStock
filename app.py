import hashlib
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

ROLES_AUTORISES = ["admin", "thérapeute"]
METIERS_AUTORISES = ["Ergo"]  # seuls les Ergo + admin ont accès


def hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode()).hexdigest()


@st.cache_data(ttl=300)
def load_utilisateurs_rh() -> pd.DataFrame:
    """Charge l'onglet Utilisateurs du GSheet 36.9_RH."""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open(st.secrets["rh_spreadsheet_name"])
        ws = sheet.worksheet("Utilisateurs")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur chargement utilisateurs RH : {e}")
        return pd.DataFrame()


def check_login(login: str, password: str):
    """Vérifie les credentials et les droits d'accès ErgoStock."""
    df = load_utilisateurs_rh()
    if df.empty:
        return None, "Impossible de charger les utilisateurs."

    # Filtrer comptes actifs
    if "must_actif" in df.columns:
        df = df[df["must_actif"].astype(str).isin(["1", "true", "oui", "yes", "True"])]

    # Chercher le login + mot de passe
    match = df[
        (df["login"].astype(str).str.strip() == login.strip()) &
        (df["mot_de_passe_hash"].astype(str) == hash_password(password))
    ]

    if match.empty:
        return None, "Identifiant ou mot de passe incorrect."

    user = match.iloc[0]
    role   = str(user.get("role", "")).strip().lower()
    metier = str(user.get("metier", "")).strip()

    # Vérifier les droits d'accès
    if role == "admin":
        return user, None
    if metier in METIERS_AUTORISES:
        return user, None

    return None, f"Accès non autorisé pour le métier : {metier}."


def login_page():
    """Affiche la page de connexion ErgoStock."""
    st.markdown("""
    <div style='text-align:center; padding: 40px 0 20px 0;'>
        <span style='font-size:3rem;'>🏥</span>
        <h1 style='margin:0;'>ErgoStock</h1>
        <p style='color:#888;'>Gestion du matériel d'ergothérapie</p>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        with st.form("login_form"):
            login    = st.text_input("👤 Identifiant", placeholder="Votre login")
            password = st.text_input("🔑 Mot de passe", type="password")
            submit   = st.form_submit_button("Se connecter", type="primary", use_container_width=True)

        if submit:
            if not login.strip() or not password.strip():
                st.error("Veuillez remplir tous les champs.")
            else:
                with st.spinner("Vérification…"):
                    user, erreur = check_login(login, password)
                if user is not None:
                    st.session_state["logged_in"]    = True
                    st.session_state["user_id"]      = user["id"]
                    st.session_state["user_nom"]     = user["nom"]
                    st.session_state["user_login"]   = user["login"]
                    st.session_state["user_role"]    = user["role"]
                    st.session_state["user_metier"]  = user.get("metier", "")
                    st.rerun()
                else:
                    st.error(erreur)


def logout():
    for key in ["logged_in", "user_id", "user_nom", "user_login", "user_role", "user_metier"]:
        st.session_state.pop(key, None)
    st.rerun()


def require_login():
    if not st.session_state.get("logged_in"):
        login_page()
        st.stop()


def is_admin() -> bool:
    return str(st.session_state.get("user_role", "")).strip().lower() == "admin"


def sidebar_user():
    """Affiche les infos de l'utilisateur connecté dans la sidebar."""
    with st.sidebar:
        nom    = st.session_state.get("user_nom", "")
        metier = st.session_state.get("user_metier", "")
        role   = st.session_state.get("user_role", "")
        st.markdown(f"👤 **{nom}**")
        st.caption(f"{metier} · {role}")
        st.divider()
        if st.button("🚪 Se déconnecter", use_container_width=True):
            logout()


def get_therapeute() -> str:
    """Retourne le nom du thérapeute connecté pour l'enregistrer dans les mouvements."""
    return st.session_state.get("user_nom", "")
