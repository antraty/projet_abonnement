from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Client, Subscription, Renewal
from django.utils import timezone
from datetime import timedelta
from .forms import ClientForm, SubscriptionForm
from django.shortcuts import render, redirect, get_object_or_404
import csv
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from io import BytesIO
from .utils import get_advanced_stats, generate_clients_chart, generate_subscriptions_chart
from .notifications import send_new_subscription_notification


def dashboard(request):
    """Tableau de bord principal avec graphiques"""
    # Statistiques de base
    total_clients = Client.objects.count()
    total_abonnements = Subscription.objects.count()
    abonnements_actifs = Subscription.objects.filter(statut='actif').count()
    
    # Abonnements expirant bientôt (dans les 7 jours)
    date_limite = timezone.now().date() + timedelta(days=7)
    abonnements_expirant = Subscription.objects.filter(
        date_fin__lte=date_limite,
        statut='actif'
    )
    
    # Derniers abonnements créés
    derniers_abonnements = Subscription.objects.all().order_by('-date_creation')[:5]
    
    # Statistiques avancées
    advanced_stats = get_advanced_stats()
    
    # Générer les graphiques
    clients_chart = generate_clients_chart()
    subscriptions_chart = generate_subscriptions_chart()
    
    context = {
        'total_clients': total_clients,
        'total_abonnements': total_abonnements,
        'abonnements_actifs': abonnements_actifs,
        'abonnements_expirant': abonnements_expirant,
        'derniers_abonnements': derniers_abonnements,
        'advanced_stats': advanced_stats,
        'clients_chart': clients_chart,
        'subscriptions_chart': subscriptions_chart,
    }
    
    return render(request, 'subscriptions/dashboard.html', context)

def client_list(request):
    """Liste de tous les clients avec recherche et filtres"""
    clients = Client.objects.all().order_by('nom')
    
    # Recherche
    query = request.GET.get('q')
    if query:
        clients = clients.filter(
            Q(nom__icontains=query) |
            Q(email__icontains=query) |
            Q(nom_entreprise__icontains=query) |
            Q(telephone__icontains=query)
        )
    
    # Filtre par type de client
    type_filter = request.GET.get('type')
    if type_filter:
        clients = clients.filter(type_client=type_filter)
    
    context = {
        'clients': clients,
        'query': query or '',
        'type_filter': type_filter or '',
    }
    return render(request, 'subscriptions/client_list.html', context)

