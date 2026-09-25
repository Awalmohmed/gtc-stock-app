# -*- encoding: utf-8 -*-
"""
GTC Stock — Import d'articles depuis un fichier CSV ou Excel (.xlsx).

Chaque ligne du fichier décrit un article du catalogue : nom, référence,
seuil d'alerte, et optionnellement son fournisseur habituel. Colonnes
attendues (en-têtes, insensibles à la casse) : nom, reference, seuil,
fournisseur (facultative).

Règle importante, volontairement stricte : la quantité en stock
(Article.quantite) n'est JAMAIS modifiée par un import, ni pour un
article existant, ni pour un nouvel article (créé avec quantite=0).
Le stock ne doit changer que via de vrais mouvements d'entrée/sortie
(voir apps/gtc_data.py, add_entree/add_sortie) — un import ne fait que
mettre à jour les informations de catalogue.

Un import cible TOUJOURS un seul magasin (`magasin_id`, voir
importer_fichier) — la référence n'étant unique que PAR MAGASIN (voir
apps/models.py, Article.__table_args__), un import ne doit jamais
toucher un article d'un autre magasin sous prétexte qu'il porte la même
référence :
- Référence déjà connue DANS CE MAGASIN -> met à jour nom, seuil,
  fournisseur habituel (et le statut Alerte/OK si l'article n'est pas
  "Dormant").
- Référence inconnue dans ce magasin (qu'elle existe ou non ailleurs)
  -> crée l'article dans ce magasin, quantite=0.
- Fournisseur mentionné mais introuvable dans la table Fournisseur ->
  ligne rejetée (pas de création silencieuse d'un fournisseur).
- Référence en double dans le même fichier -> seule la première
  occurrence est traitée, les suivantes sont rejetées.

Aucune ligne valide n'est perdue à cause d'une ligne invalide ailleurs
dans le fichier : chaque ligne est validée indépendamment, et le
rapport final liste toutes les erreurs rencontrées.
"""

import csv
import io

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from apps import db
from apps.models import Article, Fournisseur

EXTENSIONS_ACCEPTEES = ('.csv', '.xlsx')
COLONNES_ATTENDUES = ('nom', 'reference', 'seuil')  # 'fournisseur' est facultative


class FichierInvalide(Exception):
    """Erreur de niveau fichier (extension, format illisible, en-têtes
    manquantes...) — empêche tout traitement, contrairement aux erreurs
    de ligne qui n'affectent que la ligne concernée."""


def _decoder_csv(contenu_brut):
    """Décode le contenu d'un CSV en gérant les encodages courants côté
    utilisateurs francophones (Excel exporte souvent en cp1252/latin-1,
    parfois avec un BOM UTF-8)."""
    for encodage in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return contenu_brut.decode(encodage)
        except UnicodeDecodeError:
            continue
    raise FichierInvalide("Impossible de lire l'encodage du fichier CSV.")


def _lignes_depuis_csv(contenu_brut):
    texte = _decoder_csv(contenu_brut)
    try:
        dialecte = csv.Sniffer().sniff(texte.splitlines()[0], delimiters=',;\t')
    except (csv.Error, IndexError):
        dialecte = csv.excel  # séparateur "," par défaut
    lecteur = csv.DictReader(io.StringIO(texte), dialect=dialecte)
    if not lecteur.fieldnames:
        raise FichierInvalide("Le fichier CSV est vide.")
    return lecteur.fieldnames, list(lecteur)


def _lignes_depuis_xlsx(contenu_brut):
    try:
        classeur = load_workbook(io.BytesIO(contenu_brut), read_only=True, data_only=True)
    except (InvalidFileException, OSError, KeyError):
        raise FichierInvalide("Le fichier .xlsx est illisible ou corrompu.")
    feuille = classeur.active
    lignes_brutes = feuille.iter_rows(values_only=True)
    try:
        entetes = [str(c).strip() if c is not None else '' for c in next(lignes_brutes)]
    except StopIteration:
        raise FichierInvalide("Le fichier Excel est vide.")

    lignes = []
    for valeurs in lignes_brutes:
        if all(v is None for v in valeurs):
            continue  # ligne entièrement vide (fin de tableau, etc.)
        lignes.append({
            entetes[i]: ('' if v is None else str(v).strip())
            for i, v in enumerate(valeurs) if i < len(entetes)
        })
    return entetes, lignes


def _valider_entetes(entetes):
    normalisees = {e.strip().lower() for e in entetes}
    manquantes = [c for c in COLONNES_ATTENDUES if c not in normalisees]
    if manquantes:
        raise FichierInvalide(
            "Colonne(s) manquante(s) dans le fichier : " + ", ".join(manquantes) +
            ". Colonnes attendues : nom, reference, seuil, fournisseur (facultative)."
        )


def _valeur(ligne, cle):
    """Lit une valeur de ligne en tolérant la casse des en-têtes
    (ex. "Référence" ou "reference" ou "REFERENCE")."""
    for k, v in ligne.items():
        if k and k.strip().lower() == cle:
            return (v or '').strip()
    return ''


