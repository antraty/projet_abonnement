from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from .models import Subscription

def send_subscription_expiry_notifications():
    """Envoyer des notifications pour les abonnements expirant bientôt"""
    # Abonnements expirant dans 3 jours
    date_limite = timezone.now().date() + timedelta(days=3)
    abonnements_expirant = Subscription.objects.filter(
        date_fin__lte=date_limite,
        statut='actif'
    )
    
    notifications_envoyees = 0
    
    for abonnement in abonnements_expirant:
        subject = f"🔔 Abonnement Expirant: {abonnement.nom_abonnement}"
        
        context = {
            'abonnement': abonnement,
            'jours_restants': (abonnement.date_fin - timezone.now().date()).days,
            'client': abonnement.client,
        }
        
        message_html = render_to_string('subscriptions/emails/expiry_notification.html', context)
        message_text = f"""
        Bonjour,
        
        L'abonnement "{abonnement.nom_abonnement}" pour le client {abonnement.client.nom} 
        expire le {abonnement.date_fin.strftime('%d/%m/%Y')} (dans {context['jours_restants']} jours).
        
        Client: {abonnement.client.nom}
        Email: {abonnement.client.email}
        Téléphone: {abonnement.client.telephone or 'Non renseigné'}
        Prix: {abonnement.prix}€
        
        Cordialement,
        Votre système de gestion d'abonnements
        """
        
        try:
            # Envoyer à l'administrateur (vous pouvez ajouter d'autres destinataires)
            send_mail(
                subject=subject,
                message=message_text,
                html_message=message_html,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],  # Envoyer à vous-même
                fail_silently=False,
            )
            notifications_envoyees += 1
            print(f"Notification envoyée pour {abonnement.nom_abonnement}")
            
        except Exception as e:
            print(f"Erreur envoi email pour {abonnement.nom_abonnement}: {e}")
    
    return notifications_envoyees

def send_new_subscription_notification(abonnement):
    """Envoyer une notification pour un nouvel abonnement"""
    subject = f"🎉 Nouvel Abonnement Créé: {abonnement.nom_abonnement}"
    
    context = {
        'abonnement': abonnement,
        'client': abonnement.client,
    }
    
    message_html = render_to_string('subscriptions/emails/new_subscription.html', context)
    message_text = f"""
    Nouvel abonnement créé !
    
    Détails:
    - Abonnement: {abonnement.nom_abonnement}
    - Client: {abonnement.client.nom}
    - Email: {abonnement.client.email}
    - Prix: {abonnement.prix}€
    - Durée: {abonnement.duree_mois} mois
    - Période: {abonnement.date_debut.strftime('%d/%m/%Y')} au {abonnement.date_fin.strftime('%d/%m/%Y')}
    
    Cordialement,
    Votre système de gestion d'abonnements
    """
    
    try:
        send_mail(
            subject=subject,
            message=message_text,
            html_message=message_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        return True
    except Exception as e:
        print(f"Erreur notification nouvel abonnement: {e}")
        return False

def send_daily_report():
    """Envoyer un rapport quotidien"""
    from django.db.models import Count, Sum
    
    # Statistiques du jour
    aujourd_hui = timezone.now().date()
    nouveaux_clients = Subscription.objects.filter(date_creation__date=aujourd_hui).count()
    nouveaux_abonnements = Subscription.objects.filter(date_creation__date=aujourd_hui).count()
    ca_du_jour = Subscription.objects.filter(date_creation__date=aujourd_hui).aggregate(total=Sum('prix'))['total'] or 0
    
    # Abonnements expirant demain
    demain = aujourd_hui + timedelta(days=1)
    abonnements_expirant_demain = Subscription.objects.filter(date_fin=demain, statut='actif').count()
    
    subject = f"📊 Rapport Quotidien - {aujourd_hui.strftime('%d/%m/%Y')}"
    
    context = {
        'date': aujourd_hui,
        'nouveaux_clients': nouveaux_clients,
        'nouveaux_abonnements': nouveaux_abonnements,
        'ca_du_jour': ca_du_jour,
        'abonnements_expirant_demain': abonnements_expirant_demain,
    }
    
    message_html = render_to_string('subscriptions/emails/daily_report.html', context)
    message_text = f"""
    Rapport Quotidien - {aujourd_hui.strftime('%d/%m/%Y')}
    
    📈 Aujourd'hui:
    - Nouveaux clients: {nouveaux_clients}
    - Nouveaux abonnements: {nouveaux_abonnements}
    - Chiffre d'affaires: {ca_du_jour}€
    
    ⚠️ Alertes:
    - Abonnements expirant demain: {abonnements_expirant_demain}
    
    Cordialement,
    Votre système de gestion d'abonnements
    """
    
    try:
        send_mail(
            subject=subject,
            message=message_text,
            html_message=message_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
        return True
    except Exception as e:
        print(f"Erreur rapport quotidien: {e}")
        return False