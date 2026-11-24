"""Éléments d'interface partagés entre les vues d'ErgoStock."""
import streamlit as st
import pandas as pd
from utils.gsheets import (
    get_materiel, get_mouvements, get_personnes, add_personne, TYPES_PERSONNE
)

ICONS = {
    "Prêt sortant": "📤", "Retour": "📥", "Achat": "🛒",
    "Don reçu": "🎁", "Prêt entrant": "📦", "Location": "🔵",
    "Vente": "💶", "Don sortant": "❤️", "Mis en réparation": "🔧",
    "Retour de réparation": "✅", "Hors service": "❌",
    "Rendu au prêteur": "↩️",
}

AUCUNE   = "— Aucune / Non renseignée —"
NOUVELLE = "— Nouvelle personne —"


@st.cache_data(ttl=30)
def load_mat():
    return get_materiel()


@st.cache_data(ttl=30)
def load_mv():
    return get_mouvements()


@st.cache_data(ttl=30)
def load_pers():
    return get_personnes()


def nom_affiche(r):
    """Nom d'une personne : société si Pro, sinon « Prénom Nom »."""
    if r.get("Type") == "Professionnel":
        return str(r.get("Nom", "")).strip()
    return f"{r.get('Prénom', '')} {r.get('Nom', '')}".strip()


def _label(r):
    if r.get("Type") == "Professionnel":
        return f"{r['Nom']} (Pro) [{r['ID']}]"
    return f"{r['Prénom']} {r['Nom']} ({r['Téléphone']}) [{r['ID']}]"


def person_form(df_p, key, allow_none=False, default_name="", titre="Personne"):
    """Sélecteur de personne (existante ou nouvelle, formulaire Pro / particulier).

    Retourne un dict : mode ("none" | "existing" | "new"), nom, contact,
    new (dict prêt pour add_personne ou None), error (str ou None).
    """
    options = ([AUCUNE] if allow_none else []) + [NOUVELLE]
    if not df_p.empty:
        options += [_label(r) for _, r in df_p.iterrows()]

    idx = 0
    if default_name:
        for i, o in enumerate(options):
            if default_name in o:
                idx = i
                break

    choix = st.selectbox(titre, options, index=idx, key=f"{key}_sel")
    res = {"mode": "none", "nom": "", "contact": "", "new": None, "error": None}

    if choix == AUCUNE:
        return res

    if choix == NOUVELLE:
        ptype = st.selectbox("Type *", TYPES_PERSONNE, key=f"{key}_type")
        prenom = ""
        if ptype == "Professionnel":
            nom   = st.text_input("Nom de la société *", key=f"{key}_nom")
            tel   = st.text_input("Téléphone", key=f"{key}_tel")
            email = st.text_input("Email", key=f"{key}_email")
        else:
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom *", key=f"{key}_nom")
                tel = st.text_input("Téléphone", key=f"{key}_tel")
            with c2:
                prenom = st.text_input("Prénom", key=f"{key}_prenom")
                email  = st.text_input("Email", key=f"{key}_email")
        res["mode"] = "new"
        res["new"] = {
            "Nom": nom.strip(), "Prénom": prenom.strip(),
            "Téléphone": tel.strip(), "Email": email.strip(), "Type": ptype,
        }
        res["nom"] = nom.strip() if ptype == "Professionnel" else f"{prenom} {nom}".strip()
        res["contact"] = tel.strip()
        if not nom.strip():
            res["error"] = "Le nom de la personne est obligatoire."
        return res

    p_id = choix.split("[")[-1].rstrip("]")
    p_row = df_p[df_p["ID"] == p_id]
    res["mode"] = "existing"
    if not p_row.empty:
        pr = p_row.iloc[0]
        res["nom"] = nom_affiche(pr)
        res["contact"] = pr.get("Téléphone", "")
    return res


def person_save(res):
    """Crée la personne si c'est une nouvelle, puis renvoie (nom, contact)."""
    if res["mode"] == "new" and res["new"] and res["new"]["Nom"]:
        add_personne(res["new"])
    return res["nom"], res["contact"]


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
