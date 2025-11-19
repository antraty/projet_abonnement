from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# Importez vos modèles Client et Subscription depuis l'app subscriptions
from subscriptions.models import Client, Subscription


class InvoiceSequence(models.Model):
    """
    Table de séquence par année pour générer des numéros de facture uniques de façon atomique.
    """
    year = models.IntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'facturation_invoice_sequence'
        verbose_name = "Séquence facture"
        verbose_name_plural = "Séquences facture"

    def __str__(self):
        return f"{self.year}: {self.last_number}"


class Facture(models.Model):
    STATUT_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('impayee', 'Impayée'),
        ('payee', 'Payée'),
        ('annulee', 'Annulée'),
    ]

    numero = models.CharField(max_length=20, unique=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    abonnement = models.ForeignKey(Subscription, on_delete=models.CASCADE, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateField(blank=True, null=True)
    date_paiement = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='brouillon')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        # Génération atomique du numéro via InvoiceSequence
        if not self.numero:
            annee = timezone.now().year
            # Transaction atomique + verrouillage de la ligne sequence pour éviter les doublons
            with transaction.atomic():
                seq_qs = InvoiceSequence.objects.select_for_update()
                seq, created = seq_qs.get_or_create(year=annee, defaults={'last_number': 0})
                seq.last_number += 1
                seq.save(update_fields=['last_number'])
                self.numero = f"FACT-{annee}-{seq.last_number:04d}"

        # Date d'échéance par défaut si non fournie
        if not self.date_echeance:
            self.date_echeance = timezone.now().date() + timedelta(days=30)

        super().save(*args, **kwargs)

    def calculer_total(self):
        """Calcule le total de la facture à partir des lignes."""
        self.total = sum((ligne.montant or Decimal('0.00')) for ligne in self.lignes.all())
        # Sauvegarder uniquement le champ total
        self.save(update_fields=['total'])

    def get_abonnement_info(self):
        """Retourne les informations formatées de l'abonnement pour la facture"""
        if self.abonnement:
            return {
                'type': getattr(self.abonnement, 'nom_abonnement', ''),
                'duree': f"{self.abonnement.duree_mois} mois",
                'date_debut': self.abonnement.date_debut.strftime("%d/%m/%Y") if getattr(self.abonnement, 'date_debut', None) else "",
                'date_fin': self.abonnement.date_fin.strftime("%d/%m/%Y") if getattr(self.abonnement, 'date_fin', None) else "",
                'statut': getattr(self.abonnement, 'statut', ''),
                'description': getattr(self.abonnement, 'description', '')
            }
        return None

    def __str__(self):
        return f"Facture {self.numero} - {self.client.nom}"

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-date_creation']


class LigneFacture(models.Model):
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')
    description = models.CharField(max_length=200)
    quantite = models.IntegerField(default=1)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    montant = models.DecimalField(max_digits=10, decimal_places=2, blank=True, default=0)

    def save(self, *args, **kwargs):
        # Calculer le montant avant sauvegarde
        self.montant = (self.quantite or 0) * (self.prix_unitaire or Decimal('0.00'))
        super().save(*args, **kwargs)
        # Recalculer le total de la facture parent
        self.facture.calculer_total()

    def delete(self, *args, **kwargs):
        facture_parent = self.facture
        super().delete(*args, **kwargs)
        facture_parent.calculer_total()

    def __str__(self):
        return f"{self.description} - {self.montant}€"

    class Meta:
        verbose_name = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
        ordering = ['id']