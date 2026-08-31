# -*- encoding: utf-8 -*-
"""
GTC Stock — Envoi des e-mails d'alerte de stock.

Quand une sortie fait passer un article au niveau de son seuil
(transition « OK »/« Dormant » -> « Alerte », voir apps/gtc_data.py,
add_sortie), un e-mail part vers l'adresse d'alerte du magasin de
l'article (Magasin.email_alertes), ou à défaut vers ALERTE_EMAIL_DEFAUT.

Si aucun serveur SMTP n'est configuré (SMTP_HOST vide) ou si aucune
adresse de destination n'est connue, l'alerte est seulement écrite dans
les logs applicatifs : l'enregistrement de la sortie de stock ne doit
jamais échouer à cause de l'e-mail. Même principe de dégradation que le
connecteur Sage 100 (apps/sage_connector.py).
"""

import smtplib
from email.message import EmailMessage

from apps import app


def _destinataire(article):
    """Adresse à prévenir pour cet article : celle de son magasin, sinon
    l'adresse de repli globale, sinon None."""
    if article.magasin and article.magasin.email_alertes:
        return article.magasin.email_alertes
    return app.config.get('ALERTE_EMAIL_DEFAUT') or None


def _corps(article):
    magasin = article.magasin.nom if article.magasin else "(non rattaché)"
    return (
        "Alerte de stock — GTC Stock\n\n"
        f"Article : {article.nom} ({article.reference})\n"
        f"Magasin : {magasin}\n"
        f"Quantité actuelle : {article.quantite}\n"
        f"Seuil d'alerte : {article.seuil}\n\n"
        "Cet article vient d'atteindre son seuil d'alerte à la suite "
        "d'une sortie de stock. Merci de prévoir un réapprovisionnement.\n"
    )


def envoyer_alerte_seuil(article):
    """Envoie (ou, à défaut, journalise) l'e-mail d'alerte pour `article`
    qui vient d'atteindre son seuil. N'élève jamais d'exception : toute
    erreur d'envoi est journalisée et la fonction renvoie False."""
    sujet = f"[GTC Stock] Seuil d'alerte atteint — {article.nom}"
    corps = _corps(article)
    destinataire = _destinataire(article)
    hote = app.config.get('SMTP_HOST')

    if not hote or not destinataire:
        raison = "SMTP non configuré" if not hote else "aucune adresse d'alerte pour ce magasin"
        app.logger.warning(
            "Alerte de seuil non envoyée par e-mail (%s).\nÀ : %s\nSujet : %s\n%s",
            raison, destinataire or "—", sujet, corps,
        )
        return False

    message = EmailMessage()
    message['From'] = app.config.get('ALERTE_EMAIL_EXPEDITEUR')
    message['To'] = destinataire
    message['Subject'] = sujet
    message.set_content(corps)

    try:
        with smtplib.SMTP(hote, app.config.get('SMTP_PORT', 587), timeout=10) as smtp:
            if app.config.get('SMTP_USE_TLS', True):
                smtp.starttls()
            utilisateur = app.config.get('SMTP_USER')
            if utilisateur:
                smtp.login(utilisateur, app.config.get('SMTP_PASSWORD') or '')
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as e:
        app.logger.error("Échec de l'envoi de l'e-mail d'alerte à %s : %s", destinataire, e)
        return False

    app.logger.info("E-mail d'alerte de seuil envoyé à %s pour « %s ».",
                    destinataire, article.reference)
    return True
