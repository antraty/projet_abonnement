from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from num2words import num2words
import json
import logging

from django.core.mail import EmailMessage
from django.conf import settings

from subscriptions.models import Subscription, Client
from .models import Facture, LigneFacture
from .invoices import generate_invoice_pdf

logger = logging.getLogger(__name__)


def get_next_invoice_number():
    """Génère un numéro de facture unique basé sur l'année et un séquentiel"""
    current_year = timezone.now().year
    
    # Trouver le dernier numéro de facture pour cette année
    last_invoice = Facture.objects.filter(
        numero__startswith=f"FACT-{current_year}-"
    ).order_by('-numero').first()
    
    if last_invoice:
        try:
            # Extraire le séquentiel du dernier numéro
            last_seq = int(last_invoice.numero.split('-')[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1
    
    return f"FACT-{current_year}-{next_seq:04d}"


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
                    'existant': True,
                    'email_sent': False
                })
            
            # Générer un numéro de facture unique
            invoice_number = get_next_invoice_number()
            
            facture = Facture.objects.create(
                numero=invoice_number,  # Ajout du numéro unique
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

            # --- Générer le PDF et envoyer l'email au client ---
            email_sent = False
            email_error = None
            pdf_bytes = None

            try:
                pdf_bytes = generate_invoice_pdf(facture)
            except Exception as e:
                logger.exception("Erreur génération PDF pour facture id=%s : %s", facture.id, e)
                email_error = f"Erreur génération PDF: {e}"

            client_email = facture.client.email if facture.client else None
            if client_email and pdf_bytes:
                subject = f"Votre facture {facture.numero}"
                body = (
                    f"Bonjour {facture.client.nom},\n\n"
                    f"Veuillez trouver ci-joint la facture {facture.numero}.\n\n"
                    "Cordialement,\nLe service facturation"
                )
                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    to=[client_email],
                )
                email.attach(f"{facture.numero}.pdf", pdf_bytes, 'application/pdf')
                try:
                    sent = email.send(fail_silently=False)
                    email_sent = bool(sent)
                    if email_sent:
                        logger.info("Facture %s envoyée par mail à %s", facture.numero, client_email)
                    else:
                        logger.warning("send() a retourné %s pour facture id=%s", sent, facture.id)
                except Exception as e:
                    logger.exception("Erreur envoi mail facture id=%s à %s : %s", facture.id, client_email, e)
                    email_error = str(e)
            else:
                if not client_email:
                    logger.warning("Client sans email pour la facture id=%s", facture.id)
                    if not email_error:
                        email_error = "Adresse email client absente."
                if not pdf_bytes:
                    logger.warning("PDF non généré pour la facture id=%s", facture.id)
                    if not email_error:
                        email_error = "PDF non généré."

            return JsonResponse({
                'success': True,
                'facture_id': facture.id,
                'message': 'Facture générée avec succès',
                'existant': False,
                'email_sent': email_sent,
                'email_error': email_error
            })
            
        except Exception as e:
            logger.exception("Erreur génération facture via API: %s", e)
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