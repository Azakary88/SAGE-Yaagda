# SAGA YAADGA

Système d'accompagnement et de gestion des activités éducatives du Yaadga.

Base Django pour une plateforme intelligente de suivi et d'evaluation des innovations
educatives (metiers scolaires, TIC et anglais).

## Demarrage rapide

1. Creer les tables:
   `python manage.py migrate`
2. Creer un compte administrateur:
   `python manage.py createsuperuser`
3. Lancer le serveur:
   `python manage.py runserver`

## Notes techniques

- En production, Render fournit `DATABASE_URL` et le projet utilise PostgreSQL.
- Pour un test local rapide sans PostgreSQL, definir `USE_SQLITE=1`.
- Pour conserver MySQL dans un environnement distinct, installer aussi
  `requirements-mysql.txt` puis definir les variables `MYSQL_DATABASE`,
  `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST` et `MYSQL_PORT`.
- Si le mode SQLite est utilise dans un dossier synchronise par OneDrive, vous
  pouvez definir `SQLITE_PATH` vers un chemin local classique pour eviter les
  erreurs d'ecriture.
- Les recommandations automatiques sont generees a partir des evaluations via un
  mecanisme de signaux Django.
- Le module IA du tableau de bord analyse les ecoles a partir des activites,
  evaluations, recommandations et preuves terrain.
- Si `scikit-learn` est disponible, le clustering IA utilise `K-Means`.
  Sinon, le projet bascule automatiquement sur un moteur local `numpy`
  pour rester fonctionnel.
- Une page dediee `Analyse IA` presente le modele, les profils detectes,
  les scores de risque, les scores de confiance et permet l'export PDF.

## Deploiement sur Render

1. Creer un depot GitHub et y envoyer le projet.
2. Dans Render, creer un nouveau service a partir du depot puis laisser Render
   detecter le fichier `render.yaml`.
3. Verifier que la base PostgreSQL et les variables `DATABASE_URL`, `SECRET_KEY`
   et `DEBUG=False` sont definies.
4. Apres le premier deploiement, ouvrir le Shell Render et lancer :
   `python manage.py createsuperuser`.
