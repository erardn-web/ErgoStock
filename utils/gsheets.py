import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
import uuid
import time

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_MATERIEL   = "Matériel"
SHEET_MOUVEMENTS = "Mouvements"
SHEET_PERSONNES  = "Personnes"

HEADERS_MATERIEL = [
    "ID", "Nom", "Catégorie", "Description", "État",
    "Photo_URL", "Statut", "Date_Acquisition",
    "Mode_Acquisition", "Valeur_EUR", "Notes", "Disponibilités"
]

HEADERS_MOUVEMENTS = [
    "ID_Mouvement", "ID_Matériel", "Nom_Matériel", "Date",
    "Type_Mouvement", "Personne", "Contact",
    "Date_Retour_Prévu", "Date_Retour_Effectif", "Notes", "Horodatage"
]

HEADERS_PERSONNES = [
    "ID", "Nom", "Prénom", "Téléphone", "Email", "Type", "Notes"
]

STATUS_COLORS = {
    "Disponible":    "🟢",
    "En prêt":       "🟡",
    "En location":   "🔵",
    "Vendu":         "🔴",
    "Donné":         "⚫",
    "En réparation": "🟠",
    "Hors service":  "❌",
}

TYPES_MOUVEMENT = [
    "Achat", "Don reçu", "Prêt entrant", "Prêt sortant",
    "Location", "Vente", "Don sortant", "Retour",
    "Mis en réparation", "Retour de réparation", "Hors service",
]

STATUS_AFTER_MOUVEMENT = {
    "Achat":                "Disponible",
    "Don reçu":             "Disponible",
    "Prêt entrant":         "Disponible",
    "Prêt sortant":         "En prêt",
    "Location":             "En location",
    "Vente":                "Vendu",
    "Don sortant":          "Donné",
    "Retour":               "Disponible",
    "Mis en réparation":    "En réparation",
    "Retour de réparation": "Disponible",
    "Hors service":         "Hors service",
}

CATEGORIES = [
    "Aide à la mobilité", "Aide à la communication", "Aide à la préhension",
    "Aide à la vie quotidienne", "Orthèse / Attelle", "Siège / Positionnement",
    "Jeu / Loisir", "Évaluation / Bilan", "Formation / Documentation", "Autre",
]

ETATS = ["Neuf", "Très bon", "Bon", "Correct", "Usagé", "À réparer"]
TYPES_PERSONNE = ["Patient", "Professionnel", "Autre"]


# ── Connexion ─────────────────────────────────────────────────────────────────

@st.cache_resource(ttl=3600)
def get_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet():
    client = get_client()
    return client.open(st.secrets["spreadsheet_name"])


def get_or_create_sheet(spreadsheet, name: str, headers: list):
    for attempt in range(3):
        try:
            ws = spreadsheet.worksheet(name)
            existing = ws.row_values(1)
            if not existing:
                ws.append_row(headers)
            return ws
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=name, rows=2000, cols=len(headers))
            ws.append_row(headers)
            return ws
        except gspread.exceptions.APIError as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise e


def init_sheets():
    try:
        spreadsheet = get_spreadsheet()
        get_or_create_sheet(spreadsheet, SHEET_MATERIEL,   HEADERS_MATERIEL)
        get_or_create_sheet(spreadsheet, SHEET_MOUVEMENTS, HEADERS_MOUVEMENTS)
        get_or_create_sheet(spreadsheet, SHEET_PERSONNES,  HEADERS_PERSONNES)
        return True, "✅ Connexion Google Sheets établie avec succès."
    except Exception as e:
        return False, f"❌ Erreur de connexion : {e}"


# ── Lecture ───────────────────────────────────────────────────────────────────

def _safe_df(ws, headers):
    try:
        data = ws.get_all_records(expected_headers=headers)
    except Exception:
        try:
            data = ws.get_all_records()
        except Exception:
            return pd.DataFrame(columns=headers)
    if not data:
        return pd.DataFrame(columns=headers)
    df = pd.DataFrame(data)
    for col in headers:
        if col not in df.columns:
            df[col] = ""
    return df


def get_materiel() -> pd.DataFrame:
    spreadsheet = get_spreadsheet()
    ws = get_or_create_sheet(spreadsheet, SHEET_MATERIEL, HEADERS_MATERIEL)
    return _safe_df(ws, HEADERS_MATERIEL)


def get_mouvements() -> pd.DataFrame:
    spreadsheet = get_spreadsheet()
    ws = get_or_create_sheet(spreadsheet, SHEET_MOUVEMENTS, HEADERS_MOUVEMENTS)
    return _safe_df(ws, HEADERS_MOUVEMENTS)


def get_personnes() -> pd.DataFrame:
    spreadsheet = get_spreadsheet()
    ws = get_or_create_sheet(spreadsheet, SHEET_PERSONNES, HEADERS_PERSONNES)
    return _safe_df(ws, HEADERS_PERSONNES)


