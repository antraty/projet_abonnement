from django.db import models
from django.utils import timezone
from subscriptions.models import Client, Subscription
import uuid

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
    date_echeance = models.DateField()
    date_paiement = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='brouillon')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        if not self.numero:
            # Générer un numéro de facture unique
            annee = timezone.now().year
            dernier_numero = Facture.objects.filter(
                date_creation__year=annee
            ).count() + 1
            self.numero = f"FACT-{annee}-{dernier_numero:04d}"
        
        if not self.date_echeance:
            self.date_echeance = timezone.now().date() + timezone.timedelta(days=30)
            
        super().save(*args, **kwargs)
    
    def calculer_total(self):
        """Calcule le total de la facture à partir des lignes"""
        self.total = sum(ligne.montant for ligne in self.lignes.all())
        # Sauvegarder automatiquement après calcul
        self.save(update_fields=['total'])
    
    def get_abonnement_info(self):
        """Retourne les informations formatées de l'abonnement pour la facture"""
        if self.abonnement:
            return {
                'type': self.abonnement.get_nom_abonnement_display(),
                'duree': f"{self.abonnement.duree_mois} mois",
                'date_debut': self.abonnement.date_debut.strftime("%d/%m/%Y") if self.abonnement.date_debut else "",
                'date_fin': self.abonnement.date_fin.strftime("%d/%m/%Y") if self.abonnement.date_fin else "",
                'statut': self.abonnement.get_statut_display(),
                'description': self.abonnement.description
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
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    
    def save(self, *args, **kwargs):
        self.montant = self.quantite * self.prix_unitaire
        super().save(*args, **kwargs)
        
        self.facture.calculer_total()
    
    def delete(self, *args, **kwargs):
        """Surcharge de delete pour recalculer le total après suppression"""
        facture_parent = self.facture
        super().delete(*args, **kwargs)
        facture_parent.calculer_total()
    
    def __str__(self):
        return f"{self.description} - {self.montant}€"
    
    class Meta:
        verbose_name = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
        ordering = ['id']