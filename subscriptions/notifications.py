from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse  # Gardé si utilisé ailleurs, sinon à supprimer
from .utils import get_daily_stats
from datetime import timedelta
from .models import Subscription
import logging

logger = logging.getLogger(__name__)

def send_new_subscription_email(abonnement):
    client = abonnement.client

    subject = "Nouvel abonnement créé"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [client.email]

    html_content = render_to_string(
        "subscriptions/emails/new_subscription.html",
        {
            "client": client,
            "abonnement": abonnement,
        }
    )
    text_content = f"Un nouvel abonnement a été créé pour {client.nom}."

    try:
        send_mail(
            subject=subject,
            message=text_content,
            from_email=from_email,
            recipient_list=to,
            html_message=html_content 
        )
        logger.info("Email nouveau abonnement envoyé à %s (abonnement id=%s)", client.email, abonnement.id)
    except Exception:
        logger.exception("Erreur lors de l'envoi du mail de nouvel abonnement pour id=%s", abonnement.id)
    # Ne renvoie pas HttpResponse : fonction utilitaire

def send_daily_report(to_email=None):
    stats = get_daily_stats()
    context = {
        **stats
    }
    
    html_content = render_to_string("subscriptions/emails/daily_report.html", context)
    
    text_content = (
        f"Rapport du {stats['date']}:\n"
        f"Nouveaux clients: {stats['nouveaux_clients']}\n"
        f"Nouveaux abonnements: {stats['nouveaux_abonnements']}\n"
        f"Chiffre d'affaires: {stats['ca_du_jour']}Ar\n"
        f"Abonnements expirant demain: {stats['abonnements_expirant_demain']}\n"
    )
    
    if to_email is None:
        to_email = [settings.MANAGER_EMAIL]
    
    try:
        send_mail(
            subject=f"Rapport quotidien - {stats['date']}",
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=to_email,
            html_message=html_content,
        )
        logger.info("Rapport quotidien envoyé à %s", to_email)
    except Exception:
        logger.exception("Erreur lors de l'envoi du rapport quotidien à %s", to_email)


def send_upcoming_expiration_alerts(jours_avant_expiration=3):
    today = timezone.localdate()
    target_date = today + timedelta(days=jours_avant_expiration)
    
    abonnements_a_alertes = Subscription.objects.filter(date_fin=target_date)
    emails_envoyes = 0
    
    for abonnement in abonnements_a_alertes:
        client = abonnement.client
        jours_restants = (abonnement.date_fin - today).days
        
        subject = f"⚠️ Alerte : Votre abonnement {abonnement.nom_abonnement} expire bientôt"
        from_email = settings.DEFAULT_FROM_EMAIL
        to = [client.email]

        context = {
            'client': client,
            'abonnement': abonnement,
            'jours_restants': jours_restants,
        }

        html_content = render_to_string("subscriptions/emails/expiry_notification.html", context)
        text_content = (
            f"Alerte : L'abonnement {abonnement.nom_abonnement} pour {client.nom} expire dans {jours_restants} jours.\n"
            f"Client: {client.nom}\n"
            f"Email: {client.email}\n"
            f"Téléphone: {client.telephone or 'Non renseigné'}\n"
            f"Date d'expiration: {abonnement.date_fin}\n"
            f"Prix: {abonnement.prix}Ar\n"
            f"{'Description: ' + abonnement.description if abonnement.description else ''}"
        )

        try:
            send_mail(
                subject=subject,
                message=text_content,
                from_email=from_email,
                recipient_list=to,
                html_message=html_content
            )
            emails_envoyes += 1
            logger.info("Alerte expiration envoyée à %s pour abonnement id=%s", client.email, abonnement.id)
        except Exception:
            logger.exception("Erreur lors de l'envoi de l'alerte d'expiration à %s (abonnement id=%s)", client.email, abonnement.id)

    logger.info("%s alertes d'expiration envoyées.", emails_envoyes)
    return emails_envoyes