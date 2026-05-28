# DREPPNF Yaagda Platform

Base de developpement Django pour une plateforme intelligente de suivi et d'evaluation
des innovations educatives (metiers scolaires, TIC et anglais).

## Demarrage rapide

1. Creer la base locale:
   `python manage.py migrate`
2. Creer un compte administrateur:
   `python manage.py createsuperuser`
3. Lancer le serveur:
   `python manage.py runserver`

## Notes techniques

- La configuration par defaut utilise SQLite pour accelerer le developpement.
- Si les variables `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`
  et `MYSQL_PORT` sont definies, le projet bascule automatiquement sur MySQL.
- Si votre dossier de travail est synchronise par OneDrive, vous pouvez definir
  `SQLITE_PATH` vers un chemin local classique pour eviter les erreurs d'ecriture.
- Les recommandations automatiques sont generees a partir des evaluations via un
  mecanisme de signaux Django.
- Le module IA du tableau de bord analyse les ecoles a partir des activites,
  evaluations, recommandations et preuves terrain.
- Si `scikit-learn` est disponible, le clustering IA utilise `K-Means`.
  Sinon, le projet bascule automatiquement sur un moteur local `numpy`
  pour rester fonctionnel.
- Une page dediee `Analyse IA` presente le modele, les profils detectes,
  les scores de risque, les scores de confiance et permet l'export PDF.
