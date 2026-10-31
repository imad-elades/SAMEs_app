import os
import sqlite3
from pathlib import Path
from passlib.hash import bcrypt

DB_PATH = Path(__file__).parent / 'sames.db'
ASSETS_DIR = Path(__file__).parent / 'assets'
ICONS_DIR = Path(__file__).parent / 'icons'

def init_db():
    # Créer le dossier assets s'il n'existe pas
    ASSETS_DIR.mkdir(exist_ok=True)
    # Créer le dossier icons s'il n'existe pas
    ICONS_DIR.mkdir(exist_ok=True)
    
    # Connexion à la base de données
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Réinitialiser les tables pour reprendre la nouvelle structure
        cursor.execute("DROP TABLE IF EXISTS alerts")
        cursor.execute("DROP TABLE IF EXISTS anomaly_types")
        cursor.execute("DROP TABLE IF EXISTS users")
        
        # Création de la table users
        cursor.execute('''
            CREATE TABLE users (
                matricule TEXT PRIMARY KEY,
                password TEXT,
                role TEXT CHECK(role IN ('employee','technician'))
            )
        ''')
        
        # Création de la table alerts
        cursor.execute('''
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_matricule TEXT,
                photo_path TEXT,
                alert_type TEXT,
                send_date DATETIME,
                validation_date DATETIME NULL,
                status TEXT,
                comment TEXT,
                technician_id TEXT NULL,
                FOREIGN KEY (user_matricule) REFERENCES users (matricule)
            )
        ''')
        
        # Liste des types d'anomalies
        anomaly_types = [
            'Bruit',
            'Vibration',
            'Chaleur',
            'Fuite',
            'Odeur',
            'Coupure',
            'Usure',
            'Déformation',
            'Autre'
        ]
        
        # Création de la table anomaly_types
        cursor.execute('''
            CREATE TABLE anomaly_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                image_path TEXT
            )
        ''')
        
        # Insertion des types d'anomalies
        for anomaly_type in anomaly_types:
            cursor.execute('''
                INSERT OR IGNORE INTO anomaly_types (name, description, image_path)
                VALUES (?, ?, ?)
            ''', (anomaly_type, f"Description de {anomaly_type}", f"icons/{anomaly_type.lower()}.png"))
        
        # Insertion des utilisateurs de test si la table est vide
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Ajouter quelques utilisateurs de test
            users = [
                ('EMP001', None, 'employee'),
                ('EMP002', None, 'employee'),
                ('TECH001', bcrypt.hash('tech123'), 'technician'),
                ('TECH002', bcrypt.hash('tech456'), 'technician')
            ]
            cursor.executemany('INSERT OR IGNORE INTO users (matricule, password, role) VALUES (?, ?, ?)', users)
        
        # Valider les changements
        conn.commit()

if __name__ == '__main__':
    init_db()