def _valider_ligne(ligne, references_vues, fournisseurs_par_nom):
    """Valide une ligne. Retourne (donnees_propres, erreur). Une seule des
    deux est non-None."""
    nom = _valeur(ligne, 'nom')
    reference = _valeur(ligne, 'reference')
    seuil_brut = _valeur(ligne, 'seuil')
    fournisseur_nom = _valeur(ligne, 'fournisseur')

    if not nom:
        return None, "Nom manquant."
    if len(nom) > 150:
        return None, "Nom trop long (150 caractères maximum)."
    if not reference:
        return None, "Référence manquante."
    if len(reference) > 50:
        return None, "Référence trop longue (50 caractères maximum)."
    if reference in references_vues:
        return None, f"Référence « {reference} » en double dans le fichier."

    try:
        seuil = int(seuil_brut)
        if seuil < 0:
            raise ValueError
    except ValueError:
        return None, f"Seuil invalide ({seuil_brut!r}) : un nombre entier positif est attendu."

    fournisseur_id = None
    if fournisseur_nom:
        fournisseur = fournisseurs_par_nom.get(fournisseur_nom.lower())
        if not fournisseur:
            return None, (
                f"Fournisseur « {fournisseur_nom} » inconnu. "
                "Ajoutez-le d'abord depuis la page Fournisseurs."
            )
        fournisseur_id = fournisseur.id

    references_vues.add(reference)
    return {"nom": nom, "reference": reference, "seuil": seuil, "fournisseur_id": fournisseur_id}, None


def importer_fichier(nom_fichier, contenu_brut, magasin_id):
    """Importe un fichier CSV ou Excel d'articles dans le magasin
    `magasin_id` : toutes les créations/mises à jour sont scopées à ce
    magasin (voir docstring du module) — un article portant la même
    référence dans un AUTRE magasin n'est jamais touché.

    Retourne un dict : {"crees": int, "maj": int, "erreurs": [(ligne, message), ...]}.
    Lève FichierInvalide si le fichier lui-même est inexploitable
    (mauvaise extension, illisible, en-têtes manquantes)."""
    extension = ('.' + nom_fichier.rsplit('.', 1)[-1].lower()) if '.' in nom_fichier else ''
    if extension not in EXTENSIONS_ACCEPTEES:
        raise FichierInvalide("Format non reconnu : seuls les fichiers .csv et .xlsx sont acceptés.")

    if extension == '.csv':
        entetes, lignes = _lignes_depuis_csv(contenu_brut)
    else:
        entetes, lignes = _lignes_depuis_xlsx(contenu_brut)
    _valider_entetes(entetes)

    fournisseurs_par_nom = {f.nom.lower(): f for f in Fournisseur.query.all()}

    references_vues = set()
    lignes_valides = []
    erreurs = []
    for numero, ligne in enumerate(lignes, start=2):  # ligne 1 = en-têtes
        donnees, erreur = _valider_ligne(ligne, references_vues, fournisseurs_par_nom)
        if erreur:
            erreurs.append((numero, erreur))
        else:
            lignes_valides.append(donnees)

    crees = 0
    maj = 0
    references_du_fichier = [d["reference"] for d in lignes_valides]
    articles_existants = {
        a.reference: a
        for a in Article.query.filter(
            Article.reference.in_(references_du_fichier), Article.magasin_id == magasin_id,
        )
    } if references_du_fichier else {}

    for donnees in lignes_valides:
        article = articles_existants.get(donnees["reference"])
        if article:
            # Mise à jour du catalogue uniquement — quantite n'est JAMAIS
            # touchée par un import (voir docstring du module).
            article.nom = donnees["nom"]
            article.seuil = donnees["seuil"]
            article.fournisseur_id = donnees["fournisseur_id"]
            if article.statut != "Dormant":
                article.statut = "Alerte" if article.quantite <= article.seuil else "OK"
            maj += 1
        else:
            # Un article tout juste importé démarre à quantite=0 (voir
            # docstring du module) : avec un seuil >= 0, il est donc
            # toujours en "Alerte" jusqu'à la première vraie entrée de
            # stock — c'est le comportement attendu, pas un cas particulier.
            article = Article(
                nom=donnees["nom"], reference=donnees["reference"], seuil=donnees["seuil"],
                fournisseur_id=donnees["fournisseur_id"], quantite=0,
                statut="Alerte", dernier_mouvement="—", magasin_id=magasin_id,
            )
            db.session.add(article)
            crees += 1

    db.session.commit()
    return {"crees": crees, "maj": maj, "erreurs": erreurs}


def modele_csv():
    """Contenu du fichier modèle proposé au téléchargement (BOM UTF-8
    inclus pour qu'Excel affiche correctement les accents)."""
    return (
        "﻿"
        "nom,reference,seuil,fournisseur\n"
        "Riz parfumé 25 kg,REF-0001,10,Nom du fournisseur (déjà créé)\n"
        "Nouvel article exemple,REF-9001,5,\n"
    )
