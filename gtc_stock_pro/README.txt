GTC Stock — Aperçu statique (bonnes pratiques front-end)
===========================================================

STRUCTURE DU PROJET
--------------------
gtc_stock_pro/
├── index.html               -> Tableau de bord
├── connexion.html            -> Page de connexion
├── creation_compte.html       -> Page de création de compte
├── entrees_sorties.html        -> Saisie des entrées / sorties de stock
├── fiche_stock.html             -> Détail et historique par article
├── rapprochement.html            -> Rapprochement automatique avec Sage 100
├── alertes.html                   -> Liste des alertes (écarts, seuils critiques)
├── utilisateurs.html               -> Gestion des comptes (vue administrateur)
├── css/
│   └── style.css                     -> Tout le CSS custom du projet
├── js/
│   └── main.js                         -> Interactions (afficher/masquer mdp, validation de formulaire)
└── README.txt (ce fichier)

Les 8 pages sont reliées entre elles par le même menu latéral.


CE QUI EST EN LOCAL VS EN CDN
-------------------------------
- css/style.css et js/main.js : 100% en local, dans ce dossier.
- Bootstrap (CSS) et Bootstrap Icons : chargés depuis un CDN (lien internet),
  car mon environnement de génération n'a pas d'accès internet pour
  télécharger ces fichiers et te les inclure directement dans le zip.
  => Ces 3 pages ont donc besoin d'une connexion internet pour s'afficher
     correctement (le temps de charger Bootstrap).

Pour un fonctionnement 100% hors-ligne (nécessaire pour le vrai déploiement
sur le réseau local de GTC sarl), il faudra :
  1. Télécharger toi-même bootstrap.min.css et bootstrap-icons sur un poste
     connecté (depuis getbootstrap.com et icons.getbootstrap.com)
  2. Les placer dans css/vendor/ et remplacer les liens <link href="https://...">
     par des liens locaux, ex : <link href="css/vendor/bootstrap.min.css">
  3. C'est exactement ce que fait déjà le template Volt Flask qu'on utilisera
     pour la vraie application : ses fichiers Bootstrap sont fournis en local.


SÉCURITÉ — CE QUI EST FAIT ICI, ET SES LIMITES
-------------------------------------------------
Mesures présentes dans ces pages (bonnes pratiques front-end) :
  - Content-Security-Policy (balise <meta>) : limite les sources autorisées
    à charger du CSS/JS, réduit le risque d'injection de scripts externes
  - autocomplete="current-password" (connexion) vs "new-password" (création) :
    évite que le navigateur propose un mot de passe déjà utilisé ailleurs
  - minlength="8" + indicateur visuel de robustesse du mot de passe
  - Vérification que les deux champs "mot de passe" / "confirmation"
    correspondent avant envoi
  - Champs "required" + validation Bootstrap (empêche l'envoi d'un
    formulaire incomplet)
  - Bouton afficher/masquer le mot de passe (évite les fautes de frappe
    invisibles, donc des mots de passe mal choisis par erreur)

CE QUE CES MESURES NE FONT PAS (limite honnête) :
  Ces pages sont 100% statiques : aucun serveur, aucune base de données
  derrière. Le JavaScript peut toujours être désactivé ou modifié par la
  personne qui utilise le navigateur — donc TOUTE validation faite ici
  est un confort d'utilisation, jamais une garantie de sécurité.

  La vraie sécurité de ton application devra être assurée plus tard,
  côté serveur, avec Flask :
    - Hachage du mot de passe (jamais stocké en clair) via
      werkzeug.security (generate_password_hash / check_password_hash)
    - Revalidation de TOUS les champs côté serveur (ne jamais faire
      confiance aux données envoyées par le navigateur)
    - Protection CSRF sur les formulaires (Flask-WTF le fait automatiquement)
    - Requêtes préparées (paramétrées) pour toute interaction avec la base
      de données — y compris la lecture de la base Sage 100 — afin d'éviter
      les injections SQL
    - Limitation du nombre de tentatives de connexion (protection contre
      les attaques par force brute)
    - Connexion en HTTPS une fois déployé sur le réseau de l'entreprise

  C'est le module authentication/ déjà présent dans le template Volt Flask
  qui gère une bonne partie de ces points — on s'appuiera dessus plutôt
  que de tout recoder.


COMMENT UTILISER CES FICHIERS
--------------------------------
1. Décompresser le zip en conservant la structure des dossiers
   (css/ et js/ doivent rester à côté des fichiers .html)
2. Ouvrir index.html, connexion.html ou creation_compte.html dans un
   navigateur (connexion internet nécessaire pour Bootstrap, voir plus haut)
3. Les 3 pages sont reliées entre elles par des liens
