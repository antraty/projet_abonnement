from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from datetime import date
from django.http import HttpResponse
from .utils import get_daily_stats

def send_new_subscription_email(abonnement):
    client = abonnement.client

    subject = " Nouvel abonnement créé"
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

    send_mail(
    subject=subject,
    message=text_content,
    from_email=from_email,
    recipient_list=to,
    html_message=html_content 
    )
    return HttpResponse('Message sent!')


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
        f"Chiffre d'affaires: {stats['ca_du_jour']}€\n"
        f"Abonnements expirant demain: {stats['abonnements_expirant_demain']}\n"
    )
    
    if to_email is None:
        to_email = [settings.MANAGER_EMAIL]
    
    send_mail(
        subject=f"Rapport quotidien - {stats['date']}",
        message=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=to_email,
        html_message=html_content,
    )
    return HttpResponse('Message sent!')

