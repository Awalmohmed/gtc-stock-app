# -*- encoding: utf-8 -*-
"""
GTC Stock — Export PDF et Excel de la fiche de stock et du rapprochement.

Deux formats, mêmes données que ce que la page affiche à l'écran : PDF
pour imprimer/partager en lecture seule, Excel pour retravailler les
chiffres (trier, filtrer, recalculer) dans un tableur.
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

_STYLES = getSampleStyleSheet()


def _horodatage():
    return datetime.now().strftime("%d/%m/%Y à %H:%M")


# ---------------------------------------------------------------------
# PDF — mise en page commune (titre + sous-titre + un ou plusieurs tableaux)
# ---------------------------------------------------------------------
def _construire_pdf(titre, sous_titre, tableaux):
    """tableaux : liste de (legende_ou_None, liste_de_lignes[, styles_sup]) ;
    la première ligne de chaque liste est traitée comme l'en-tête.
    styles_sup (optionnel) : commandes TableStyle ajoutées après le style
    commun, pour colorer certaines cellules au cas par cas."""
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(
        tampon, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    elements = [
        Paragraph(titre, _STYLES["Title"]),
        Paragraph(sous_titre, _STYLES["Normal"]),
        Spacer(1, 0.5 * cm),
    ]
    for tableau in tableaux:
        legende, lignes = tableau[0], tableau[1]
        styles_sup = tableau[2] if len(tableau) > 2 else []
        if legende:
            elements.append(Paragraph(legende, _STYLES["Heading3"]))
        table = Table(lignes, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2559")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5dd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8fa")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ] + list(styles_sup)))
        elements.append(table)
        elements.append(Spacer(1, 0.5 * cm))
    doc.build(elements)
    return tampon.getvalue()


# ---------------------------------------------------------------------
# Excel — feuille unique, en-tête en gras
# ---------------------------------------------------------------------
def _construire_excel(nom_feuille, entetes, lignes):
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = nom_feuille
    feuille.append(entetes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    for ligne in lignes:
        feuille.append(ligne)
    for i, entete in enumerate(entetes, start=1):
        feuille.column_dimensions[get_column_letter(i)].width = max(14, len(str(entete)) + 4)

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


# ---------------------------------------------------------------------
# Fiche de stock
# ---------------------------------------------------------------------
def fiche_stock_pdf(article, historique):
    infos = [
        ["Référence", article.reference],
        ["Quantité actuelle", str(article.quantite)],
        ["Seuil d'alerte", str(article.seuil)],
        ["Statut", article.statut],
        ["Dernier mouvement", article.dernier_mouvement or "—"],
    ]
    lignes_historique = [["Date", "Type", "Référence", "Quantité", "Solde après mouvement"]]
    lignes_historique += [
        [h["date"], h["type"], h["reference"], h["quantite"], str(h["solde"])]
        for h in historique
    ] or [["Aucun mouvement enregistré.", "", "", "", ""]]

    return _construire_pdf(
        f"Fiche de stock — {article.nom}",
        f"Généré le {_horodatage()} — GTC Stock",
        [(None, infos), ("Historique des mouvements", lignes_historique)],
    )


def fiche_stock_excel(article, historique):
    classeur = Workbook()

    resume = classeur.active
    resume.title = "Article"
    resume.append(["Champ", "Valeur"])
    for cellule in resume[1]:
        cellule.font = Font(bold=True)
    for champ, valeur in [
        ("Nom", article.nom), ("Référence", article.reference),
        ("Quantité actuelle", article.quantite), ("Seuil d'alerte", article.seuil),
        ("Statut", article.statut), ("Dernier mouvement", article.dernier_mouvement or "—"),
    ]:
        resume.append([champ, valeur])
    resume.column_dimensions["A"].width = 20
    resume.column_dimensions["B"].width = 30

    historique_feuille = classeur.create_sheet("Historique")
    historique_feuille.append(["Date", "Type", "Référence", "Quantité", "Solde après mouvement"])
    for cellule in historique_feuille[1]:
        cellule.font = Font(bold=True)
    for h in historique:
        historique_feuille.append([h["date"], h["type"], h["reference"], h["quantite_brute"], h["solde"]])
    for i in range(1, 6):
        historique_feuille.column_dimensions[get_column_letter(i)].width = 18

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


# ---------------------------------------------------------------------
# Rapprochement Sage 100
# ---------------------------------------------------------------------
def rapprochement_pdf(lignes, sage_connecte):
    source = "Sage 100 (connexion en direct)" if sage_connecte else "données de démonstration (Sage 100 non connecté)"
    entetes = ["Article", "Quantité application", "Quantité Sage 100", "Écart", "Statut", "Conformité"]
    tableau = [entetes]
    col_conformite = len(entetes) - 1
    # Couleurs choisies pour rester distinctes en niveaux de gris à l'impression,
    # mais le texte « Conforme »/« Écart » suffit seul si la couleur est perdue.
    vert_fond, vert_texte = colors.HexColor("#d4edda"), colors.HexColor("#0f7b34")
    rouge_fond, rouge_texte = colors.HexColor("#f8d7da"), colors.HexColor("#b42318")
    styles_conformite = []
    for l in lignes:
        conforme = l["conforme"]
        tableau.append([
            l["article"], str(l["qte_app"]), str(l["qte_sage"]), str(l["ecart"]),
            "Conforme" if conforme else "Écart détecté",
            "Conforme" if conforme else "Écart",
        ])
        rang = len(tableau) - 1
        cellule = (col_conformite, rang)
        styles_conformite += [
            ("BACKGROUND", cellule, cellule, vert_fond if conforme else rouge_fond),
            ("TEXTCOLOR", cellule, cellule, vert_texte if conforme else rouge_texte),
            ("FONTNAME", cellule, cellule, "Helvetica-Bold"),
            ("ALIGN", cellule, cellule, "CENTER"),
        ]
    if not lignes:
        tableau.append(["Aucune donnée de rapprochement.", "", "", "", "", ""])

    return _construire_pdf(
        "Rapprochement comptable — GTC Stock",
        f"Généré le {_horodatage()} — Source : {source}",
        [(None, tableau, styles_conformite)],
    )


def rapprochement_excel(lignes, sage_connecte):
    entetes = ["Article", "Quantité application", "Quantité Sage 100", "Écart", "Conforme"]
    donnees = [
        [l["article"], l["qte_app"], l["qte_sage"], l["ecart"], "Oui" if l["conforme"] else "Non"]
        for l in lignes
    ]
    return _construire_excel("Rapprochement", entetes, donnees)