def get_historique_materiel(mat_id: str) -> pd.DataFrame:
    df = get_mouvements()
    if df.empty:
        return df
    filtered = df[df["ID_Matériel"] == mat_id].copy()
    if "Horodatage" in filtered.columns and filtered["Horodatage"].astype(bool).any():
        try:
            filtered["_sort"] = pd.to_datetime(filtered["Horodatage"], errors="coerce")
            filtered = filtered.sort_values("_sort", ascending=False).drop(columns=["_sort"])
            return filtered
        except Exception:
            pass
    return filtered.sort_values("Date", ascending=False)


# ── Helpers disponibilités ────────────────────────────────────────────────────

def encode_disponibilites(tester: bool, preter: bool, vendre: bool) -> str:
    parts = []
    if tester: parts.append("À tester")
    if preter: parts.append("À prêter")
    if vendre: parts.append("À vendre")
    return ", ".join(parts)


def decode_disponibilites(value: str):
    v = value or ""
    return {
        "tester": "À tester" in v,
        "preter": "À prêter" in v,
        "vendre": "À vendre" in v,
    }


# ── Écriture ──────────────────────────────────────────────────────────────────

def _gen_id() -> str:
    return str(uuid.uuid4())[:8].upper()


def add_materiel(data: dict) -> str:
    mat_id = _gen_id()
    spreadsheet = get_spreadsheet()
    ws = get_or_create_sheet(spreadsheet, SHEET_MATERIEL, HEADERS_MATERIEL)
    row = [
        mat_id,
        data.get("Nom", ""),
        data.get("Catégorie", ""),
        data.get("Description", ""),
        data.get("État", ""),
        data.get("Photo_URL", ""),
        "Disponible",
        data.get("Date_Acquisition", datetime.now().strftime("%Y-%m-%d")),
        data.get("Mode_Acquisition", ""),
        data.get("Valeur_EUR", ""),
        data.get("Notes", ""),
        data.get("Disponibilités", ""),
    ]
    ws.append_row(row)
    return mat_id


def update_materiel(mat_id: str, data: dict) -> bool:
    try:
        spreadsheet = get_spreadsheet()
        ws = get_or_create_sheet(spreadsheet, SHEET_MATERIEL, HEADERS_MATERIEL)
        cell = ws.find(mat_id, in_column=1)
        if not cell:
            return False
        for col_name, value in data.items():
            if col_name in HEADERS_MATERIEL:
                col_idx = HEADERS_MATERIEL.index(col_name) + 1
                ws.update_cell(cell.row, col_idx, value)
        return True
    except Exception as e:
        st.error(f"Erreur mise à jour matériel : {e}")
        return False


def update_statut_materiel(mat_id: str, type_mouvement: str):
    new_status = STATUS_AFTER_MOUVEMENT.get(type_mouvement, "Disponible")
    update_materiel(mat_id, {"Statut": new_status})


def add_mouvement(data: dict):
    mv_id = _gen_id()
    spreadsheet = get_spreadsheet()
    ws = get_or_create_sheet(spreadsheet, SHEET_MOUVEMENTS, HEADERS_MOUVEMENTS)
    row = [
        mv_id,
        data.get("ID_Matériel", ""),
        data.get("Nom_Matériel", ""),
        data.get("Date", datetime.now().strftime("%Y-%m-%d")),
        data.get("Type_Mouvement", ""),
        data.get("Personne", ""),
        data.get("Contact", ""),
        data.get("Date_Retour_Prévu", ""),
        data.get("Date_Retour_Effectif", ""),
        data.get("Notes", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ]
    ws.append_row(row)
    update_statut_materiel(data["ID_Matériel"], data["Type_Mouvement"])
    return mv_id


def add_personne(data: dict) -> str:
    p_id = _gen_id()
    spreadsheet = get_spreadsheet()
    ws = get_or_create_sheet(spreadsheet, SHEET_PERSONNES, HEADERS_PERSONNES)
    row = [
        p_id,
        data.get("Nom", ""),
        data.get("Prénom", ""),
        data.get("Téléphone", ""),
        data.get("Email", ""),
        data.get("Type", ""),
        data.get("Notes", ""),
    ]
    ws.append_row(row)
    return p_id


def update_personne(p_id: str, data: dict) -> bool:
    try:
        spreadsheet = get_spreadsheet()
        ws = get_or_create_sheet(spreadsheet, SHEET_PERSONNES, HEADERS_PERSONNES)
        cell = ws.find(p_id, in_column=1)
        if not cell:
            return False
        for col_name, value in data.items():
            if col_name in HEADERS_PERSONNES:
                col_idx = HEADERS_PERSONNES.index(col_name) + 1
                ws.update_cell(cell.row, col_idx, value)
        return True
    except Exception as e:
        st.error(f"Erreur mise à jour personne : {e}")
        return False


# ── Upload photo ImgBB ────────────────────────────────────────────────────────

def upload_photo_to_drive(image_bytes: bytes, filename: str) -> str:
    try:
        import base64, requests
        api_key   = "1bce8a9184c42475f79f73c5e2f3c60c"
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        response  = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": image_b64, "name": filename},
            timeout=30,
        )
        result = response.json()
        if result.get("success"):
            return result["data"]["url"]
        else:
            st.error(f"Erreur ImgBB : {result.get('error', {}).get('message', 'Inconnue')}")
            return ""
    except Exception as e:
        st.error(f"Erreur upload photo : {e}")
        return ""
