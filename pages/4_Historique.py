st.dataframe(
    display[cols_show].rename(columns={
        "Nom_Matériel":         "Matériel",
        "Type_Mouvement":       "Mouvement",
        "Date_Retour_Prévu":    "Retour prévu",
        "Date_Retour_Effectif": "Retour effectif",
    }),
    use_container_width=True,
    hide_index=True,
)

# Lien vers la fiche matériel
st.markdown("**🔍 Voir la fiche d'un article :**")
ids_disponibles = filtered["ID_Matériel"].dropna().unique().tolist()
noms_disponibles = {
    row["ID_Matériel"]: row["Nom_Matériel"]
    for _, row in filtered.drop_duplicates(subset="ID_Matériel").iterrows()
}
options = {f"[{id}] {noms_disponibles.get(id,'')}": id for id in ids_disponibles}

if options:
    col1, col2 = st.columns([3, 1])
    with col1:
        choix = st.selectbox("Sélectionner un article", list(options.keys()), label_visibility="collapsed")
    with col2:
        if st.button("🔍 Voir la fiche", type="primary", use_container_width=True):
            st.query_params["mat_id"] = options[choix]
            st.switch_page("pages/5_Fiche_Materiel.py")
