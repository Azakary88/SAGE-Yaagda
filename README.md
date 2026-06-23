# SAGA YAADGA

Système d'accompagnement et de gestion des activités éducatives du Yaadga.

Base Django pour une plateforme intelligente de suivi et d'evaluation des innovations
educatives (metiers scolaires, TIC et anglais).

## Demarrage rapide

1. Configurer la base MySQL:
   `$env:MYSQL_DATABASE='saga_yaadga'`
   `$env:MYSQL_USER='root'`
   `$env:MYSQL_PASSWORD='mot_de_passe'`
   `$env:MYSQL_HOST='127.0.0.1'`
   `$env:MYSQL_PORT='3306'`
2. Creer les tables:
   `python manage.py migrate`
3. Creer un compte administrateur:
   `python manage.py createsuperuser`
4. Lancer le serveur:
   `python manage.py runserver`

## Notes techniques

- La configuration utilise MySQL lorsque `MYSQL_DATABASE` est defini.
- Pour un test local rapide sans MySQL, definir `USE_SQLITE=1`.
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
