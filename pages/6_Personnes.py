import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.gsheets import get_personnes, add_personne, update_personne, get_mouvements, TYPES_PERSONNE

st.set_page_config(page_title="Personnes – ErgoStock", page_icon="👥", layout="wide")
st.title("👥 Personnes")
st.divider()

@st.cache_data(ttl=30)
def load():
    return get_personnes(), get_mouvements()

df_p, df_mv = load()

tab1, tab2 = st.tabs(["📋 Liste des personnes", "➕ Ajouter une personne"])

# ── Onglet liste ───────────────────────────────────────────────────────────────
with tab1:
    if df_p.empty:
        st.info("Aucune personne enregistrée.")
    else:
        search = st.text_input("🔍 Rechercher", "")
        filtre_type = st.selectbox("Type", ["Tous"] + TYPES_PERSONNE)

        filtered = df_p.copy()
        if search:
            mask = (
                filtered["Nom"].str.contains(search, case=False, na=False) |
                filtered["Prénom"].str.contains(search, case=False, na=False) |
                filtered["Téléphone"].str.contains(search, case=False, na=False) |
                filtered["Email"].str.contains(search, case=False, na=False)
            )
            filtered = filtered[mask]
        if filtre_type != "Tous":
            filtered = filtered[filtered["Type"] == filtre_type]

        st.caption(f"**{len(filtered)}** personne(s)")
        st.dataframe(filtered, use_container_width=True, hide_index=True)

        # Fiche détail
        st.divider()
        st.subheader("🔍 Détail d'une personne")
        if not filtered.empty:
            p_options = {
                f"[{r['ID']}] {r['Prénom']} {r['Nom']}": r['ID']
                for _, r in filtered.iterrows()
            }
            p_label = st.selectbox("Choisir une personne", list(p_options.keys()))
            p_id = p_options[p_label]
            p_row = df_p[df_p["ID"] == p_id].iloc[0]

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Nom :** {p_row.get('Prénom','')} {p_row.get('Nom','')}")
                st.markdown(f"**Type :** {p_row.get('Type','')}")
                st.markdown(f"**Téléphone :** {p_row.get('Téléphone','')}")
            with c2:
                st.markdown(f"**Email :** {p_row.get('Email','')}")
                st.markdown(f"**Notes :** {p_row.get('Notes','')}")

            # Historique mouvements de cette personne
            if not df_mv.empty:
                p_hist = df_mv[
                    df_mv["Personne"].str.contains(
                        f"{p_row.get('Prénom','')} {p_row.get('Nom','')}".strip(),
                        case=False, na=False
                    )
                ].sort_values("Date", ascending=False)
                if not p_hist.empty:
                    st.subheader("📜 Historique des emprunts")
                    cols = [c for c in ["Date","Nom_Matériel","Type_Mouvement",
                                         "Date_Retour_Prévu","Date_Retour_Effectif","Notes"]
                            if c in p_hist.columns]
                    st.dataframe(p_hist[cols], use_container_width=True, hide_index=True)

            # Modifier
            with st.expander("✏️ Modifier"):
                with st.form("form_edit_p"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_nom    = st.text_input("Nom",    value=p_row.get("Nom",""))
                        e_tel    = st.text_input("Téléphone", value=p_row.get("Téléphone",""))
                    with ec2:
                        e_prenom = st.text_input("Prénom", value=p_row.get("Prénom",""))
                        e_email  = st.text_input("Email",  value=p_row.get("Email",""))
                    e_type  = st.selectbox("Type", TYPES_PERSONNE,
                                           index=TYPES_PERSONNE.index(p_row["Type"])
                                           if p_row.get("Type") in TYPES_PERSONNE else 0)
                    e_notes = st.text_area("Notes", value=p_row.get("Notes",""))
                    if st.form_submit_button("💾 Enregistrer", type="primary"):
                        ok = update_personne(p_id, {
                            "Nom": e_nom, "Prénom": e_prenom,
                            "Téléphone": e_tel, "Email": e_email,
                            "Type": e_type, "Notes": e_notes
                        })
                        if ok:
                            st.success("✅ Personne mise à jour.")
                            st.cache_data.clear()

# ── Onglet ajout ───────────────────────────────────────────────────────────────
with tab2:
    with st.form("form_add_p", clear_on_submit=True):
        a1, a2 = st.columns(2)
        with a1:
            a_nom    = st.text_input("Nom *")
            a_tel    = st.text_input("Téléphone")
            a_type   = st.selectbox("Type *", TYPES_PERSONNE)
        with a2:
            a_prenom = st.text_input("Prénom")
            a_email  = st.text_input("Email")
        a_notes = st.text_area("Notes")

        if st.form_submit_button("💾 Ajouter la personne", type="primary"):
            if not a_nom.strip():
                st.error("Le nom est obligatoire.")
            else:
                p_id = add_personne({
                    "Nom": a_nom.strip(), "Prénom": a_prenom.strip(),
                    "Téléphone": a_tel.strip(), "Email": a_email.strip(),
                    "Type": a_type, "Notes": a_notes,
                })
                st.success(f"✅ Personne ajoutée avec l'ID **{p_id}**.")
                st.cache_data.clear()
