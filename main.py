import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
from datetime import datetime, timedelta
import json
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time
import os
from collections import defaultdict

class ApplicationSuiviAbonnements:
    def __init__(self, root):
        self.root = root
        self.root.title("Suivi des Abonnements Clients - Version Avancée")
        self.root.geometry("1200x800")
        
        # Configuration par défaut
        self.config = {
            'retention_days': 30,
            'grace_period': 7,
            'smtp_host': '',
            'smtp_port': 587,
            'smtp_user': '',
            'smtp_password': '',
            'auto_archive': True
        }
        
        # Charger la configuration
        self.load_config()
        
        # Initialiser la base de données
        self.init_db()
        
        # Variables pour les entrées
        self.nom_var = tk.StringVar()
        self.prenom_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.telephone_var = tk.StringVar()
        self.type_abonnement_var = tk.StringVar()
        self.prix_var = tk.DoubleVar()
        
        # Créer l'interface
        self.creer_interface()
        
        # Démarrer les tâches automatiques
        self.start_auto_tasks()
        
        # Charger les données initiales
        self.actualiser_donnees()
        
    def load_config(self):
        """Charger la configuration depuis un fichier"""
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
        except Exception as e:
            print(f"Erreur chargement config: {e}")
    
    def save_config(self):
        """Sauvegarder la configuration dans un fichier"""
        try:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Erreur sauvegarde config: {e}")

    def get_db_connection(self):
        """Retourne une nouvelle connexion SQLite utilisable depuis n'importe quel thread."""
        # check_same_thread=False permet d'ouvrir la connexion depuis un autre thread,
        # mais on préfère créer une connexion par thread pour éviter la récursion des curseurs.
        return sqlite3.connect('abonnements.db', check_same_thread=False)
    
    def init_db(self):
        """Initialiser la base de données SQLite avec les nouvelles tables"""
        # Connexion principale (utilisée par le thread principal / UI)
        self.conn = sqlite3.connect('abonnements.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Table clients
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                prenom TEXT NOT NULL,
                email TEXT,
                telephone TEXT,
                date_creation TEXT NOT NULL,
                statut TEXT DEFAULT 'actif',
                blacklist INTEGER DEFAULT 0,
                echecs_renouvellement INTEGER DEFAULT 0
            )
        ''')
        
        # Table abonnements avec nouveaux champs
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS abonnements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                type_abonnement TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT NOT NULL,
                prix REAL NOT NULL,
                statut TEXT NOT NULL,
                auto_renew INTEGER DEFAULT 0,
                date_archivage TEXT,
                archived INTEGER DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        ''')
        
        # Table archive_abonnements
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS archive_abonnements (
                id INTEGER PRIMARY KEY,
                client_id INTEGER NOT NULL,
                type_abonnement TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT NOT NULL,
                prix REAL NOT NULL,
                statut TEXT NOT NULL,
                date_archivage TEXT NOT NULL,
                raison_archivage TEXT
            )
        ''')
        
        # Table paiements
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS paiements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                abonnement_id INTEGER NOT NULL,
                montant REAL NOT NULL,
                date_paiement TEXT NOT NULL,
                methode TEXT NOT NULL,
                statut TEXT NOT NULL,
                reference TEXT,
                FOREIGN KEY (abonnement_id) REFERENCES abonnements (id)
            )
        ''')
        
        # Table templates_relances
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates_relances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                type_relance TEXT NOT NULL,
                jours_avant INTEGER DEFAULT 0,
                sujet TEXT NOT NULL,
                corps TEXT NOT NULL,
                actif INTEGER DEFAULT 1
            )
        ''')
        
        # Table historique_relances
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS historique_relances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                abonnement_id INTEGER NOT NULL,
                template_id INTEGER NOT NULL,
                date_envoi TEXT NOT NULL,
                statut TEXT NOT NULL,
                destinataire TEXT NOT NULL,
                FOREIGN KEY (abonnement_id) REFERENCES abonnements (id),
                FOREIGN KEY (template_id) REFERENCES templates_relances (id)
            )
        ''')
        
        # Table tags
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE,
                couleur TEXT DEFAULT '#007bff'
            )
        ''')
        
        # Table abonnement_tags
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS abonnement_tags (
                abonnement_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (abonnement_id, tag_id),
                FOREIGN KEY (abonnement_id) REFERENCES abonnements (id),
                FOREIGN KEY (tag_id) REFERENCES tags (id)
            )
        ''')
        
        # Table logs_audit
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                table_concernee TEXT NOT NULL,
                id_concerne INTEGER,
                anciennes_valeurs TEXT,
                nouvelles_valeurs TEXT,
                date_action TEXT NOT NULL,
                utilisateur TEXT DEFAULT 'system'
            )
        ''')
        
        # Insérer les templates par défaut
        self.init_templates_defaut()
        
        self.conn.commit()
    
    def init_templates_defaut(self):
        """Insérer les templates de relance par défaut"""
        templates = [
            ('Rappel J-7', 'rappel', 7, 'Rappel - Votre abonnement expire bientôt',
             'Bonjour {prenom} {nom},\n\nVotre abonnement {type} expire le {date_fin}.\nPensez à le renouveler!\n\nCordialement'),
            ('Rappel J-1', 'rappel', 1, 'Dernier rappel - Expiration imminente',
             'Bonjour {prenom} {nom},\n\nVotre abonnement {type} expire DEMAIN ({date_fin}).\nRenouvelez dès maintenant!\n\nCordialement'),
            ('Relance J+3', 'relance', -3, 'Votre abonnement a expiré',
             'Bonjour {prenom} {nom},\n\nVotre abonnement {type} a expiré le {date_fin}.\nRenouvelez pour continuer le service!\n\nCordialement')
        ]
        
        for nom, type_relance, jours_avant, sujet, corps in templates:
            self.cursor.execute('''
                INSERT OR IGNORE INTO templates_relances (nom, type_relance, jours_avant, sujet, corps, actif)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (nom, type_relance, jours_avant, sujet, corps))
        
        self.conn.commit()
    
    def creer_interface(self):
        """Créer l'interface utilisateur"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configuration du grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Menu principal
        self.creer_menu(main_frame)
        
        # Zone de contenu
        self.content_frame = ttk.Frame(main_frame, relief='sunken', padding="10")
        self.content_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)
        
        # Afficher l'accueil par défaut
        self.afficher_accueil()
    
    def creer_menu(self, parent):
        """Créer le menu de navigation étendu"""
        menu_frame = ttk.Frame(parent)
        menu_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Boutons du menu principal
        buttons_principaux = [
            ("🏠 Accueil", self.afficher_accueil),
            ("👥 Gestion Clients", self.afficher_gestion_clients),
            ("🗓️ Gestion Abonnements", self.afficher_gestion_abonnements),
            ("💰 Paiements", self.afficher_gestion_paiements),
            ("📧 Relances", self.afficher_gestion_relances),
            ("🧰 Outils", self.afficher_outils_avances),
            ("📊 Dashboard", self.afficher_dashboard),
            ("❓ Aide", self.afficher_aide)
        ]
        
        for i, (text, command) in enumerate(buttons_principaux):
            ttk.Button(menu_frame, text=text, command=command).grid(row=0, column=i, padx=2, pady=5)
    
    def start_auto_tasks(self):
        """Démarrer les tâches automatiques en arrière-plan"""
        def task_archivage():
            while True:
                try:
                    self.auto_archiver_abonnements()
                    time.sleep(3600)  # Vérifier toutes les heures
                except Exception as e:
                    print(f"Erreur tâche archivage: {e}")
                    time.sleep(300)
        
        def task_relances():
            while True:
                try:
                    self.verifier_relances_automatiques()
                    time.sleep(1800)  # Vérifier toutes les 30 minutes
                except Exception as e:
                    print(f"Erreur tâche relances: {e}")
                    time.sleep(300)
        
        # Démarrer les threads
        threading.Thread(target=task_archivage, daemon=True).start()
        threading.Thread(target=task_relances, daemon=True).start()
    
    def auto_archiver_abonnements(self):
        """Archiver automatiquement les abonnements expirés selon la politique de rétention"""
        try:
            # Utiliser une connexion locale dans le thread pour éviter "Recursive use of cursors"
            conn = self.get_db_connection()
            cur = conn.cursor()

            date_limite = (datetime.now() - timedelta(days=self.config['retention_days'])).strftime("%Y-%m-%d")
            
            # Récupérer les abonnements à archiver
            cur.execute('''
                SELECT * FROM abonnements 
                WHERE statut = 'Expiré' AND date_fin < ? AND archived = 0
            ''', (date_limite,))
            
            abonnements_a_archiver = cur.fetchall()
            
            for abonnement in abonnements_a_archiver:
                # Archiver dans la table archive
                cur.execute('''
                    INSERT INTO archive_abonnements 
                    (id, client_id, type_abonnement, date_debut, date_fin, prix, statut, date_archivage, raison_archivage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (abonnement[0], abonnement[1], abonnement[2], abonnement[3], 
                      abonnement[4], abonnement[5], abonnement[6], 
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Archivage automatique"))
                
                # Marquer comme archivé dans la table principale
                cur.execute('''
                    UPDATE abonnements SET archived = 1, date_archivage = ?
                    WHERE id = ?
                ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), abonnement[0]))
                
                # Logger l'action (log_audit ouvre sa propre connexion)
                self.log_audit('ARCHIVAGE', 'abonnements', abonnement[0], 
                              f"Abonnement {abonnement[0]} archivé automatiquement")
            
            if abonnements_a_archiver:
                conn.commit()
                print(f"{len(abonnements_a_archiver)} abonnement(s) archivé(s) automatiquement")
            conn.close()
                
        except Exception as e:
            print(f"Erreur archivage automatique: {e}")
    
    def verifier_relances_automatiques(self):
        """Vérifier et envoyer les relances automatiques"""
        try:
            # Utiliser une connexion locale dans le thread
            conn = self.get_db_connection()
            cur = conn.cursor()

            aujourdhui = datetime.now().strftime("%Y-%m-%d")
            
            # Récupérer les templates actifs
            cur.execute('''
                SELECT * FROM templates_relances WHERE actif = 1
            ''')
            templates = cur.fetchall()
            
            for template in templates:
                template_id, nom, type_relance, jours_avant, sujet, corps, actif = template
                
                # Calculer la date cible
                if jours_avant >= 0:
                    date_cible = (datetime.now() + timedelta(days=jours_avant)).strftime("%Y-%m-%d")
                else:
                    date_cible = (datetime.now() - timedelta(days=abs(jours_avant))).strftime("%Y-%m-%d")
                
                # Récupérer les abonnements concernés
                if jours_avant >= 0:
                    # Relances avant expiration
                    cur.execute('''
                        SELECT a.*, c.nom, c.prenom, c.email 
                        FROM abonnements a
                        JOIN clients c ON a.client_id = c.id
                        WHERE a.date_fin = ? AND a.statut = 'Actif' AND c.email IS NOT NULL
                    ''', (date_cible,))
                else:
                    # Relances après expiration
                    cur.execute('''
                        SELECT a.*, c.nom, c.prenom, c.email 
                        FROM abonnements a
                        JOIN clients c ON a.client_id = c.id
                        WHERE a.date_fin = ? AND a.statut = 'Expiré' AND c.email IS NOT NULL
                    ''', (date_cible,))
                
                abonnements = cur.fetchall()
                
                for abonnement in abonnements:
                    # Vérifier si cette relance a déjà été envoyée
                    # attention: ici on utilise la connexion locale pour la vérification
                    cur.execute('''
                        SELECT COUNT(*) FROM historique_relances 
                        WHERE abonnement_id = ? AND template_id = ?
                    ''', (abonnement[0], template_id))
                    
                    if cur.fetchone()[0] == 0:
                        # Envoyer la relance (la fonction ouvre/ferme sa propre connexion pour l'historique)
                        self.envoyer_relance(abonnement, template)
            conn.close()
        except Exception as e:
            print(f"Erreur vérification relances: {e}")
    
    def envoyer_relance(self, abonnement, template):
        """Envoyer une relance par email"""
        try:
            if not self.config['smtp_host']:
                return  # SMTP non configuré
            
            # template tuple: id, nom, type_relance, jours_avant, sujet, corps, actif
            template_id, nom_template, type_relance, jours_avant, sujet_template, corps_template, actif = template
            
            # abonnement contient a.* puis nom, prenom, email -> les 3 derniers éléments sont nom, prenom, email
            nom_client = abonnement[-3]
            prenom_client = abonnement[-2]
            email_client = abonnement[-1]
            
            # Préparer le message
            sujet = sujet_template.format(
                nom=nom_client,
                prenom=prenom_client,
                type=abonnement[2],
                date_fin=abonnement[4]
            )
            
            corps = corps_template.format(
                nom=nom_client,
                prenom=prenom_client,
                type=abonnement[2],
                date_fin=abonnement[4],
                prix=abonnement[5]
            )
            
            # Configuration SMTP
            msg = MIMEMultipart()
            msg['From'] = self.config['smtp_user']
            msg['To'] = email_client
            msg['Subject'] = sujet
            msg.attach(MIMEText(corps, 'plain'))
            
            # Envoyer l'email
            server = smtplib.SMTP(self.config['smtp_host'], self.config['smtp_port'])
            server.starttls()
            server.login(self.config['smtp_user'], self.config['smtp_password'])
            server.send_message(msg)
            server.quit()
            
            # Enregistrer dans l'historique via une connexion locale (évite le partage de curseur)
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO historique_relances 
                (abonnement_id, template_id, date_envoi, statut, destinataire)
                VALUES (?, ?, ?, ?, ?)
            ''', (abonnement[0], template_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                  'envoyé', email_client))
            conn.commit()
            conn.close()
            
            print(f"Relance envoyée à {email_client}")
            
        except Exception as e:
            print(f"Erreur envoi relance: {e}")
            # Enregistrer l'échec via une connexion locale
            try:
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO historique_relances 
                    (abonnement_id, template_id, date_envoi, statut, destinataire)
                    VALUES (?, ?, ?, ?, ?)
                ''', (abonnement[0], template_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                      'échec', abonnement[-1]))
                conn.commit()
                conn.close()
            except Exception as e2:
                print(f"Erreur enregistrement échec relance: {e2}")
    
    def log_audit(self, action, table_concernee, id_concerne, description=""):
        """Logger une action dans l'audit trail"""
        try:
            # Utiliser une connexion locale pour l'audit afin d'éviter le partage de curseurs entre threads
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO logs_audit 
                (action, table_concernee, id_concerne, anciennes_valeurs, date_action)
                VALUES (?, ?, ?, ?, ?)
            ''', (action, table_concernee, id_concerne, description, 
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erreur log audit: {e}")

    def clear_content(self):
        """Effacer le contenu de la zone principale"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def afficher_accueil(self):
        """Afficher la page d'accueil (version étendue)"""
        self.clear_content()
        
        # Titre
        ttk.Label(self.content_frame, text="🏠 ACCUEIL - SUIVI DES ABONNEMENTS AVANCÉ", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=20)
        
        # Date actuelle
        date_actuelle = datetime.now().strftime("%d/%m/%Y %H:%M")
        ttk.Label(self.content_frame, text=f"Date actuelle: {date_actuelle}",
                 font=('Arial', 12)).grid(row=1, column=0, pady=10)
        
        # Description étendue
        description = """
        Application avancée de suivi des abonnements clients et personnels
        
        Nouvelles fonctionnalités :
        • 🗃️ Archivage automatique avec politique de rétention
        • 📧 Système de relances automatiques par email
        • 🔄 Renouvellement automatique
        • 💰 Gestion des paiements
        • 🏷️ Système de tags et catégories
        • 📊 Dashboard analytique avancé
        • 💾 Export multiples (CSV, ICS, etc.)
        • 🔍 Recherche et filtres avancés
        """
        
        ttk.Label(self.content_frame, text=description, justify=tk.LEFT,
                 font=('Arial', 11)).grid(row=2, column=0, pady=20)
        
        # Boutons d'action
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=3, column=0, pady=20)
        
        ttk.Button(action_frame, text="🔄 Actualiser toutes les données", 
                  command=self.actualiser_donnees).grid(row=0, column=0, padx=10)
        ttk.Button(action_frame, text="🧰 Outils avancés", 
                  command=self.afficher_outils_avances).grid(row=0, column=1, padx=10)
        ttk.Button(action_frame, text="❌ Quitter l'application", 
                  command=self.root.quit).grid(row=0, column=2, padx=10)
        
        # Statistiques rapides étendues
        self.afficher_statistiques_rapides_avancees()
    
    def afficher_statistiques_rapides_avancees(self):
        """Afficher les statistiques rapides avancées"""
        stats_frame = ttk.LabelFrame(self.content_frame, text="📊 Tableau de bord rapide", padding="10")
        stats_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=20)
        stats_frame.columnconfigure(0, weight=1)
        
        try:
            # Récupérer les statistiques étendues
            stats = self.calculer_statistiques_avancees()
            
            # Ajouter des stats supplémentaires
            self.cursor.execute("SELECT COUNT(*) FROM historique_relances WHERE date_envoi >= date('now', '-7 days')")
            relances_7j = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM archive_abonnements")
            archives_total = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM paiements WHERE statut = 'payé' AND date_paiement >= date('now', '-30 days')")
            paiements_30j = self.cursor.fetchone()[0]
            
            stats_text = f"""
            Clients & Abonnements:
            • Clients actifs: {stats['clients_actifs']}
            • Abonnements actifs: {stats['abonnements_actifs']}
            • Archives total: {archives_total}
            
            Activité récente:
            • Relances (7j): {relances_7j}
            • Paiements (30j): {paiements_30j}
            • CA mensuel: €{stats['ca_mensuel']:.2f}
            • Taux renouvellement: {stats['taux_renouvellement']:.1f}%
            """
            
            ttk.Label(stats_frame, text=stats_text, justify=tk.LEFT,
                     font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W)
            
        except Exception as e:
            ttk.Label(stats_frame, text="Erreur lors du chargement des statistiques",
                     foreground='red').grid(row=0, column=0)

    def calculer_statistiques_avancees(self):
        """Calculer des statistiques avancées pour le dashboard"""
        stats = {}
        
        try:
            # Clients actifs
            self.cursor.execute("SELECT COUNT(*) FROM clients WHERE statut = 'actif'")
            stats['clients_actifs'] = self.cursor.fetchone()[0]
            
            # Abonnements actifs
            self.cursor.execute("SELECT COUNT(*) FROM abonnements WHERE statut = 'Actif'")
            stats['abonnements_actifs'] = self.cursor.fetchone()[0]
            
            # CA mensuel
            mois_courant = datetime.now().strftime("%Y-%m")
            self.cursor.execute('''
                SELECT SUM(prix) FROM abonnements 
                WHERE strftime('%Y-%m', date_debut) = ? AND statut = 'Actif'
            ''', (mois_courant,))
            stats['ca_mensuel'] = self.cursor.fetchone()[0] or 0
            
            # Taux de renouvellement (simplifié)
            self.cursor.execute("SELECT COUNT(*) FROM abonnements WHERE auto_renew = 1")
            auto_renew = self.cursor.fetchone()[0]
            stats['taux_renouvellement'] = (auto_renew / stats['abonnements_actifs'] * 100) if stats['abonnements_actifs'] > 0 else 0
            
            # Évolution mensuelle
            stats['evolution_mensuelle'] = {}
            for i in range(6):
                mois = (datetime.now() - timedelta(days=30*i)).strftime("%Y-%m")
                self.cursor.execute('''
                    SELECT COUNT(*), SUM(prix) FROM abonnements 
                    WHERE strftime('%Y-%m', date_debut) = ?
                ''', (mois,))
                result = self.cursor.fetchone()
                stats['evolution_mensuelle'][mois] = {
                    'abonnements': result[0] or 0,
                    'ca': result[1] or 0
                }
                
        except Exception as e:
            print(f"Erreur calcul statistiques: {e}")
        
        return stats

    def afficher_gestion_clients(self):
        """Afficher la gestion des clients (version de base)"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="👥 GESTION DES CLIENTS", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10)
        
        # Frame pour les actions
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(action_frame, text="➕ Ajouter un client",
                  command=self.ajouter_client).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="📋 Lister les clients",
                  command=self.lister_clients).grid(row=0, column=1, padx=5)
        
        # Zone d'affichage des clients
        self.client_tree = ttk.Treeview(self.content_frame, columns=('ID', 'Nom', 'Prénom', 'Email', 'Téléphone', 'Date Création'), show='headings')
        self.client_tree.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Configurer les colonnes
        columns = [('ID', 50), ('Nom', 150), ('Prénom', 150), ('Email', 200), ('Téléphone', 120), ('Date Création', 120)]
        for col, width in columns:
            self.client_tree.heading(col, text=col)
            self.client_tree.column(col, width=width)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.content_frame, orient=tk.VERTICAL, command=self.client_tree.yview)
        scrollbar.grid(row=2, column=1, sticky=(tk.N, tk.S))
        self.client_tree.configure(yscrollcommand=scrollbar.set)
        
        # Configurer le grid pour l'expansion
        self.content_frame.rowconfigure(2, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        
        # Charger les clients
        self.charger_clients()

    def ajouter_client(self):
        """Ouvrir une fenêtre pour ajouter un client"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Ajouter un client")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Ajouter un nouveau client", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        # Champs du formulaire
        fields = [
            ("Nom*:", self.nom_var),
            ("Prénom*:", self.prenom_var),
            ("Email:", self.email_var),
            ("Téléphone:", self.telephone_var)
        ]
        
        for i, (label, var) in enumerate(fields, 1):
            ttk.Label(dialog, text=label).grid(row=i, column=0, padx=10, pady=5, sticky=tk.W)
            ttk.Entry(dialog, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=5)
        
        # Boutons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Enregistrer", command=lambda: self.enregistrer_client(dialog)).grid(row=0, column=0, padx=10)
        ttk.Button(button_frame, text="Annuler", command=dialog.destroy).grid(row=0, column=1, padx=10)

    def enregistrer_client(self, dialog):
        """Enregistrer un nouveau client dans la base de données"""
        if not self.nom_var.get() or not self.prenom_var.get():
            messagebox.showerror("Erreur", "Le nom et le prénom sont obligatoires")
            return
        
        try:
            date_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                INSERT INTO clients (nom, prenom, email, telephone, date_creation)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.nom_var.get(), self.prenom_var.get(), self.email_var.get(), 
                  self.telephone_var.get(), date_creation))
            
            self.conn.commit()
            
            # Réinitialiser les variables
            self.nom_var.set("")
            self.prenom_var.set("")
            self.email_var.set("")
            self.telephone_var.set("")
            
            messagebox.showinfo("Succès", "Client ajouté avec succès")
            dialog.destroy()
            self.charger_clients()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'ajout du client: {str(e)}")

    def charger_clients(self):
        """Charger la liste des clients dans le Treeview"""
        # Vider le treeview
        for item in self.client_tree.get_children():
            self.client_tree.delete(item)
        
        try:
            self.cursor.execute("SELECT * FROM clients ORDER BY nom, prenom")
            clients = self.cursor.fetchall()
            
            for client in clients:
                self.client_tree.insert('', tk.END, values=client)
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du chargement des clients: {str(e)}")

    def lister_clients(self):
        """Afficher tous les clients (rafraîchir)"""
        self.charger_clients()
        messagebox.showinfo("Info", "Liste des clients actualisée")

    def afficher_gestion_abonnements(self):
        """Afficher la gestion des abonnements (version de base)"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="🗓️ GESTION DES ABONNEMENTS", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10)
        
        # Frame pour les actions
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(action_frame, text="➕ Ajouter un abonnement",
                  command=self.ajouter_abonnement).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="📋 Liste complète",
                  command=self.lister_abonnements).grid(row=0, column=1, padx=5)
        ttk.Button(action_frame, text="🔔 Rappels / relances",
                  command=self.afficher_rappels).grid(row=0, column=2, padx=5)
        
        # Zone d'affichage des abonnements
        self.abonnement_tree = ttk.Treeview(self.content_frame, 
                                          columns=('ID', 'Client', 'Type', 'Début', 'Fin', 'Prix', 'Statut'), 
                                          show='headings')
        self.abonnement_tree.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Configurer les colonnes
        columns = [('ID', 50), ('Client', 200), ('Type', 150), ('Début', 100), 
                  ('Fin', 100), ('Prix', 80), ('Statut', 80)]
        for col, width in columns:
            self.abonnement_tree.heading(col, text=col)
            self.abonnement_tree.column(col, width=width)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.content_frame, orient=tk.VERTICAL, command=self.abonnement_tree.yview)
        scrollbar.grid(row=2, column=1, sticky=(tk.N, tk.S))
        self.abonnement_tree.configure(yscrollcommand=scrollbar.set)
        
        # Configurer le grid pour l'expansion
        self.content_frame.rowconfigure(2, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        
        # Charger les abonnements
        self.charger_abonnements()

    def ajouter_abonnement(self):
        """Ouvrir une fenêtre pour ajouter un abonnement"""
        # Récupérer la liste des clients
        try:
            self.cursor.execute("SELECT id, nom, prenom FROM clients ORDER BY nom, prenom")
            clients = self.cursor.fetchall()
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du chargement des clients: {str(e)}")
            return
        
        if not clients:
            messagebox.showwarning("Avertissement", "Aucun client disponible. Veuillez d'abord ajouter un client.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Ajouter un abonnement")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Ajouter un nouvel abonnement", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        # Sélection du client
        ttk.Label(dialog, text="Client*:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        client_var = tk.StringVar()
        client_combo = ttk.Combobox(dialog, textvariable=client_var, width=30)
        client_combo['values'] = [f"{nom} {prenom} (ID: {id})" for id, nom, prenom in clients]
        client_combo.grid(row=1, column=1, padx=10, pady=5)
        
        # Type d'abonnement
        ttk.Label(dialog, text="Type d'abonnement*:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        type_combo = ttk.Combobox(dialog, textvariable=self.type_abonnement_var, width=30)
        type_combo['values'] = ['Mensuel', 'Trimestriel', 'Semestriel', 'Annuel', 'Personnalisé']
        type_combo.grid(row=2, column=1, padx=10, pady=5)
        
        # Date de début
        ttk.Label(dialog, text="Date de début*:").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        date_debut_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(dialog, textvariable=date_debut_var, width=30).grid(row=3, column=1, padx=10, pady=5)
        
        # Prix
        ttk.Label(dialog, text="Prix*:").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(dialog, textvariable=self.prix_var, width=30).grid(row=4, column=1, padx=10, pady=5)
        
        # Case à cocher pour le renouvellement automatique
        auto_renew_var = tk.BooleanVar()
        ttk.Checkbutton(dialog, text="Renouvellement automatique", variable=auto_renew_var).grid(row=5, column=0, columnspan=2, pady=10)
        
        # Boutons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Enregistrer", 
                  command=lambda: self.enregistrer_abonnement(dialog, client_var.get(), date_debut_var.get(), auto_renew_var.get())).grid(row=0, column=0, padx=10)
        ttk.Button(button_frame, text="Annuler", command=dialog.destroy).grid(row=0, column=1, padx=10)

    def enregistrer_abonnement(self, dialog, client_selectionne, date_debut, auto_renew):
        """Enregistrer un nouvel abonnement"""
        if not client_selectionne or not self.type_abonnement_var.get() or not date_debut or not self.prix_var.get():
            messagebox.showerror("Erreur", "Tous les champs obligatoires doivent être remplis")
            return
        
        try:
            # Extraire l'ID du client
            client_id = int(client_selectionne.split('(ID: ')[1].rstrip(')'))
            
            # Calculer la date de fin selon le type
            date_debut_obj = datetime.strptime(date_debut, "%Y-%m-%d")
            type_abonnement = self.type_abonnement_var.get()
            
            if type_abonnement == 'Mensuel':
                date_fin = date_debut_obj + timedelta(days=30)
            elif type_abonnement == 'Trimestriel':
                date_fin = date_debut_obj + timedelta(days=90)
            elif type_abonnement == 'Semestriel':
                date_fin = date_debut_obj + timedelta(days=180)
            elif type_abonnement == 'Annuel':
                date_fin = date_debut_obj + timedelta(days=365)
            else:
                # Pour personnalisé, demander la durée
                duree = simpledialog.askinteger("Durée personnalisée", "Nombre de jours:", minvalue=1)
                if duree:
                    date_fin = date_debut_obj + timedelta(days=duree)
                else:
                    return
            
            date_fin_str = date_fin.strftime("%Y-%m-%d")
            
            # Vérifier si l'abonnement est actif ou expiré
            statut = "Actif" if date_fin >= datetime.now() else "Expiré"
            
            self.cursor.execute('''
                INSERT INTO abonnements (client_id, type_abonnement, date_debut, date_fin, prix, statut, auto_renew)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (client_id, type_abonnement, date_debut, date_fin_str, self.prix_var.get(), statut, 1 if auto_renew else 0))
            
            self.conn.commit()
            
            # Réinitialiser les variables
            self.type_abonnement_var.set("")
            self.prix_var.set(0.0)
            
            messagebox.showinfo("Succès", "Abonnement ajouté avec succès")
            dialog.destroy()
            self.charger_abonnements()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'ajout de l'abonnement: {str(e)}")

    def charger_abonnements(self):
        """Charger la liste des abonnements dans le Treeview"""
        # Vider le treeview
        for item in self.abonnement_tree.get_children():
            self.abonnement_tree.delete(item)
        
        try:
            self.cursor.execute('''
                SELECT a.id, c.nom || ' ' || c.prenom, a.type_abonnement, 
                       a.date_debut, a.date_fin, a.prix, a.statut
                FROM abonnements a
                JOIN clients c ON a.client_id = c.id
                ORDER BY a.date_fin
            ''')
            abonnements = self.cursor.fetchall()
            
            for abonnement in abonnements:
                self.abonnement_tree.insert('', tk.END, values=abonnement)
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du chargement des abonnements: {str(e)}")

    def lister_abonnements(self):
        """Afficher tous les abonnements (rafraîchir)"""
        self.charger_abonnements()
        messagebox.showinfo("Info", "Liste des abonnements actualisée")

    def afficher_rappels(self):
        """Afficher les rappels d'abonnements expirant bientôt"""
        try:
            date_limite = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            self.cursor.execute('''
                SELECT c.nom, c.prenom, a.type_abonnement, a.date_fin
                FROM abonnements a
                JOIN clients c ON a.client_id = c.id
                WHERE a.date_fin <= ? AND a.statut = 'Actif'
                ORDER BY a.date_fin
            ''', (date_limite,))
            
            rappels = self.cursor.fetchall()
            
            if not rappels:
                messagebox.showinfo("Rappels", "Aucun abonnement n'expire dans les 7 prochains jours.")
                return
            
            # Créer une fenêtre pour afficher les rappels
            rappel_window = tk.Toplevel(self.root)
            rappel_window.title("🔔 Rappels - Abonnements à renouveler")
            rappel_window.geometry("600x400")
            
            ttk.Label(rappel_window, text="Abonnements expirant dans les 7 prochains jours:", 
                     font=('Arial', 12, 'bold')).pack(pady=10)
            
            # Treeview pour les rappels
            rappel_tree = ttk.Treeview(rappel_window, columns=('Client', 'Type', 'Date fin'), show='headings')
            rappel_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            rappel_tree.heading('Client', text='Client')
            rappel_tree.heading('Type', text="Type d'abonnement")
            rappel_tree.heading('Date fin', text='Date de fin')
            
            rappel_tree.column('Client', width=200)
            rappel_tree.column('Type', width=150)
            rappel_tree.column('Date fin', width=100)
            
            for rappel in rappels:
                rappel_tree.insert('', tk.END, values=rappel)
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du chargement des rappels: {str(e)}")

    def afficher_gestion_paiements(self):
        """Afficher la gestion des paiements COMPLÈTE"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="💰 GESTION DES PAIEMENTS", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10)
        
        # Frame actions
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(action_frame, text="➕ Nouveau paiement",
                  command=self.ajouter_paiement).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="📋 Importer CSV",
                  command=self.importer_paiements_csv).grid(row=0, column=1, padx=5)
        ttk.Button(action_frame, text="🔄 Actualiser",
                  command=self.charger_paiements).grid(row=0, column=2, padx=5)
        
        # Frame de recherche/filtres
        search_frame = ttk.Frame(self.content_frame)
        search_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(search_frame, text="Rechercher:").grid(row=0, column=0, padx=5)
        self.search_paiement_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_paiement_var, width=30)
        search_entry.grid(row=0, column=1, padx=5)
        search_entry.bind('<KeyRelease>', self.filtrer_paiements)
        
        # Treeview des paiements
        columns = ['ID', 'Client', 'Abonnement', 'Montant', 'Date', 'Méthode', 'Statut', 'Référence']
        self.paiement_tree = ttk.Treeview(self.content_frame, columns=columns, show='headings')
        
        for col in columns:
            self.paiement_tree.heading(col, text=col)
            if col in ['ID', 'Montant']:
                self.paiement_tree.column(col, width=80)
            else:
                self.paiement_tree.column(col, width=120)
        
        self.paiement_tree.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Menu contextuel pour le treeview
        self.menu_contextuel_paiement = tk.Menu(self.root, tearoff=0)
        self.menu_contextuel_paiement.add_command(label="Marquer comme payé", command=self.marquer_paye)
        self.menu_contextuel_paiement.add_command(label="Supprimer", command=self.supprimer_paiement)
        
        self.paiement_tree.bind("<Button-3>", self.afficher_menu_contextuel_paiement)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.content_frame, orient=tk.VERTICAL, command=self.paiement_tree.yview)
        scrollbar.grid(row=3, column=1, sticky=(tk.N, tk.S))
        self.paiement_tree.configure(yscrollcommand=scrollbar.set)
        
        # Statistiques des paiements
        stats_frame = ttk.LabelFrame(self.content_frame, text="📈 Statistiques Paiements", padding="10")
        stats_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        
        self.stats_label = ttk.Label(stats_frame, text="", justify=tk.LEFT)
        self.stats_label.pack()
        
        self.content_frame.rowconfigure(3, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        
        self.charger_paiements()
        self.afficher_stats_paiements()

    def ajouter_paiement(self):
        """Ouvrir une fenêtre pour ajouter un paiement COMPLET"""
        # Récupérer la liste des abonnements
        try:
            self.cursor.execute('''
                SELECT a.id, c.nom, c.prenom, a.type_abonnement 
                FROM abonnements a
                JOIN clients c ON a.client_id = c.id
                WHERE a.statut = 'Actif'
                ORDER BY c.nom, c.prenom
            ''')
            abonnements = self.cursor.fetchall()
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du chargement des abonnements: {str(e)}")
            return
        
        if not abonnements:
            messagebox.showwarning("Avertissement", "Aucun abonnement actif disponible.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Nouveau Paiement")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Ajouter un nouveau paiement", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        # Sélection de l'abonnement
        ttk.Label(dialog, text="Abonnement*:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        abonnement_var = tk.StringVar()
        abonnement_combo = ttk.Combobox(dialog, textvariable=abonnement_var, width=40, state="readonly")
        abonnement_combo['values'] = [f"{prenom} {nom} - {type_abon} (ID: {id})" for id, nom, prenom, type_abon in abonnements]
        abonnement_combo.grid(row=1, column=1, padx=10, pady=5)
        
        # Montant
        ttk.Label(dialog, text="Montant*:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        montant_var = tk.DoubleVar()
        ttk.Entry(dialog, textvariable=montant_var, width=20).grid(row=2, column=1, padx=10, pady=5)
        
        # Date de paiement
        ttk.Label(dialog, text="Date paiement*:").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        date_paiement_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(dialog, textvariable=date_paiement_var, width=20).grid(row=3, column=1, padx=10, pady=5)
        
        # Méthode de paiement
        ttk.Label(dialog, text="Méthode*:").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        methode_var = tk.StringVar()
        methode_combo = ttk.Combobox(dialog, textvariable=methode_var, width=20, state="readonly")
        methode_combo['values'] = ['Carte Bancaire', 'Virement', 'Espèces', 'Chèque', 'Prélèvement', 'PayPal']
        methode_combo.grid(row=4, column=1, padx=10, pady=5)
        
        # Statut
        ttk.Label(dialog, text="Statut*:").grid(row=5, column=0, padx=10, pady=5, sticky=tk.W)
        statut_var = tk.StringVar(value="payé")
        statut_combo = ttk.Combobox(dialog, textvariable=statut_var, width=20, state="readonly")
        statut_combo['values'] = ['payé', 'en attente', 'échec', 'remboursé']
        statut_combo.grid(row=5, column=1, padx=10, pady=5)
        
        # Référence
        ttk.Label(dialog, text="Référence:").grid(row=6, column=0, padx=10, pady=5, sticky=tk.W)
        reference_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=reference_var, width=30).grid(row=6, column=1, padx=10, pady=5)
        
        # Boutons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="💾 Enregistrer", 
                  command=lambda: self.enregistrer_paiement(
                      dialog, abonnement_var.get(), montant_var.get(), 
                      date_paiement_var.get(), methode_var.get(), 
                      statut_var.get(), reference_var.get()
                  )).grid(row=0, column=0, padx=10)
        ttk.Button(button_frame, text="❌ Annuler", command=dialog.destroy).grid(row=0, column=1, padx=10)

    def enregistrer_paiement(self, dialog, abonnement_selectionne, montant, date_paiement, methode, statut, reference):
        """Enregistrer un nouveau paiement dans la base de données"""
        if not all([abonnement_selectionne, montant, date_paiement, methode, statut]):
            messagebox.showerror("Erreur", "Tous les champs obligatoires doivent être remplis")
            return
        
        try:
            # Extraire l'ID de l'abonnement
            abonnement_id = int(abonnement_selectionne.split('(ID: ')[1].rstrip(')'))
            
            # Vérifier si l'abonnement existe
            self.cursor.execute("SELECT id FROM abonnements WHERE id = ?", (abonnement_id,))
            if not self.cursor.fetchone():
                messagebox.showerror("Erreur", "Abonnement non trouvé")
                return
            
            # Insérer le paiement
            self.cursor.execute('''
                INSERT INTO paiements (abonnement_id, montant, date_paiement, methode, statut, reference)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (abonnement_id, montant, date_paiement, methode, statut, reference))
            
            self.conn.commit()
            
            # Logger l'action
            self.log_audit('AJOUT_PAIEMENT', 'paiements', self.cursor.lastrowid,
                          f"Paiement de {montant}€ pour abonnement {abonnement_id}")
            
            messagebox.showinfo("Succès", "Paiement enregistré avec succès")
            dialog.destroy()
            self.charger_paiements()
            self.afficher_stats_paiements()
            
        except ValueError:
            messagebox.showerror("Erreur", "ID d'abonnement invalide")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'ajout du paiement: {str(e)}")

    def charger_paiements(self):
        """Charger la liste des paiements avec filtres"""
        try:
            for item in self.paiement_tree.get_children():
                self.paiement_tree.delete(item)
            
            # Construction de la requête avec filtres
            query = '''
                SELECT p.id, c.nom || ' ' || c.prenom, a.type_abonnement, 
                       p.montant, p.date_paiement, p.methode, p.statut, p.reference
                FROM paiements p
                JOIN abonnements a ON p.abonnement_id = a.id
                JOIN clients c ON a.client_id = c.id
            '''
            
            params = []
            
            # Application du filtre de recherche
            search_term = self.search_paiement_var.get().strip()
            if search_term:
                query += ''' WHERE (c.nom LIKE ? OR c.prenom LIKE ? OR a.type_abonnement LIKE ? 
                            OR p.methode LIKE ? OR p.statut LIKE ? OR p.reference LIKE ?)'''
                search_pattern = f'%{search_term}%'
                params = [search_pattern] * 6
            
            query += ' ORDER BY p.date_paiement DESC'
            
            self.cursor.execute(query, params)
            
            for paiement in self.cursor.fetchall():
                # Colorer les lignes selon le statut
                tags = ()
                if paiement[6] == 'payé':
                    tags = ('paye',)
                elif paiement[6] == 'échec':
                    tags = ('echec',)
                elif paiement[6] == 'en attente':
                    tags = ('attente',)
                
                self.paiement_tree.insert('', tk.END, values=paiement, tags=tags)
            
            # Configuration des couleurs
            self.paiement_tree.tag_configure('paye', background='#d4edda')
            self.paiement_tree.tag_configure('echec', background='#f8d7da')
            self.paiement_tree.tag_configure('attente', background='#fff3cd')
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur chargement paiements: {str(e)}")

    def filtrer_paiements(self, event=None):
        """Filtrer les paiements selon la recherche"""
        self.charger_paiements()

    def afficher_stats_paiements(self):
        """Afficher les statistiques des paiements"""
        try:
            # Total des paiements
            self.cursor.execute("SELECT COUNT(*), SUM(montant) FROM paiements WHERE statut = 'payé'")
            total_payes, total_montant = self.cursor.fetchone()
            total_montant = total_montant or 0
            
            # Paiements du mois
            mois_courant = datetime.now().strftime("%Y-%m")
            self.cursor.execute('''
                SELECT COUNT(*), SUM(montant) FROM paiements 
                WHERE statut = 'payé' AND strftime('%Y-%m', date_paiement) = ?
            ''', (mois_courant,))
            mois_payes, mois_montant = self.cursor.fetchone()
            mois_montant = mois_montant or 0
            
            # En attente
            self.cursor.execute("SELECT COUNT(*) FROM paiements WHERE statut = 'en attente'")
            en_attente = self.cursor.fetchone()[0]
            
            # Échecs
            self.cursor.execute("SELECT COUNT(*) FROM paiements WHERE statut = 'échec'")
            echecs = self.cursor.fetchone()[0]
            
            stats_text = f"""
            • Total payés: {total_payes} (€{total_montant:.2f})
            • Ce mois: {mois_payes} (€{mois_montant:.2f})
            • En attente: {en_attente}
            • Échecs: {echecs}
            """
            
            self.stats_label.config(text=stats_text)
            
        except Exception as e:
            print(f"Erreur calcul stats paiements: {e}")

    def afficher_menu_contextuel_paiement(self, event):
        """Afficher le menu contextuel pour les paiements"""
        try:
            item = self.paiement_tree.identify_row(event.y)
            if item:
                self.paiement_tree.selection_set(item)
                self.menu_contextuel_paiement.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"Erreur menu contextuel: {e}")

    def marquer_paye(self):
        """Marquer un paiement comme payé"""
        selection = self.paiement_tree.selection()
        if not selection:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement")
            return
        
        item = selection[0]
        paiement_id = self.paiement_tree.item(item, 'values')[0]
        
        try:
            self.cursor.execute('''
                UPDATE paiements SET statut = 'payé' WHERE id = ?
            ''', (paiement_id,))
            self.conn.commit()
            
            self.log_audit('MODIFICATION_PAIEMENT', 'paiements', paiement_id, "Statut changé à 'payé'")
            
            messagebox.showinfo("Succès", "Paiement marqué comme payé")
            self.charger_paiements()
            self.afficher_stats_paiements()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur mise à jour: {str(e)}")

    def supprimer_paiement(self):
        """Supprimer un paiement"""
        selection = self.paiement_tree.selection()
        if not selection:
            messagebox.showwarning("Avertissement", "Veuillez sélectionner un paiement")
            return
        
        item = selection[0]
        paiement_id = self.paiement_tree.item(item, 'values')[0]
        client = self.paiement_tree.item(item, 'values')[1]
        montant = self.paiement_tree.item(item, 'values')[3]
        
        if messagebox.askyesno("Confirmation", f"Supprimer le paiement de {montant}€ pour {client} ?"):
            try:
                self.cursor.execute('DELETE FROM paiements WHERE id = ?', (paiement_id,))
                self.conn.commit()
                
                self.log_audit('SUPPRESSION_PAIEMENT', 'paiements', paiement_id, f"Paiement {montant}€ supprimé")
                
                messagebox.showinfo("Succès", "Paiement supprimé")
                self.charger_paiements()
                self.afficher_stats_paiements()
                
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur suppression: {str(e)}")

    def importer_paiements_csv(self):
        """Importer des paiements depuis un fichier CSV COMPLET"""
        filename = filedialog.askopenfilename(
            title="Sélectionner un fichier CSV",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                paiements_importes = 0
                erreurs = 0
                
                for ligne in reader:
                    try:
                        # Validation des données requises
                        required_fields = ['abonnement_id', 'montant', 'date_paiement', 'methode', 'statut']
                        if not all(field in ligne for field in required_fields):
                            erreurs += 1
                            continue
                        
                        # Vérifier que l'abonnement existe
                        self.cursor.execute("SELECT id FROM abonnements WHERE id = ?", (ligne['abonnement_id'],))
                        if not self.cursor.fetchone():
                            erreurs += 1
                            continue
                        
                        # Insérer le paiement
                        self.cursor.execute('''
                            INSERT INTO paiements (abonnement_id, montant, date_paiement, methode, statut, reference)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            ligne['abonnement_id'],
                            float(ligne['montant']),
                            ligne['date_paiement'],
                            ligne['methode'],
                            ligne['statut'],
                            ligne.get('reference', '')
                        ))
                        
                        paiements_importes += 1
                        
                    except (ValueError, KeyError) as e:
                        erreurs += 1
                        print(f"Erreur ligne {reader.line_num}: {e}")
                
                self.conn.commit()
                
                # Logger l'import
                self.log_audit('IMPORT_PAIEMENTS', 'paiements', 0, 
                              f"Import CSV: {paiements_importes} paiements importés, {erreurs} erreurs")
                
                messagebox.showinfo("Import terminé", 
                                  f"Paiements importés: {paiements_importes}\nErreurs: {erreurs}")
                
                self.charger_paiements()
                self.afficher_stats_paiements()
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'import: {str(e)}")

    def afficher_gestion_relances(self):
        """Afficher la gestion des relances"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="📧 GESTION DES RELANCES", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10)
        
        # Notebook pour les onglets
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Onglet Templates
        templates_frame = ttk.Frame(notebook)
        notebook.add(templates_frame, text="Templates")
        
        # Onglet Historique
        historique_frame = ttk.Frame(notebook)
        notebook.add(historique_frame, text="Historique")
        
        # Onglet Configuration SMTP
        smtp_frame = ttk.Frame(notebook)
        notebook.add(smtp_frame, text="Configuration SMTP")
        
        self.content_frame.rowconfigure(1, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        
        # Configurer chaque onglet
        self.configurer_onglet_templates(templates_frame)
        self.configurer_onglet_historique(historique_frame)
        self.configurer_onglet_smtp(smtp_frame)

    def configurer_onglet_templates(self, parent):
        """Configurer l'onglet des templates de relance"""
        # Boutons d'action
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(action_frame, text="➕ Nouveau template",
                  command=self.ajouter_template).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="✏️ Modifier",
                  command=self.modifier_template).grid(row=0, column=1, padx=5)
        
        # Treeview des templates
        columns = ['ID', 'Nom', 'Type', 'Jours', 'Sujet', 'Actif']
        self.template_tree = ttk.Treeview(parent, columns=columns, show='headings')
        
        for col in columns:
            self.template_tree.heading(col, text=col)
            self.template_tree.column(col, width=120)
        
        self.template_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.charger_templates()

    def charger_templates(self):
        """Charger la liste des templates"""
        try:
            for item in self.template_tree.get_children():
                self.template_tree.delete(item)
            
            self.cursor.execute('SELECT * FROM templates_relances ORDER BY jours_avant')
            
            for template in self.cursor.fetchall():
                actif = "Oui" if template[6] else "Non"
                self.template_tree.insert('', tk.END, values=(
                    template[0], template[1], template[2], template[3], 
                    template[4][:50] + "...", actif
                ))
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur chargement templates: {str(e)}")

    def ajouter_template(self):
        """Ajouter un nouveau template de relance"""
        # Implémentation simplifiée
        messagebox.showinfo("Info", "Fonctionnalité d'ajout de template à implémenter")

    def modifier_template(self):
        """Modifier un template existant"""
        messagebox.showinfo("Info", "Fonctionnalité de modification de template à implémenter")

    def configurer_onglet_historique(self, parent):
        """Configurer l'onglet historique des relances"""
        # Treeview de l'historique
        columns = ['ID', 'Client', 'Template', 'Date', 'Statut']
        self.historique_tree = ttk.Treeview(parent, columns=columns, show='headings')
        
        for col in columns:
            self.historique_tree.heading(col, text=col)
            self.historique_tree.column(col, width=150)
        
        self.historique_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.charger_historique_relances()

    def charger_historique_relances(self):
        """Charger l'historique des relances"""
        try:
            for item in self.historique_tree.get_children():
                self.historique_tree.delete(item)
            
            self.cursor.execute('''
                SELECT h.id, c.nom || ' ' || c.prenom, t.nom, h.date_envoi, h.statut
                FROM historique_relances h
                JOIN abonnements a ON h.abonnement_id = a.id
                JOIN clients c ON a.client_id = c.id
                JOIN templates_relances t ON h.template_id = t.id
                ORDER BY h.date_envoi DESC
            ''')
            
            for relance in self.cursor.fetchall():
                self.historique_tree.insert('', tk.END, values=relance)
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur chargement historique: {str(e)}")

    def configurer_onglet_smtp(self, parent):
        """Configurer l'onglet configuration SMTP"""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Champs de configuration SMTP
        fields = [
            ("Serveur SMTP:", 'smtp_host'),
            ("Port:", 'smtp_port'),
            ("Utilisateur:", 'smtp_user'),
            ("Mot de passe:", 'smtp_password')
        ]
        
        for i, (label, config_key) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=30)
            entry.insert(0, str(self.config.get(config_key, '')))
            entry.grid(row=i, column=1, pady=5, padx=10)
            
            # Sauvegarder la valeur quand elle change
            if config_key == 'smtp_password':
                entry.config(show='*')
            entry.bind('<FocusOut>', 
                      lambda e, key=config_key: self.sauvegarder_config_smtp(key, e.widget.get()))
        
        # Bouton test
        ttk.Button(form_frame, text="🧪 Tester la connexion",
                  command=self.tester_connexion_smtp).grid(row=len(fields), column=0, columnspan=2, pady=20)

    def sauvegarder_config_smtp(self, key, value):
        """Sauvegarder un paramètre SMTP"""
        if key == 'smtp_port':
            try:
                value = int(value)
            except ValueError:
                value = 587
        self.config[key] = value
        self.save_config()

    def tester_connexion_smtp(self):
        """Tester la connexion SMTP"""
        try:
            if not all([self.config['smtp_host'], self.config['smtp_user'], self.config['smtp_password']]):
                messagebox.showerror("Erreur", "Veuillez remplir tous les champs SMTP")
                return
            
            server = smtplib.SMTP(self.config['smtp_host'], self.config['smtp_port'])
            server.starttls()
            server.login(self.config['smtp_user'], self.config['smtp_password'])
            server.quit()
            
            messagebox.showinfo("Succès", "Connexion SMTP réussie!")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec connexion SMTP: {str(e)}")

    def afficher_dashboard(self):
        """Afficher le dashboard avec graphiques"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="📊 DASHBOARD ANALYTIQUE", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10)
        
        # Frame pour les statistiques en grille
        stats_grid = ttk.Frame(self.content_frame)
        stats_grid.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        
        # Calculer les statistiques
        stats = self.calculer_statistiques_avancees()
        
        # Afficher les KPI
        kpis = [
            ("👥 Clients actifs", stats['clients_actifs']),
            ("📈 Abonnements actifs", stats['abonnements_actifs']),
            ("💰 CA mensuel", f"€{stats['ca_mensuel']:.2f}"),
            ("🔄 Taux renouvellement", f"{stats['taux_renouvellement']:.1f}%")
        ]
        
        for i, (label, valeur) in enumerate(kpis):
            frame = ttk.Frame(stats_grid, relief='raised', padding="10")
            frame.grid(row=0, column=i, padx=10, pady=10, sticky=(tk.W, tk.E))
            
            ttk.Label(frame, text=label, font=('Arial', 10)).pack()
            ttk.Label(frame, text=str(valeur), font=('Arial', 16, 'bold')).pack()
        
        # Graphiques simples (texte pour l'instant)
        graph_frame = ttk.LabelFrame(self.content_frame, text="Évolution mensuelle", padding="15")
        graph_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10, padx=10)
        
        # Afficher l'évolution sous forme textuelle
        evolution_text = "Évolution des 6 derniers mois:\n\n"
        for mois, data in stats['evolution_mensuelle'].items():
            evolution_text += f"{mois}: {data['abonnements']} abonnements, €{data['ca']:.2f} CA\n"
        
        ttk.Label(graph_frame, text=evolution_text, justify=tk.LEFT).pack()

    def afficher_outils_avances(self):
        """Afficher les outils avancés"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="🧰 OUTILS AVANCÉS", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10)
        
        # Notebook pour les différents outils
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Onglet Archivage
        archive_frame = ttk.Frame(notebook)
        notebook.add(archive_frame, text="📦 Archivage")
        
        # Onglet Export
        export_frame = ttk.Frame(notebook)
        notebook.add(export_frame, text="💾 Export")
        
        # Onglet Tags
        tags_frame = ttk.Frame(notebook)
        notebook.add(tags_frame, text="🏷️ Tags")
        
        self.content_frame.rowconfigure(1, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        
        self.configurer_onglet_archivage(archive_frame)
        self.configurer_onglet_export(export_frame)
        self.configurer_onglet_tags(tags_frame)

    def configurer_onglet_archivage(self, parent):
        """Configurer l'onglet archivage"""
        # Configuration rétention
        config_frame = ttk.LabelFrame(parent, text="Configuration archivage automatique", padding="10")
        config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(config_frame, text="Jours avant archivage:").grid(row=0, column=0, sticky=tk.W)
        jours_var = tk.StringVar(value=str(self.config['retention_days']))
        jours_entry = ttk.Entry(config_frame, textvariable=jours_var, width=10)
        jours_entry.grid(row=0, column=1, padx=10)
        
        ttk.Button(config_frame, text="💾 Sauvegarder",
                  command=lambda: self.sauvegarder_config_archivage(jours_var.get())).grid(row=0, column=2, padx=10)
        
        # Liste des archives
        archive_tree = ttk.Treeview(parent, columns=('ID', 'Client', 'Type', 'Date fin', 'Date archivage'), show='headings')
        archive_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for col in ['ID', 'Client', 'Type', 'Date fin', 'Date archivage']:
            archive_tree.heading(col, text=col)
            archive_tree.column(col, width=120)
        
        # Charger les archives
        try:
            self.cursor.execute('''
                SELECT a.id, c.nom || ' ' || c.prenom, a.type_abonnement, a.date_fin, a.date_archivage
                FROM archive_abonnements a
                JOIN clients c ON a.client_id = c.id
                ORDER BY a.date_archivage DESC
            ''')
            
            for archive in self.cursor.fetchall():
                archive_tree.insert('', tk.END, values=archive)
                
        except Exception as e:
            print(f"Erreur chargement archives: {e}")

    def sauvegarder_config_archivage(self, jours):
        """Sauvegarder la configuration d'archivage"""
        try:
            self.config['retention_days'] = int(jours)
            self.save_config()
            messagebox.showinfo("Succès", "Configuration sauvegardée")
        except ValueError:
            messagebox.showerror("Erreur", "Veuillez entrer un nombre valide")

    def configurer_onglet_export(self, parent):
        """Configurer l'onglet export"""
        # Options d'export
        options_frame = ttk.LabelFrame(parent, text="Options d'export", padding="15")
        options_frame.pack(fill=tk.X, padx=10, pady=10)
        
        formats = [
            ("📊 CSV - Abonnements", self.exporter_csv_abonnements),
            ("📅 ICS - Calendrier", self.exporter_ics),
            ("📋 CSV - Clients", self.exporter_csv_clients),
            ("💰 CSV - Paiements", self.exporter_csv_paiements)
        ]
        
        for i, (label, command) in enumerate(formats):
            ttk.Button(options_frame, text=label, command=command).grid(
                row=i//2, column=i%2, padx=10, pady=5, sticky=tk.W+tk.E)
        
        options_frame.columnconfigure(0, weight=1)
        options_frame.columnconfigure(1, weight=1)

    def exporter_csv_abonnements(self):
        """Exporter les abonnements en CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")])
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(['ID', 'Client', 'Type', 'Date début', 'Date fin', 'Prix', 'Statut'])
                    
                    self.cursor.execute('''
                        SELECT a.id, c.nom || ' ' || c.prenom, a.type_abonnement, 
                               a.date_debut, a.date_fin, a.prix, a.statut
                        FROM abonnements a
                        JOIN clients c ON a.client_id = c.id
                    ''')
                    
                    for row in self.cursor.fetchall():
                        writer.writerow(row)
                
                messagebox.showinfo("Succès", f"Export CSV vers {filename}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur export: {str(e)}")

    def exporter_ics(self):
        """Exporter les échéances en format ICS"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".ics",
            filetypes=[("ICS files", "*.ics")])
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as file:
                    file.write("BEGIN:VCALENDAR\n")
                    file.write("VERSION:2.0\n")
                    file.write("PRODID:-//Suivi Abonnements//FR\n")
                    
                    self.cursor.execute('''
                        SELECT c.nom, c.prenom, a.type_abonnement, a.date_fin
                        FROM abonnements a
                        JOIN clients c ON a.client_id = c.id
                        WHERE a.statut = 'Actif'
                    ''')
                    
                    for nom, prenom, type_abon, date_fin in self.cursor.fetchall():
                        file.write("BEGIN:VEVENT\n")
                        file.write(f"SUMMARY:Expiration {type_abon} - {prenom} {nom}\n")
                        file.write(f"DTSTART;VALUE=DATE:{date_fin.replace('-', '')}\n")
                        file.write(f"DTEND;VALUE=DATE:{date_fin.replace('-', '')}\n")
                        file.write("END:VEVENT\n")
                    
                    file.write("END:VCALENDAR\n")
                
                messagebox.showinfo("Succès", f"Export ICS vers {filename}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur export ICS: {str(e)}")

    def exporter_csv_clients(self):
        """Exporter les clients en CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")])
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(['ID', 'Nom', 'Prénom', 'Email', 'Téléphone', 'Date Création'])
                    
                    self.cursor.execute('SELECT * FROM clients')
                    
                    for row in self.cursor.fetchall():
                        writer.writerow(row)
                
                messagebox.showinfo("Succès", f"Export clients CSV vers {filename}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur export: {str(e)}")

    def exporter_csv_paiements(self):
        """Exporter les paiements en CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")])
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(['ID', 'Abonnement ID', 'Montant', 'Date', 'Méthode', 'Statut', 'Référence'])
                    
                    self.cursor.execute('SELECT * FROM paiements')
                    
                    for row in self.cursor.fetchall():
                        writer.writerow(row)
                
                messagebox.showinfo("Succès", f"Export paiements CSV vers {filename}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur export: {str(e)}")

    def configurer_onglet_tags(self, parent):
        """Configurer l'onglet gestion des tags"""
        # Frame pour ajouter un tag
        add_frame = ttk.Frame(parent)
        add_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(add_frame, text="Nouveau tag:").grid(row=0, column=0)
        nom_tag_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=nom_tag_var).grid(row=0, column=1, padx=10)
        ttk.Button(add_frame, text="➕ Ajouter",
                  command=lambda: self.ajouter_tag(nom_tag_var.get())).grid(row=0, column=2)
        
        # Liste des tags
        self.tag_tree = ttk.Treeview(parent, columns=('ID', 'Nom', 'Couleur'), show='headings')
        self.tag_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for col in ['ID', 'Nom', 'Couleur']:
            self.tag_tree.heading(col, text=col)
            self.tag_tree.column(col, width=100)
        
        self.charger_tags()

    def ajouter_tag(self, nom):
        """Ajouter un nouveau tag"""
        if nom:
            try:
                self.cursor.execute('INSERT OR IGNORE INTO tags (nom) VALUES (?)', (nom,))
                self.conn.commit()
                self.charger_tags()
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur ajout tag: {str(e)}")

    def charger_tags(self):
        """Charger la liste des tags"""
        try:
            for item in self.tag_tree.get_children():
                self.tag_tree.delete(item)
            
            self.cursor.execute('SELECT * FROM tags ORDER BY nom')
            
            for tag in self.cursor.fetchall():
                self.tag_tree.insert('', tk.END, values=tag)
                
        except Exception as e:
            print(f"Erreur chargement tags: {e}")

    def afficher_aide(self):
        """Afficher la section aide"""
        self.clear_content()
        
        ttk.Label(self.content_frame, text="❓ AIDE & INFORMATIONS", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10)
        
        # Informations sur l'application
        info_text = """
        Application de Suivi des Abonnements - Version Avancée
        
        Version: 1.2
        Développeur: Antratia's team
        Date: 2025
        
        Nouvelles fonctionnalités:
        • Archivage automatique avec politique de rétention
        • Système de relances automatiques par email
        • Renouvellement automatique
        • Gestion des paiements
        • Dashboard analytique avancé
        • Export multiples (CSV, ICS)
        • Système de tags et catégories
        
        Pour toute assistance, consultez la documentation.
        """
        
        ttk.Label(self.content_frame, text=info_text, justify=tk.LEFT,
                 font=('Arial', 11)).grid(row=1, column=0, pady=20)

    def actualiser_donnees(self):
        """Actualiser toutes les données (version étendue)"""
        try:
            # Mettre à jour les statuts des abonnements
            date_actuelle = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute('''
                UPDATE abonnements 
                SET statut = 'Expiré' 
                WHERE date_fin < ? AND statut = 'Actif'
            ''', (date_actuelle,))
            
            self.cursor.execute('''
                UPDATE abonnements 
                SET statut = 'Actif' 
                WHERE date_fin >= ? AND statut = 'Expiré'
            ''', (date_actuelle,))
            
            # Gérer le renouvellement automatique
            self.gerer_renouvellement_automatique()
            
            self.conn.commit()
            
            # Recharger les données affichées
            if hasattr(self, 'client_tree'):
                self.charger_clients()
            if hasattr(self, 'abonnement_tree'):
                self.charger_abonnements()
            if hasattr(self, 'paiement_tree'):
                self.charger_paiements()
                
            messagebox.showinfo("Actualisation", "Toutes les données ont été actualisées avec succès")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'actualisation: {str(e)}")

    def gerer_renouvellement_automatique(self):
        """Gérer le renouvellement automatique des abonnements"""
        try:
            # Utiliser une connexion locale pour le traitement
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Récupérer les abonnements avec auto-renew qui viennent d'expirer
            date_actuelle = datetime.now().strftime("%Y-%m-%d")
            cur.execute('''
                SELECT * FROM abonnements 
                WHERE auto_renew = 1 AND statut = 'Expiré' AND date_fin = ?
            ''', (date_actuelle,))
            
            abonnements_a_renouveler = cur.fetchall()
            
            for abonnement in abonnements_a_renouveler:
                # Calculer la nouvelle date de fin
                ancienne_date_fin = datetime.strptime(abonnement[4], "%Y-%m-%d")
                type_abonnement = abonnement[2]
                
                if type_abonnement == 'Mensuel':
                    nouvelle_date_fin = ancienne_date_fin + timedelta(days=30)
                elif type_abonnement == 'Trimestriel':
                    nouvelle_date_fin = ancienne_date_fin + timedelta(days=90)
                elif type_abonnement == 'Semestriel':
                    nouvelle_date_fin = ancienne_date_fin + timedelta(days=180)
                elif type_abonnement == 'Annuel':
                    nouvelle_date_fin = ancienne_date_fin + timedelta(days=365)
                else:
                    continue  # Type personnalisé, ne pas renouveler automatiquement
                
                # Mettre à jour l'abonnement
                cur.execute('''
                    UPDATE abonnements 
                    SET date_fin = ?, statut = 'Actif'
                    WHERE id = ?
                ''', (nouvelle_date_fin.strftime("%Y-%m-%d"), abonnement[0]))
                
                # Logger le renouvellement (log_audit utilise sa propre connexion)
                self.log_audit('RENOUVELLEMENT_AUTO', 'abonnements', abonnement[0],
                              f"Renouvellement automatique jusqu'au {nouvelle_date_fin.strftime('%Y-%m-%d')}")
            
            if abonnements_a_renouveler:
                conn.commit()
                print(f"{len(abonnements_a_renouveler)} abonnement(s) renouvelé(s) automatiquement")
            conn.close()
                
        except Exception as e:
            print(f"Erreur renouvellement automatique: {e}")

    def __del__(self):
        """Fermer la connexion à la base de données"""
        if hasattr(self, 'conn'):
            try:
                self.conn.close()
            except Exception:
                pass

def main():
    """Fonction principale"""
    root = tk.Tk()
    app = ApplicationSuiviAbonnements(root)
    root.mainloop()

if __name__ == "__main__":
    main()