from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from num2words import num2words
import json

from subscriptions.models import Subscription, Client
from .models import Facture, LigneFacture

def convertir_ariary_en_lettres(montant_ariary):
    """Convertit un montant en Ariary en lettres français"""
    try:
        if isinstance(montant_ariary, str):
            montant_ariary = float(montant_ariary.replace(' Ar', '').replace(' ', ''))
        
        num = float(montant_ariary)
        ariary = int(num)
        
        if ariary == 0:
            texte_ariary = "zéro"
        elif ariary == 1:
            texte_ariary = "un"
        else:
            texte_ariary = num2words(ariary, lang='fr')
        
        pluriel_ariary = "ariary" if ariary == 1 else "ariary"
        
        return f"{texte_ariary} {pluriel_ariary}"
            
    except Exception as e:
        print(f"Erreur conversion lettres: {e}")
        return f"{montant_ariary} ariary"

@method_decorator(csrf_exempt, name='dispatch')
class GenererFactureAbonnementAPI(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            abonnement_id = data.get('abonnement_id')
            
            abonnement = get_object_or_404(Subscription, pk=abonnement_id)
            
            prix_ariary = abonnement.prix
            
            mois_courant = timezone.now().month
            annee_courante = timezone.now().year
            
            facture_existante = Facture.objects.filter(
                abonnement=abonnement,
                date_creation__month=mois_courant,
                date_creation__year=annee_courante
            ).first()
            
            if facture_existante:
                return JsonResponse({
                    'success': True,
                    'facture_id': facture_existante.id,
                    'message': 'Facture déjà existante pour ce mois',
                    'existant': True
                })
            
            facture = Facture.objects.create(
                client=abonnement.client,
                abonnement=abonnement,
                date_echeance=timezone.now().date() + timezone.timedelta(days=30),
                statut='impayee'
            )
            
            LigneFacture.objects.create(
                facture=facture,
                description=f"Abonnement {abonnement.nom_abonnement} - {abonnement.duree_mois} mois (Du {abonnement.date_debut.strftime('%d/%m/%Y')} au {abonnement.date_fin.strftime('%d/%m/%Y')})",
                quantite=1,
                prix_unitaire=prix_ariary,  
                montant=prix_ariary  
            )
            
            facture.calculer_total()
            
            return JsonResponse({
                'success': True,
                'facture_id': facture.id,
                'message': 'Facture générée avec succès',
                'existant': False
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

class FactureView(View):
    def get(self, request, facture_id):
        facture = get_object_or_404(Facture, pk=facture_id)
        
        total_ariary = facture.total
        total_en_lettres = convertir_ariary_en_lettres(total_ariary)
        
        lignes_avec_ariary = []
        for ligne in facture.lignes.all():
            lignes_avec_ariary.append({
                'description': ligne.description,
                'quantite': ligne.quantite,
                'prix_unitaire': ligne.prix_unitaire,
                'montant': ligne.montant,
                'prix_unitaire_ariary': f"{ligne.prix_unitaire:,.0f} Ar".replace(",", " "),
                'montant_ariary': f"{ligne.montant:,.0f} Ar".replace(",", " ")
            })
        
        context = {
            'facture': facture,
            'abonnement': facture.abonnement,
            'client': facture.client,
            'lignes': lignes_avec_ariary,
            'today': timezone.now().date(),
            'total_en_lettres': total_en_lettres,
            'total_ariary': f"{facture.total:,.0f} Ar".replace(",", " "),
        }
        return render(request, 'facturation/facture.html', context)

class ListeFacturesView(View):
    def get(self, request):
        factures = Facture.objects.all().select_related('client', 'abonnement')
        return render(request, 'facturation/liste_factures.html', {
            'factures': factures,
            'total_factures': factures.count()
        })