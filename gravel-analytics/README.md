# Gravel Analytics

Dashboard personnel d'analyse de tes sorties gravel, à partir des données
Garmin Connect : zones de puissance, progression vers ton objectif de 260W
en Z2, charge d'entraînement (CTL/ATL/TSB), vitesse, dénivelé, courbe de
puissance.

## Comment ça marche

```
Garmin Connect  --(garminconnect, non-officiel)-->  SQLite local  -->  Dashboard Streamlit
```

- **`app/garmin_sync.py`** — connexion à Garmin Connect (librairie non-officielle
  `garminconnect`, il n'existe pas d'API publique pour les comptes particuliers).
- **`app/db.py`** — cache local SQLite des activités (évite de re-télécharger
  à chaque ouverture, limite la fréquence des appels à Garmin).
- **`app/analysis.py`** — zones de puissance (modèle Coggan, basées sur ta FTP),
  puissance normalisée, TSS, CTL/ATL/TSB, suivi de la progression Z2.
- **`app/sync.py`** — orchestre la synchro complète.
- **`app/streamlit_app.py`** — le dashboard.

## 1. Lancer en local

```bash
cd gravel-analytics
pip install -r requirements.txt
cp .env.example .env        # puis renseigne GARMIN_EMAIL / GARMIN_PASSWORD
export $(cat .env | xargs)  # charge les variables d'environnement
streamlit run app/streamlit_app.py
```

Au premier lancement, clique sur **"Synchroniser avec Garmin Connect"** dans
la barre latérale. La session Garmin est ensuite mise en cache localement
(`~/.garminconnect`) pour éviter de se reconnecter à chaque fois.

## 2. Déployer gratuitement (Streamlit Community Cloud)

C'est l'option la plus simple pour avoir une vraie URL accessible depuis ton
téléphone, sans gérer de serveur :

1. Pousse ce dossier sur un repo GitHub (le `.gitignore` fourni exclut déjà
   tes identifiants).
2. Va sur [share.streamlit.io](https://share.streamlit.io), connecte ton
   compte GitHub, choisis le repo et indique `app/streamlit_app.py` comme
   fichier principal.
3. Dans les réglages de l'appli déployée → **Secrets**, colle le contenu de
   `.streamlit/secrets.toml.example` en remplaçant par tes vrais identifiants.
4. Déploie. Ton dashboard est en ligne, privé par défaut (tu peux restreindre
   l'accès à ton compte Google/GitHub dans les réglages).

### Autres options d'hébergement
Le code est un Streamlit standard, donc il tourne aussi sans modification sur
Render, Railway ou Fly.io (déploiement par Dockerfile ou buildpack Python) si
tu préfères ne pas dépendre de Streamlit Cloud, ou sur ton propre serveur/NAS.

## 3. Synchronisation automatique (optionnel)

Pour ne pas avoir à cliquer sur "Synchroniser" à chaque visite, tu peux lancer
`python app/sync.py` sur un cron (ex. tous les matins) — en local, sur un
Raspberry Pi, ou via une tâche planifiée si tu héberges le code ailleurs que
sur Streamlit Cloud (qui n'a pas de cron natif).

## Limites connues

- **API non-officielle** : `garminconnect`/`garth` font du reverse engineering
  de l'interface web de Garmin. Ça fonctionne bien en pratique mais Garmin
  peut changer son API sans préavis ; si la synchro casse un jour, c'est
  probablement la cause.
- **Vérification en 2 étapes** : si ton compte Garmin a la double
  authentification activée, la connexion automatique échouera — il faut la
  désactiver pour ce compte, ou utiliser un compte Garmin dédié.
- **Puissance** : les analyses de zones/TSS nécessitent un capteur de
  puissance sur ton vélo. Sans capteur, tu as quand même vitesse, dénivelé,
  FC et distance.
- **Zones de puissance** : le modèle Coggan par défaut (% de FTP) est une
  base standard, modifiable dans `app/analysis.py` (`DEFAULT_ZONES`) si ton
  coach utilise une autre répartition.

## Prochaines pistes

- Ajouter un export CSV/PDF des sorties filtrées.
- Détecter automatiquement les sorties "Sombra Grus" vs autres vélos via le
  champ équipement Garmin.
- Graphe de récupération (TSB) avec alertes avant les sorties clés.
