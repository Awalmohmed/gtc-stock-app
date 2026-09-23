# -*- encoding: utf-8 -*-
"""
GTC Stock — Photo de profil : upload, validation, stockage.

Chaque utilisateur peut changer SA PROPRE photo (voir la route
modifier_photo_profil dans views.py) ; il n'y a pas de gestion des photos
des autres comptes, même par un Administrateur — Utilisateur.photo
(apps/models.py) est une simple colonne texte, jamais exposée en écriture
ailleurs que via ce module.

Stockage : le fichier est enregistré sous app.config['AVATARS_UPLOAD_DIR']
(par défaut apps/static/uploads/avatars/, voir apps/config.py), nommé
"<id utilisateur>.<extension>" — un utilisateur ne peut donc avoir qu'un
seul fichier à la fois ; en changer l'extension (ex. .png -> .jpg) supprime
l'ancien fichier pour ne pas laisser de résidu orphelin. Utilisateur.photo
retient le chemin relatif à apps/static/ (ex. "uploads/avatars/3.jpg"),
directement utilisable par les templates via url_for('static', filename=...).

Comme pour l'e-mail d'alerte (apps/mailer.py) ou le connecteur Sage 100
(apps/sage_connector.py) : jamais d'exception qui remonterait jusqu'à
l'utilisateur sous une forme brute — toute erreur de validation est levée
comme ValueError au message déjà présentable (flash côté views.py).
"""

import os

from apps import app, db

EXTENSIONS_ACCEPTEES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
TAILLE_MAX_OCTETS = 2 * 1024 * 1024  # 2 Mo — une photo de profil, pas un document


def _extension(nom_fichier):
    _, ext = os.path.splitext(nom_fichier or "")
    return ext.lower()


def enregistrer_photo(utilisateur, fichier):
    """Valide et enregistre `fichier` (werkzeug FileStorage, tel que reçu
    via request.files) comme photo de profil de `utilisateur`. Remplace
    une photo précédente s'il y en avait une. Lève ValueError si `fichier`
    est absent, d'un type non accepté, ou trop volumineux."""
    if fichier is None or not fichier.filename:
        raise ValueError("Merci de choisir une image.")

    extension = _extension(fichier.filename)
    if extension not in EXTENSIONS_ACCEPTEES:
        raise ValueError(
            "Format d'image non pris en charge (formats acceptés : "
            + ", ".join(e.lstrip('.').upper() for e in EXTENSIONS_ACCEPTEES) + ")."
        )
    # Vérification complémentaire, sur la base du type déclaré par le
    # navigateur : ne bloque rien de plus que l'extension (un navigateur
    # ment aussi facilement qu'un nom de fichier), juste un second filet
    # pour un fichier renommé par erreur plutôt que par malveillance.
    if fichier.mimetype and not fichier.mimetype.startswith('image/'):
        raise ValueError("Le fichier envoyé ne semble pas être une image.")

    fichier.stream.seek(0, os.SEEK_END)
    taille = fichier.stream.tell()
    fichier.stream.seek(0)
    if taille == 0:
        raise ValueError("Le fichier envoyé est vide.")
    if taille > TAILLE_MAX_OCTETS:
        raise ValueError(
            f"Image trop volumineuse ({taille // 1024} Ko) : "
            f"{TAILLE_MAX_OCTETS // 1024} Ko maximum."
        )

    dossier = app.config['AVATARS_UPLOAD_DIR']
    os.makedirs(dossier, exist_ok=True)

    # Retire l'ancien fichier si son extension diffère de la nouvelle
    # (sinon on écrirait un fichier à côté de l'ancien au lieu de le
    # remplacer, ex. 3.png laissé après upload de 3.jpg). basename() par
    # sécurité : utilisateur.photo ne doit contenir aucun séparateur de
    # chemin, mais mieux vaut ne jamais faire confiance à une valeur qui
    # pourrait un jour venir d'ailleurs qu'une écriture de ce module.
    if utilisateur.photo:
        ancien_chemin = os.path.join(dossier, os.path.basename(utilisateur.photo))
        if os.path.isfile(ancien_chemin) and os.path.basename(ancien_chemin) != f"{utilisateur.id}{extension}":
            try:
                os.remove(ancien_chemin)
            except OSError:
                pass  # tant pis, pas bloquant pour l'utilisateur

    nom_fichier = f"{utilisateur.id}{extension}"
    fichier.save(os.path.join(dossier, nom_fichier))

    utilisateur.photo = f"uploads/avatars/{nom_fichier}"
    db.session.commit()
    return utilisateur.photo


def supprimer_photo(utilisateur):
    """Revient à l'avatar par défaut : supprime le fichier s'il existe et
    vide Utilisateur.photo. N'échoue jamais si le fichier est déjà absent
    (ex. supprimé manuellement du disque)."""
    if not utilisateur.photo:
        return
    dossier = app.config['AVATARS_UPLOAD_DIR']
    chemin = os.path.join(dossier, os.path.basename(utilisateur.photo))
    if os.path.isfile(chemin):
        try:
            os.remove(chemin)
        except OSError:
            pass
    utilisateur.photo = None
    db.session.commit()