def subscription_list(request):
    """Liste de tous les abonnements avec recherche et filtres"""
    abonnements = Subscription.objects.all().order_by('-date_creation')
    
    # Recherche
    query = request.GET.get('q')
    if query:
        abonnements = abonnements.filter(
            Q(nom_abonnement__icontains=query) |
            Q(client__nom__icontains=query) |
            Q(client__nom_entreprise__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Filtre par statut
    statut_filter = request.GET.get('statut')
    if statut_filter:
        abonnements = abonnements.filter(statut=statut_filter)
    
    context = {
        'abonnements': abonnements,
        'query': query or '',
        'statut_filter': statut_filter or '',
    }
    return render(request, 'subscriptions/subscription_list.html', context)

def client_create(request):
    """Créer un nouveau client"""
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client créé avec succès !')
            return redirect('subscriptions:client_list')
    else:
        form = ClientForm()
    
    return render(request, 'subscriptions/client_form.html', {'form': form})

def subscription_create(request):
    """Créer un nouvel abonnement"""
    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            abonnement = form.save()
            messages.success(request, 'Abonnement créé avec succès !')
            
            # Envoyer une notification email
            send_new_subscription_notification(abonnement)
            
            return redirect('subscriptions:subscription_list')
    else:
        form = SubscriptionForm()
    
    return render(request, 'subscriptions/subscription_form.html', {'form': form})

def client_edit(request, pk):
    """Modifier un client existant"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client modifié avec succès !')
            return redirect('subscriptions:client_list')
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'subscriptions/client_form.html', {
        'form': form,
        'client': client,
        'editing': True
    })

def client_delete(request, pk):
    """Supprimer un client"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        client.delete()
        messages.success(request, 'Client supprimé avec succès !')
        return redirect('subscriptions:client_list')
    
    return render(request, 'subscriptions/client_confirm_delete.html', {'client': client})

def subscription_edit(request, pk):
    """Modifier un abonnement existant"""
    abonnement = get_object_or_404(Subscription, pk=pk)
    
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=abonnement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Abonnement modifié avec succès !')
            return redirect('subscriptions:subscription_list')
    else:
        form = SubscriptionForm(instance=abonnement)
    
    return render(request, 'subscriptions/subscription_form.html', {
        'form': form,
        'abonnement': abonnement,
        'editing': True
    })

def subscription_delete(request, pk):
    """Supprimer un abonnement"""
    abonnement = get_object_or_404(Subscription, pk=pk)
    
    if request.method == 'POST':
        abonnement.delete()
        messages.success(request, 'Abonnement supprimé avec succès !')
        return redirect('subscriptions:subscription_list')
    
    return render(request, 'subscriptions/subscription_confirm_delete.html', {'abonnement': abonnement})


def export_clients_csv(request):
    """Exporter la liste des clients en CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="clients.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Nom', 'Email', 'Téléphone', 'Type', 'Entreprise', 'Adresse', 'Date Création'])
    
    clients = Client.objects.all().order_by('nom')
    for client in clients:
        writer.writerow([
            client.nom,
            client.email,
            client.telephone or '',
            client.get_type_client_display(),
            client.nom_entreprise or '',
            client.adresse or '',
            client.date_creation.strftime('%d/%m/%Y')
        ])
    
    return response

def export_subscriptions_csv(request):
    """Exporter la liste des abonnements en CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="abonnements.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Nom Abonnement', 'Client', 'Email Client', 'Prix (€)', 'Date Début', 'Date Fin', 'Durée (mois)', 'Statut', 'Description'])
    
    abonnements = Subscription.objects.all().order_by('-date_creation')
    for abonnement in abonnements:
        writer.writerow([
            abonnement.nom_abonnement,
            abonnement.client.nom,
            abonnement.client.email,
            str(abonnement.prix),
            abonnement.date_debut.strftime('%d/%m/%Y'),
            abonnement.date_fin.strftime('%d/%m/%Y'),
            str(abonnement.duree_mois),
            abonnement.get_statut_display(),
            abonnement.description or ''
        ])
    
    return response

def export_clients_pdf(request):
    """Exporter la liste des clients en PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    elements = []
    
    # Titre
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        textColor=colors.HexColor('#2c3e50')
    )
    
    elements.append(Paragraph("Liste des Clients - Gestion d'Abonnements", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Données
    clients = Client.objects.all().order_by('nom')
    
    if clients:
        # En-têtes du tableau
        data = [['Nom', 'Email', 'Téléphone', 'Type', 'Entreprise', 'Date Création']]
        
        for client in clients:
            data.append([
                client.nom,
                client.email,
                client.telephone or '-',
                client.get_type_client_display(),
                client.nom_entreprise or '-',
                client.date_creation.strftime('%d/%m/%Y')
            ])
        
        # Création du tableau
        table = Table(data, colWidths=[1.5*inch, 1.8*inch, 1.2*inch, 1.0*inch, 1.5*inch, 1.0*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(f"Total: {clients.count()} client(s)", styles['Normal']))
    else:
        elements.append(Paragraph("Aucun client à exporter.", styles['Normal']))
    
    # Génération du PDF
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="clients.pdf"'
    
    return response

def export_subscriptions_pdf(request):
    """Exporter la liste des abonnements en PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    elements = []
    
    # Titre
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        textColor=colors.HexColor('#2c3e50')
    )
    
    elements.append(Paragraph("Liste des Abonnements - Gestion d'Abonnements", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Statistiques
    stats_style = ParagraphStyle(
        'StatsStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666')
    )
    
    total_abonnements = Subscription.objects.count()
    abonnements_actifs = Subscription.objects.filter(statut='actif').count()
    
    elements.append(Paragraph(f"Statistiques: {total_abonnements} abonnement(s) total, {abonnements_actifs} actif(s)", stats_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Données
    abonnements = Subscription.objects.all().order_by('-date_creation')
    
    if abonnements:
        # En-têtes du tableau
        data = [['Abonnement', 'Client', 'Prix (€)', 'Début', 'Fin', 'Statut']]
        
        for abonnement in abonnements:
            data.append([
                abonnement.nom_abonnement,
                abonnement.client.nom,
                str(abonnement.prix),
                abonnement.date_debut.strftime('%d/%m/%Y'),
                abonnement.date_fin.strftime('%d/%m/%Y'),
                abonnement.get_statut_display()
            ])
        
        # Création du tableau
        table = Table(data, colWidths=[1.8*inch, 1.5*inch, 0.8*inch, 0.9*inch, 0.9*inch, 1.0*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),  # Aligner les prix à droite
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(f"Total: {abonnements.count()} abonnement(s)", styles['Normal']))
    else:
        elements.append(Paragraph("Aucun abonnement à exporter.", styles['Normal']))
    
    # Génération du PDF
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="abonnements.pdf"'
    
    return response