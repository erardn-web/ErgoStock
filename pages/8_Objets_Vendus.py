import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import get_materiel, get_mouvements, update_materiel, STATUS_COLORS

st.set_page_config(page_title="Objets vendus – ErgoStock", page_icon="💼", layout="wide")
st.title("💼 Objets vendus — Suivi des actions")
st.caption("Liste du matériel vendu pour lequel une action est à faire (commande, information fournisseur…)")
st.divider()

@st.cache_data(ttl=30)
def load_mat():
    return get_materiel()

@st.cache_data(ttl=30)
def load_mv():
    return get_mouvements()

with st.spinner("Chargement…"):
    df_mat = load_mat()
    df_mv  = load_mv()

if df_mat.empty:
    st.info("Aucun matériel enregistré.")
    st.stop()

# Filtrer les vendus
vendus = df_mat[df_mat["Statut"] == "Vendu"].copy()

if vendus.empty:
    st.success("✅ Aucun objet vendu pour le moment.")
    st.stop()

# Séparer archivés et à traiter
if "Archivé" not in vendus.columns:
    vendus["Archivé"] = ""

a_traiter = vendus[vendus["Archivé"] != "oui"].copy()
archives  = vendus[vendus["Archivé"] == "oui"].copy()

# Enrichir avec la date de vente et la personne depuis les mouvements
if not df_mv.empty:
    ventes = (
        df_mv[df_mv["Type_Mouvement"] == "Vente"]
        .sort_values("Date", ascending=False)
        .drop_duplicates(subset="ID_Matériel", keep="first")
        [["ID_Matériel", "Date", "Personne", "Contact", "Notes"]]
        .rename(columns={
            "Date":    "Date_Vente",
            "Personne": "Acheteur",
            "Contact":  "Contact_Acheteur",
            "Notes":    "Notes_Vente",
        })
    )
    a_traiter = a_traiter.merge(ventes, left_on="ID", right_on="ID_Matériel", how="left")
    archives  = archives.merge(ventes,  left_on="ID", right_on="ID_Matériel", how="left")

# ── À traiter ─────────────────────────────────────────────────────────────────
st.subheader(f"🔴 À traiter ({len(a_traiter)} objet(s))")

if a_traiter.empty:
    st.success("✅ Tout a été traité !")
else:
    for _, row in a_traiter.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])

            with c1:
                st.markdown(f"### 📦 {row['Nom']}")
                st.markdown(f"**ID :** `{row['ID']}` · **Catégorie :** {row.get('Catégorie', '')} · **État :** {row.get('État', '')}")
                if row.get("Date_Vente"):
                    st.markdown(f"📅 Vendu le : **{row['Date_Vente']}**")
                if row.get("Acheteur"):
                    ligne = f"👤 Acheteur : **{row['Acheteur']}**"
                    if row.get("Contact_Acheteur"):
                        ligne += f" · 📞 {row['Contact_Acheteur']}"
                    st.markdown(ligne)
                if row.get("Notes_Vente"):
                    st.markdown(f"💬 *{row['Notes_Vente']}*")
                if row.get("Valeur_EUR"):
                    st.markdown(f"💶 Valeur : **{row['Valeur_EUR']} €**")

            with c2:
                st.markdown("**Action effectuée :**")
                action = st.multiselect(
                    "Action",
                    [
                        "✅ Fournisseur informé",
                        "✅ Remplacement commandé",
                        "✅ Aucune action requise",
                        "✅ Autre action effectuée",
                    ],
                    key=f"action_{row['ID']}",
                    placeholder="Sélectionner une ou plusieurs actions…",
                    label_visibility="collapsed",
                )
                note_action = st.text_input(
                    "Note (optionnel)", key=f"note_{row['ID']}",
                    placeholder="Détail de l'action…"
                )

            with c3:
                st.markdown("&nbsp;")
                if st.button(
                    "📁 Archiver", key=f"archive_{row['ID']}",
                    type="primary", use_container_width=True,
                    disabled=(len(action) == 0),
                ):
                    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")
                    note_finale = f"{', '.join(action)} — {horodatage}"
                    if note_action.strip():
                        note_finale += f" — {note_action.strip()}"
                    update_materiel(row["ID"], {"Archivé": "oui"})
                    # Ajouter la note dans les notes du matériel
                    notes_existantes = row.get("Notes", "")
                    nouvelle_note = f"{notes_existantes}\n[VENTE ARCHIVÉE] {note_finale}".strip()
                    update_materiel(row["ID"], {"Notes": nouvelle_note})
                    st.success(f"✅ **{row['Nom']}** archivé.")
                    st.cache_data.clear()
                    st.rerun()

# ── Archivés ──────────────────────────────────────────────────────────────────
st.divider()
with st.expander(f"📁 Objets archivés ({len(archives)})"):
    if archives.empty:
        st.info("Aucun objet archivé pour le moment.")
    else:
        display = archives.copy()
        cols_show = [c for c in [
            "Nom", "Catégorie", "État", "Date_Vente", "Acheteur", "Valeur_EUR", "Notes"
        ] if c in display.columns]
        st.dataframe(display[cols_show], use_container_width=True, hide_index=True)

        # Possibilité de désarchiver
        st.markdown("**Désarchiver un objet :**")
        options = {f"{r['Nom']} [{r['ID']}]": r['ID'] for _, r in archives.iterrows()}
        if options:
            col1, col2 = st.columns([3, 1])
            with col1:
                choix = st.selectbox("Objet à désarchiver", list(options.keys()),
                                     label_visibility="collapsed")
            with col2:
                if st.button("↩️ Désarchiver", use_container_width=True):
                    update_materiel(options[choix], {"Archivé": ""})
                    st.success("↩️ Objet remis dans la liste à traiter.")
                    st.cache_data.clear()
                    st.rerun()
