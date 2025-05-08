import sqlite3
import os
from PIL import Image
from passlib.hash import bcrypt

DB_PATH = 'sames.db'

def init_db():
    # Check if database already exists
    if os.path.exists(DB_PATH):
        return  # Skip initialization to preserve existing data
    
    os.makedirs('icons', exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            matricule TEXT PRIMARY KEY,
            password TEXT,
            role TEXT NOT NULL CHECK(role IN ('employee', 'technician', 'admin'))
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS anomaly_types (
            name TEXT PRIMARY KEY,
            description TEXT,
            icon_name TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_matricule TEXT,
            photo_path TEXT,
            alert_type TEXT,
            description TEXT,
            send_date DATETIME,
            validation_date DATETIME,
            status TEXT CHECK(status IN ('En attente', 'Validé', 'Rejeté')),
            comment TEXT,
            technician_id TEXT,
            FOREIGN KEY(user_matricule) REFERENCES users(matricule),
            FOREIGN KEY(alert_type) REFERENCES anomaly_types(name),
            FOREIGN KEY(technician_id) REFERENCES users(matricule)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS reset_codes (
            matricule TEXT,
            code TEXT NOT NULL,
            expiry_date DATETIME NOT NULL,
            PRIMARY KEY(matricule),
            FOREIGN KEY(matricule) REFERENCES users(matricule)
        )''')
        
        # Données de test
        anomaly_types = [
            ('Bruit', 'Bruit anormal dans la machine', 'bruit.png'),
            ('Fuite', 'Fuite de liquide ou de gaz', 'fuite.png'),
            ('Vibration', 'Vibration excessive', 'vibration.png'),
            ('Surchauffe', 'Température anormale', 'surchauffe.png')
        ]
        
        for name, description, icon_name in anomaly_types:
            c.execute('''INSERT OR IGNORE INTO anomaly_types (name, description, icon_name) 
                        VALUES (?, ?, ?)''', (name, description, icon_name))
            icon_path = os.path.join('icons', icon_name)
            if not os.path.exists(icon_path):
                img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                img.save(icon_path)
        
        users = [
            ('EMP001', None, 'employee'),  # No password for employees
            ('EMP002', None, 'employee'),
            ('TECH001', bcrypt.hash('tech123'), 'technician'),
            ('TECH002', bcrypt.hash('tech123'), 'technician'),
            ('ADMIN001', bcrypt.hash('admin123'), 'admin')
        ]
        
        for matricule, password, role in users:
            c.execute('''INSERT OR IGNORE INTO users (matricule, password, role) 
                        VALUES (?, ?, ?)''', (matricule, password, role))
        
        conn.commit()

if __name__ == '__main__':
    init_db()