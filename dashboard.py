"""
dashboard.py — Dashboard Streamlit pour la surveillance des plantes
===================================================================
Affiche l'historique des détections de maladies, les statistiques,
et la dernière image analysée.

Lancement : streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import os
from PIL import Image

# ─────────────────────────────────────────
# CONFIGURATION DE LA PAGE
# ─────────────────────────────────────────
st.set_page_config(
    page_title="🌿 Plant Disease Monitor",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Système Intelligent de Détection des Maladies des Plantes")
st.caption("Basé sur le dataset PlantVillage — Modèle MobileNetV2")

# ─────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────
CSV_FILE = "historique_plante.csv"

try:
    df = pd.read_csv(CSV_FILE)
except FileNotFoundError:
    st.warning(f"⏳ En attente de données... ({CSV_FILE} non trouvé)")
    df = pd.DataFrame(columns=["date", "maladie", "confiance", "statut", "image_path"])

# ─────────────────────────────────────────
# MÉTRIQUES RAPIDES (en haut)
# ─────────────────────────────────────────
if not df.empty:
    col1, col2, col3, col4 = st.columns(4)

    total         = len(df)
    nb_sain       = len(df[df["statut"] == "sain"])
    nb_eleve      = len(df[df["statut"] == "risque_eleve"])
    conf_moyenne  = df["confiance"].mean() * 100

    col1.metric("📊 Total analyses", total)
    col2.metric("🟢 Plantes saines", nb_sain)
    col3.metric("🔴 Risque élevé", nb_eleve)
    col4.metric("🎯 Confiance moy.", f"{conf_moyenne:.1f}%")

    st.divider()

# ─────────────────────────────────────────
# DERNIÈRE DÉTECTION + IMAGE
# ─────────────────────────────────────────
if not df.empty:
    last = df.iloc[-1]
    st.subheader("🔍 Dernière détection")

    left, right = st.columns([1, 2])

    with left:
        # Afficher la dernière image si elle existe
        if "image_path" in df.columns and pd.notna(last["image_path"]):
            img_path = last["image_path"]
            if os.path.exists(img_path):
                img = Image.open(img_path)
                st.image(img, caption=f"Image analysée", use_column_width=True)
            else:
                st.info("🖼️ Image non disponible localement")

    with right:
        st.markdown(f"**📅 Date :** {last['date']}")
        st.markdown(f"**🌿 Maladie détectée :** `{last['maladie']}`")
        st.markdown(f"**📊 Confiance :** {float(last['confiance']) * 100:.1f}%")

        # Alerte visuelle selon le statut
        statut = last["statut"]
        if statut == "risque_eleve":
            st.error("🔴 RISQUE ÉLEVÉ DE MALADIE — Intervention recommandée !")
        elif statut == "risque_modere":
            st.warning("🟡 Risque modéré — Surveiller de près")
        else:
            st.success("🟢 Plante saine — Aucune action requise")

    st.divider()

# ─────────────────────────────────────────
# GRAPHIQUES
# ─────────────────────────────────────────
if not df.empty:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📈 Évolution de la confiance")
        st.line_chart(df["confiance"])

    with col_b:
        st.subheader("🦠 Maladies les plus fréquentes")
        top_maladies = df["maladie"].value_counts().head(8)
        st.bar_chart(top_maladies)

    st.subheader("📋 Répartition des statuts")
    statut_counts = df["statut"].value_counts()
    st.bar_chart(statut_counts)

# ─────────────────────────────────────────
# TABLEAU DE L'HISTORIQUE
# ─────────────────────────────────────────
st.subheader("📋 Historique des mesures")
if not df.empty:
    # Afficher sans la colonne image_path (trop technique)
    df_display = df[["date", "maladie", "confiance", "statut"]].copy()
    df_display["confiance"] = (df_display["confiance"] * 100).round(1).astype(str) + "%"
    st.dataframe(df_display.tail(20), use_container_width=True)
else:
    st.info("Aucune donnée disponible pour le moment.")

# ─────────────────────────────────────────
# TÉLÉCHARGEMENT
# ─────────────────────────────────────────
if not df.empty:
    st.download_button(
        label="📥 Télécharger l'historique CSV",
        data=df.to_csv(index=False),
        file_name="historique_plante.csv",
        mime="text/csv"
    )

# Auto-refresh toutes les 10 secondes
st.caption("🔄 Rafraîchissez la page pour voir les nouvelles données")
