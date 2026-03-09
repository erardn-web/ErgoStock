# 🏥 ErgoStock — Gestion de stock pour cabinet d'ergothérapie

Application web de gestion du matériel d'un cabinet d'ergothérapie, construite avec **Streamlit** et **Google Sheets**.

---

## 🚀 Fonctionnalités

| Page | Description |
|------|-------------|
| 🏠 **Tableau de bord** | Vue d'ensemble : statuts, alertes retards, derniers mouvements |
| 📦 **Inventaire** | Liste complète avec filtres, vue galerie avec photos |
| ➕ **Ajouter du matériel** | Formulaire complet + génération automatique de QR code |
| 🔄 **Mouvement** | Enregistrer prêt / retour / vente / don / location |
| 📜 **Historique** | Journal complet filtrable + export CSV |
| 🔍 **Fiche matériel** | Détail article, historique, QR code téléchargeable, édition |
| 👥 **Personnes** | Gestion des patients, familles, donateurs |

---

## 🛠️ Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/VOTRE_USER/ergo-stock.git
cd ergo-stock
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configurer Google Sheets (une seule fois)

#### a) Créer un projet Google Cloud

1. Allez sur [console.cloud.google.com](https://console.cloud.google.com)
2. Créez un nouveau projet (ex : `ergo-stock`)
3. Activez les APIs suivantes :
   - **Google Sheets API**
   - **Google Drive API**

#### b) Créer un compte de service

1. Dans le menu → **IAM et administration** → **Comptes de service**
2. Cliquez sur **Créer un compte de service**
3. Donnez-lui un nom (ex : `ergostock-bot`)
4. Cliquez sur **Créer et continuer**, puis **Terminer**
5. Cliquez sur le compte créé → onglet **Clés** → **Ajouter une clé** → **JSON**
6. Téléchargez le fichier JSON — **gardez-le secret !**

#### c) Créer le Google Sheet

1. Allez sur [sheets.google.com](https://sheets.google.com)
2. Créez un nouveau classeur, nommez-le exactement **`ErgoStock`**
3. Copiez l'adresse email du compte de service (format `...@....iam.gserviceaccount.com`)
4. Dans le classeur → **Partager** → collez l'email → donnez le rôle **Éditeur**

#### d) Configurer les secrets Streamlit

Copiez le fichier exemple :

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Ouvrez `.streamlit/secrets.toml` et remplissez avec le contenu du fichier JSON téléchargé :

```toml
spreadsheet_name = "ErgoStock"

[gcp_service_account]
type = "service_account"
project_id = "votre-project-id"
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "ergostock-bot@votre-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

> ⚠️ **Important :** N'ajoutez jamais `secrets.toml` sur GitHub ! Le fichier `.gitignore` l'exclut déjà.

### 4. Lancer l'application

```bash
streamlit run app.py
```

Ouvrez votre navigateur sur [http://localhost:8501](http://localhost:8501)

---

## ☁️ Déploiement sur Streamlit Cloud (gratuit)

1. Poussez votre code sur GitHub (**sans** `secrets.toml`)
2. Allez sur [share.streamlit.io](https://share.streamlit.io)
3. Connectez votre compte GitHub et sélectionnez le dépôt
4. Dans **Advanced settings** → **Secrets**, collez le contenu de votre `secrets.toml`
5. Cliquez **Deploy** !

Votre application sera accessible via une URL publique partageable avec toute l'équipe.

---

## 📷 Ajouter des photos

1. Prenez une photo du matériel
2. Uploadez-la sur **Google Drive**
3. Clic droit → **Partager** → **Tout le monde avec le lien peut voir**
4. Copiez le lien et transformez-le en lien direct :
   - Lien Drive : `https://drive.google.com/file/d/XXXID/view`
   - Lien direct : `https://drive.google.com/uc?id=XXXID`
5. Collez cette URL dans le champ **Photo URL** du formulaire

---

## 🔲 QR Codes

Chaque article génère automatiquement un QR code lors de son ajout. Vous pouvez :
- Télécharger le QR code en PNG depuis la fiche article
- L'imprimer et le coller sur le matériel
- Le scanner avec n'importe quel smartphone pour identifier l'article

---

## 📊 Structure Google Sheets

L'application crée automatiquement 3 onglets :

| Onglet | Contenu |
|--------|---------|
| **Matériel** | Inventaire complet (ID, Nom, Catégorie, Statut, Photo…) |
| **Mouvements** | Historique de tous les mouvements |
| **Personnes** | Patients, familles, donateurs, prêteurs |

---

## 🔒 Sécurité

- Les credentials Google ne sont **jamais** dans le code
- Le fichier `secrets.toml` est dans `.gitignore`
- Sur Streamlit Cloud, les secrets sont chiffrés

---

## 📝 .gitignore recommandé

```
.streamlit/secrets.toml
__pycache__/
*.pyc
.env
*.json
```

---

## 🆘 Support

En cas de problème de connexion, vérifiez :
1. Que le Google Sheet est bien partagé avec l'email du compte de service
2. Que les APIs Sheets et Drive sont activées dans Google Cloud
3. Que le nom du classeur dans `secrets.toml` correspond exactement
