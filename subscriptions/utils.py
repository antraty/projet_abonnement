from django.db.models import Count, Sum
from django.utils import timezone
from .models import Client, Subscription
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

def get_advanced_stats():
    total_clients = Client.objects.count()
    total_abonnements = Subscription.objects.count()
    abonnements_actifs = Subscription.objects.filter(statut='actif').count()
    chiffre_affaires = round(Subscription.objects.aggregate(total=Sum('prix'))['total'] or 0, 2)
    
    # Répartition par type
    clients_par_type = Client.objects.values('type_client').annotate(total=Count('id'))
    repartition_clients = {
        'personnel': 0,
        'entreprise': 0
    }
    for item in clients_par_type:
        repartition_clients[item['type_client']] = item['total']
    
    # Répartition par statut d'abonnement
    abonnements_par_statut = Subscription.objects.values('statut').annotate(total=Count('id'))
    repartition_statuts = {
        'actif': 0,
        'inactif': 0,
        'suspendu': 0,
        'expire': 0
    }
    for item in abonnements_par_statut:
        repartition_statuts[item['statut']] = item['total']

    #info ce mois
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    abonnements_ce_mois = Subscription.objects.filter(date_creation__gte=debut_mois).count()
    clients_ce_mois = Client.objects.filter(date_creation__gte=debut_mois).count()
    
    return {
        'total_clients': total_clients,
        'total_abonnements': total_abonnements,
        'abonnements_actifs': abonnements_actifs,
        'chiffre_affaires': chiffre_affaires,
        'repartition_clients': repartition_clients,
        'repartition_statuts': repartition_statuts,
        'abonnements_ce_mois': abonnements_ce_mois,
        'clients_ce_mois': clients_ce_mois,
    }


def generate_clients_chart():
    """Générer un graphique camembert pour la répartition des clients"""
    stats = get_advanced_stats()
    
    # Créer le graphique
    plt.figure(figsize=(6, 4))
    labels = ['Personnel', 'Entreprise']
    sizes = [
        stats['repartition_clients']['personnel'],
        stats['repartition_clients']['entreprise']
        ]
    colors = ['#3498db', '#2ecc71']
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    plt.axis('equal')
    plt.title('Répartition des Clients par Type')
    
    # Convertir en image base64 visible en html
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close()

    return graphic


def generate_subscriptions_chart():
    """Générer un graphique camembert pour la répartition des abonnements"""
    stats = get_advanced_stats()
    
    plt.figure(figsize=(6, 4))
    labels = ['Actif', 'Inactif', 'Suspendu', 'Expiré']
    sizes = [
        stats['repartition_statuts']['actif'],
        stats['repartition_statuts']['inactif'],
        stats['repartition_statuts']['suspendu'],
        stats['repartition_statuts']['expire']
    ]
    colors = ['#2ecc71', '#e74c3c', '#f39c12', '#95a5a6']  
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    plt.axis('equal')
    plt.title('Répartition des Abonnements par Statut')
    
    # Convertir en image base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close()
    
    return graphic