# Déploiement DigitalOcean App Platform

Cette configuration permet de déployer SAGE YAADGA sur DigitalOcean App Platform
sans arrêter Render. Render reste disponible comme solution de secours pendant les
tests.

## Préparation

Le fichier `.do/app.yaml` décrit l'application pour DigitalOcean :

- branche GitHub : `main` ;
- commande de build : `bash build.sh` ;
- commande de lancement : `gunicorn dreppnf_platform.wsgi:application ...` ;
- health check : `/health/` ;
- région : `fra` ;
- taille recommandée : `professional-xs`.

## Variables à renseigner dans DigitalOcean

Renseigner ces variables comme secrets dans l'interface DigitalOcean :

- `DATABASE_URL` : URL de connexion Neon ;
- `SECRET_KEY` : clé secrète Django ;
- `SAGE_ADMIN_USERNAME` : identifiant du premier administrateur ;
- `SAGE_ADMIN_EMAIL` : email du premier administrateur ;
- `SAGE_ADMIN_PASSWORD` : mot de passe du premier administrateur ;
- `CLOUDINARY_CLOUD_NAME` : nom Cloudinary ;
- `CLOUDINARY_API_KEY` : clé Cloudinary ;
- `CLOUDINARY_API_SECRET` : secret Cloudinary.

Les variables suivantes sont déjà prévues dans `.do/app.yaml` :

- `DEBUG=False` ;
- `PYTHON_VERSION=3.12.8` ;
- `ALLOWED_HOSTS=.ondigitalocean.app` ;
- `CSRF_TRUSTED_ORIGINS=https://*.ondigitalocean.app`.

## Procédure

1. Créer une nouvelle application DigitalOcean App Platform depuis le dépôt
   GitHub `Azakary88/SAGE-Yaagda`.
2. Choisir la branche `main`.
3. Vérifier que DigitalOcean détecte `.do/app.yaml`.
4. Renseigner les secrets listés ci-dessus.
5. Lancer le déploiement.
6. Tester l'URL DigitalOcean : connexion, tableau de bord, création d'activité,
   upload d'image, rapports PDF et module IA.
7. Garder Render actif jusqu'à validation complète.

## Après validation

Si un domaine personnalisé est utilisé, ajouter ce domaine dans DigitalOcean puis
mettre à jour :

- `ALLOWED_HOSTS` avec le domaine ;
- `CSRF_TRUSTED_ORIGINS` avec `https://votre-domaine`.

Ensuite seulement, le trafic peut être basculé vers DigitalOcean.
