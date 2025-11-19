# invoices.py
import logging
from io import BytesIO
from decimal import Decimal
from datetime import date, timedelta

from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views import View
from django.core.mail import EmailMessage

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from subscriptions.models import Subscription
from .models import Facture, LigneFacture

logger = logging.getLogger(__name__)


def generate_invoice_pdf(facture: Facture) -> bytes:
    """
    Génère un PDF de la facture et renvoie les bytes.
    Utilise reportlab (déjà présent dans votre projet).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()

    # Titre
    elements.append(Paragraph(f"Facture: {facture.numero}", styles['Title']))
    elements.append(Spacer(1, 12))

    # Informations client / facture
    client = facture.client
    info_lines = [
        f"Client: {client.nom}",
        f"Email: {client.email or '-'}",
        f"Téléphone: {client.telephone or '-'}",
        f"Date création: {facture.date_creation.strftime('%d/%m/%Y %H:%M')}",
        f"Date échéance: {facture.date_echeance.strftime('%d/%m/%Y') if facture.date_echeance else '-'}",
        f"Statut: {facture.get_statut_display()}",
    ]
    for line in info_lines:
        elements.append(Paragraph(line, styles['Normal']))
    elements.append(Spacer(1, 12))

    # Table des lignes
    table_data = [["Description", "Quantité", "Prix Unitaire", "Montant"]]
    for ligne in facture.lignes.all():
        table_data.append([
            ligne.description,
            str(ligne.quantite),
            f"{ligne.prix_unitaire:.2f}",
            f"{ligne.montant:.2f}"
        ])

    # Total
    table_data.append(["", "", "Total", f"{facture.total:.2f}"])

    table = Table(table_data, colWidths=[260, 60, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    if facture.notes:
        elements.append(Paragraph("Notes:", styles['Heading3']))
        elements.append(Paragraph(facture.notes, styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


class GenererFactureAbonnementAPI(View):
    """
    Endpoint pour générer une facture pour un abonnement et l'envoyer par mail au client.
    POST (ou GET) paramètre: abonnement_id
    Retour JSON: {'facture_id': ..., 'numero': ..., 'email_sent': True/False}
    """
    def post(self, request, *args, **kwargs):
        return self._handle(request)

    def get(self, request, *args, **kwargs):
        # Permet d'appeler depuis le navigateur pour tests simples
        return self._handle(request)

    def _handle(self, request):
        abonnement_id = request.POST.get('abonnement_id') or request.GET.get('abonnement_id')
        if not abonnement_id:
            return HttpResponseBadRequest("Paramètre 'abonnement_id' requis.")

        abonnement = get_object_or_404(Subscription, pk=abonnement_id)
        client = abonnement.client

        # Créer la facture
        facture = Facture.objects.create(
            client=client,
            abonnement=abonnement,
            date_echeance=(date.today() + timedelta(days=30)),
            statut='brouillon',
            total=0
        )

        # Créer la ligne de facture correspondant à l'abonnement (1 ligne)
        prix = getattr(abonnement, 'prix', None) or Decimal('0.00')
        LigneFacture.objects.create(
            facture=facture,
            description=f"Abonnement: {abonnement.nom_abonnement}",
            quantite=1,
            prix_unitaire=prix,
            montant=prix
        )
        # calcule automatique du total est fait par la logique de LigneFacture.save()

        # Générer le PDF
        try:
            pdf_bytes = generate_invoice_pdf(facture)
        except Exception as e:
            logger.exception("Erreur génération PDF facture id=%s: %s", facture.id, e)
            pdf_bytes = None

        # Envoyer le mail si adresse présente
        email_sent = False
        if client.email and pdf_bytes:
            subject = f"Votre facture {facture.numero}"
            body = (
                f"Bonjour {client.nom},\n\n"
                f"Veuillez trouver ci-joint la facture {facture.numero}.\n\n"
                "Cordialement,\nLe service facturation"
            )
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[client.email],
            )
            email.attach(f"{facture.numero}.pdf", pdf_bytes, 'application/pdf')
            try:
                email.send(fail_silently=False)
                email_sent = True
                logger.info("Facture %s envoyée par mail à %s", facture.numero, client.email)
            except Exception as e:
                logger.exception("Erreur envoi mail facture id=%s à %s: %s", facture.id, client.email, e)
                email_sent = False
        else:
            logger.warning("Impossible d'envoyer la facture id=%s: email client absent ou PDF non généré", facture.id)

        return JsonResponse({
            'facture_id': facture.id,
            'numero': facture.numero,
            'email_sent': email_sent,
        })