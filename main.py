from datetime import datetime
import sqlite3
from passlib.hash import bcrypt
from init_db import init_db, DB_PATH
import os
import cv2
from kivy.graphics.texture import Texture
from kivy.uix.image import Image, AsyncImage
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.utils import get_color_from_hex
from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDFillRoundFlatIconButton, MDFlatButton, MDIconButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.icon_definitions import md_icons
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, OneLineIconListItem
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.textfield import MDTextField
import re
import logging

# Configuration du logging
logging.basicConfig(
    filename='sames.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Logger:
    @staticmethod
    def log_action(user_matricule, action, details=None):
        """Journalise une action utilisateur"""
        message = f"User {user_matricule}: {action}"
        if details:
            message += f" - {details}"
        logging.info(message)

# init_db importé depuis init_db.py

class InputValidator:
    @staticmethod
    def validate_matricule(matricule):
        """Valide le format du matricule"""
        if not matricule:
            return False, "Le matricule ne peut pas être vide"
        if not re.match(r'^[A-Z0-9]{4,10}$', matricule):
            return False, "Le matricule doit contenir entre 4 et 10 caractères alphanumériques"
        return True, ""

    @staticmethod
    def validate_password(password):
        """Valide le format du mot de passe"""
        if not password:
            return False, "Le mot de passe ne peut pas être vide"
        if len(password) < 8:
            return False, "Le mot de passe doit contenir au moins 8 caractères"
        if not re.search(r'[A-Z]', password):
            return False, "Le mot de passe doit contenir au moins une majuscule"
        if not re.search(r'[a-z]', password):
            return False, "Le mot de passe doit contenir au moins une minuscule"
        if not re.search(r'[0-9]', password):
            return False, "Le mot de passe doit contenir au moins un chiffre"
        return True, ""

class NotificationManager:
    @staticmethod
    def show_notification(text, duration=3):
        """Affiche une notification à l'utilisateur"""
        snackbar = Snackbar(
            text=text,
            duration=duration,
            bg_color=get_color_from_hex('#4CAF50'),
            text_color=get_color_from_hex('#FFFFFF')
        )
        snackbar.open()

class BaseScreen(MDScreen):
    """Classe de base avec des méthodes communes"""
    def show_error_dialog(self, text):
        dialog = MDDialog(
            title="Erreur",
            text=text,
            buttons=[
                MDFlatButton(
                    text="OK",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
        
    def show_success_notification(self, text):
        """Affiche une notification de succès"""
        NotificationManager.show_notification(text)

class LoginScreen(BaseScreen):
    def verify_login(self):
        matricule = self.ids.matricule.text.strip()
        password = self.ids.password.text.strip() if hasattr(self.ids, 'password') else ''
        
        # Validation des entrées
        is_valid, error_msg = InputValidator.validate_matricule(matricule)
        if not is_valid:
            Logger.log_action(matricule, "Login failed", f"Invalid matricule format: {error_msg}")
            self.show_error_dialog(error_msg)
            return
            
        if hasattr(self.ids, 'password'):
            is_valid, error_msg = InputValidator.validate_password(password)
            if not is_valid:
                Logger.log_action(matricule, "Login failed", f"Invalid password format: {error_msg}")
                self.show_error_dialog(error_msg)
                return

        # Vérifier en base
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT matricule, password, role FROM users WHERE matricule=?", (matricule,))
            user = c.fetchone()
            
        # Authentification
        if not user or user[2] not in ('employee','technician'):
            Logger.log_action(matricule, "Login failed", "Invalid credentials")
            self.show_error_dialog("Identifiants invalides")
            return
            
        if user[2] == 'technician':
            stored = user[1] or ''
            try:
                ok = bcrypt.verify(password, stored)
            except ValueError:
                ok = (password == stored)
                if ok:
                    # Migration: rehash old plaintext password
                    new_hash = bcrypt.hash(password)
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        c.execute("UPDATE users SET password=? WHERE matricule=?", (new_hash, matricule))
                    Logger.log_action(matricule, "Password migrated to bcrypt")
            if not ok:
                Logger.log_action(matricule, "Login failed", "Invalid password")
                self.show_error_dialog("Identifiants invalides")
                return
                
        app = MDApp.get_running_app()
        app.current_user = {'matricule': user[0], 'role': user[2]}
        app.reset_timeout()
        
        Logger.log_action(matricule, f"Login successful as {user[2]}")
        self.show_success_notification(f"Bienvenue {user[0]} !")

        # Naviguer
        if user[2] == 'employee':
            self.manager.current = 'employee_camera'
        else:
            self.manager.current = 'technician_dashboard'

class EmployeeCameraScreen(BaseScreen):
    def on_enter(self):
        self.capture = None
        self.camera_active = False
        self.preview = Image()
        self.ids.camera_layout.add_widget(self.preview)
        Clock.schedule_once(self.start_camera, 1)  # Délai pour laisser l'interface se charger

    def on_leave(self):
        self.stop_camera()

    def start_camera(self, dt):
        # Essayer plusieurs indices de caméra
        for camera_index in range(2):  # Essayer les caméras 0 et 1
            self.capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # Utiliser DirectShow
            if self.capture.isOpened():
                # Définir une résolution plus basse pour de meilleures performances
                self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera_active = True
                Clock.schedule_interval(self.update_camera, 1.0 / 30.0)
                return
        
        # Si aucune caméra n'est trouvée
        self.show_error_dialog("Impossible d'accéder à la caméra")

    def stop_camera(self):
        if self.camera_active:
            Clock.unschedule(self.update_camera)
            if self.capture:
                self.capture.release()
            self.camera_active = False

    def update_camera(self, dt):
        if self.camera_active:
            ret, frame = self.capture.read()
            if ret:
                # Convertir BGR en RGB
                buf = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 0).tobytes()
                texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='rgb')
                texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                self.preview.texture = texture
                return True
        return False

    def capture_photo(self):
        if not self.camera_active:
            self.show_error_dialog("La caméra n'est pas active")
            return

        ret, frame = self.capture.read()
        if ret:
            # Créer le dossier assets s'il n'existe pas
            if not os.path.exists('assets'):
                os.makedirs('assets')

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join('assets', f'alert_{timestamp}.jpg')
            
            # Sauvegarder l'image
            cv2.imwrite(filename, frame)
            
            app = MDApp.get_running_app()
            app.current_photo = filename
            
            # Logger l'action
            Logger.log_action(
                app.current_user['matricule'],
                "Photo captured",
                f"Saved as {filename}"
            )
            
            self.show_success_notification("Photo capturée avec succès !")
            
            self.stop_camera()
            self.manager.current = 'alert_type'
        else:
            Logger.log_action(
                MDApp.get_running_app().current_user['matricule'],
                "Photo capture failed",
                "Camera error"
            )
            self.show_error_dialog("Erreur lors de la capture")

class AlertTypeScreen(BaseScreen):
    anomaly_types = [
        {'name': 'Bruit', 'icon': 'volume-high', 'description': 'Sons anormaux'},
        {'name': 'Vibration', 'icon': 'vibrate', 'description': 'Secousses ou tremblements'},
        {'name': 'Chaleur', 'icon': 'thermometer-high', 'description': 'Température élevée'},
        {'name': 'Fuite', 'icon': 'water', 'description': 'Fuite de liquide'},
        {'name': 'Odeur', 'icon': 'scent', 'description': 'Odeur inhabituelle'},
        {'name': 'Coupure', 'icon': 'power-plug-off', 'description': 'Arrêt ou coupure'},
        {'name': 'Usure', 'icon': 'cog-off', 'description': 'Usure anormale'},
        {'name': 'Déformation', 'icon': 'shape', 'description': 'Déformation visible'},
        {'name': 'Autre', 'icon': 'help-circle', 'description': 'Autre problème'}
    ]
    
    def on_enter(self):
        # Nettoyer la grille existante
        grid = self.ids.type_grid
        grid.clear_widgets()
        
        # Ajouter les cartes pour chaque type d'anomalie
        for anomaly in self.anomaly_types:
            self.add_type_card(anomaly)
    
    def add_type_card(self, anomaly):
        # Création de la carte
        card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(200),
            md_bg_color=get_color_from_hex('#424242'),
            radius=[dp(10)],
            elevation=3,
            padding=dp(10),
            spacing=dp(5)
        )
        
        # Icône de l'anomalie
        icon_box = MDBoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(120),
            padding=dp(10)
        )
        
        app = MDApp.get_running_app()
        icon = MDIconButton(
            icon=anomaly['icon'],
            icon_size=dp(64),
            pos_hint={'center_x': 0.5},
            theme_icon_color="Custom",
            icon_color=app.theme_cls.primary_color
        )
        
        icon_box.add_widget(icon)
        
        # Nom de l'anomalie
        name_label = MDLabel(
            text=anomaly['name'],
            halign='center',
            font_style='H6',
            size_hint_y=None,
            height=dp(30)
        )
        
        # Description de l'anomalie
        desc_label = MDLabel(
            text=anomaly['description'],
            halign='center',
            theme_text_color="Secondary",
            font_style='Caption',
            size_hint_y=None,
            height=dp(20)
        )
        
        # Assemblage de la carte
        card.add_widget(icon_box)
        card.add_widget(name_label)
        card.add_widget(desc_label)
        
        # Ajout du comportement tactile
        card.bind(on_release=lambda x, name=anomaly['name']: self.select_type(name))
        
        # Ajout de la carte à la grille
        self.ids.type_grid.add_widget(card)
    
    def select_type(self, type_name):
        app = MDApp.get_running_app()
        if self.check_daily_alert():
            self.show_error_dialog("Vous avez déjà envoyé une alerte aujourd'hui")
            return
            
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''INSERT INTO alerts 
                    (user_matricule, photo_path, alert_type, send_date, status)
                    VALUES (?, ?, ?, ?, ?)''',
                 (app.current_user['matricule'],
                  app.current_photo,
                  type_name,
                  datetime.now(),
                  'En attente'))
                  
        conn.commit()
        conn.close()
        
        self.manager.current = 'alert_status'
    
    def check_daily_alert(self):
        app = MDApp.get_running_app()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        today = datetime.now().date()
        c.execute('''SELECT COUNT(*) FROM alerts 
                    WHERE user_matricule=? 
                    AND date(send_date)=date(?)''',
                 (app.current_user['matricule'], today))
                 
        count = c.fetchone()[0]
        conn.close()
        return count > 0

class AlertStatusScreen(BaseScreen):
    def on_enter(self):
        self.update_status()
        Clock.schedule_interval(self.update_status, 30)  # Update every 30 seconds
    
    def on_leave(self):
        Clock.unschedule(self.update_status)
    
    def update_status(self, *args):
        app = MDApp.get_running_app()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT status FROM alerts 
                    WHERE user_matricule=?
                    ORDER BY send_date DESC LIMIT 1''',
                 (app.current_user['matricule'],))
                 
        status = c.fetchone()
        conn.close()
        
        if status:
            self.ids.status_label.text = f"Statut: {status[0]}"

class TechnicianDashboardScreen(BaseScreen):
    def on_enter(self):
        self.load_alerts()
    
    def load_alerts(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''SELECT * FROM alerts 
                    WHERE status='En attente'
                    ORDER BY send_date DESC''')
                    
        alerts = c.fetchall()
        conn.close()
        
        # Update UI with alerts
        self.ids.alerts_grid.clear_widgets()
        for alert in alerts:
            self.add_alert_card(alert)

    def add_alert_card(self, alert):
        app = MDApp.get_running_app()
        # Sécurité sur les champs
        alert_id = alert[0]
        user_matricule = alert[1] if alert[1] else "?"
        photo_path = alert[2]
        alert_type = alert[3] if alert[3] else "?"
        send_date = alert[4].split('.')[0] if alert[4] else "?"
        status = alert[5] if alert[5] else "En attente"
        comment = alert[6] if len(alert) > 6 and alert[6] else None
        
        # Création de la carte
        card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(420),
            md_bg_color=get_color_from_hex('#424242'),
            radius=[dp(10)],
            elevation=3,
            padding=dp(10)
        )

        # En-tête avec l'ID et la date
        header = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40)
        )
        header.add_widget(MDLabel(
            text=f"Alerte #{alert_id}",
            theme_text_color="Primary",
            font_style="H6"
        ))
        date_label = MDLabel(
            text=send_date,
            theme_text_color="Secondary",
            halign='right'
        )
        header.add_widget(date_label)

        # Contenu principal
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(220)
        )
        # Type d'anomalie avec icône
        type_box = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40)
        )
        icon = MDIconButton(
            icon=self.get_alert_icon(alert_type),
            theme_text_color="Custom",
            text_color=app.theme_cls.primary_color
        )
        type_box.add_widget(icon)
        type_box.add_widget(MDLabel(
            text=f"Type: {alert_type}",
            theme_text_color="Primary"
        ))
        content.add_widget(type_box)
        # Séparateur
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=get_color_from_hex('#666666'), padding=[dp(10), 0]))
        # Status avec couleur
        status_colors = {
            'Validé': (0, 1, 0, 1),
            'Rejeté': (1, 0, 0, 1),
            'En attente': app.theme_cls.primary_color
        }
        status_color = status_colors.get(status, app.theme_cls.primary_color)
        status_label = MDLabel(
            text=f"Statut: {status}",
            theme_text_color="Custom",
            text_color=status_color,
            font_style="Subtitle2"
        )
        content.add_widget(status_label)
        # Employé
        content.add_widget(MDLabel(
            text=f"Employé: {user_matricule}",
            theme_text_color="Secondary"
        ))
        # Séparateur
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=get_color_from_hex('#666666'), padding=[dp(10), 0]))
        # Commentaire (si présent)
        if comment:
            comment_box = MDBoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=dp(80),
                padding=[0, dp(10)]
            )
            comment_box.add_widget(MDLabel(
                text="Commentaire du technicien:",
                theme_text_color="Secondary",
                font_style="Caption",
                size_hint_y=None,
                height=dp(20)
            ))
            comment_box.add_widget(MDLabel(
                text=comment,
                theme_text_color="Primary",
                size_hint_y=None,
                height=dp(60)
            ))
            content.add_widget(comment_box)
        # Bouton pour voir l'image de l'anomalie
        image_button = MDFillRoundFlatIconButton(
            text="Voir l'image",
            icon="image",
            on_release=lambda x, path=photo_path: self.show_image_popup(path)
        )
        content.add_widget(image_button)
        # Boutons d'action
        buttons = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(48),
            spacing=dp(20),
            padding=[dp(10), 0]
        )
        if status == 'En attente':
            validate_button = MDFillRoundFlatIconButton(
                text="Valider",
                icon="check",
                on_release=lambda x, alert_id=alert_id: self.validate_alert(alert_id)
            )
            reject_button = MDFillRoundFlatIconButton(
                text="Rejeter",
                icon="close",
                theme_text_color="Custom",
                text_color=(0.8, 0, 0, 1),
                md_bg_color=(0.9, 0.9, 0.9, 1),
                on_release=lambda x, alert_id=alert_id: self.reject_alert(alert_id)
            )
            buttons.add_widget(validate_button)
            buttons.add_widget(reject_button)
        # Assemblage final de la carte
        card.add_widget(header)
        card.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=get_color_from_hex('#666666'), padding=[dp(10), 0]))
        card.add_widget(content)
        if status == 'En attente':
            card.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=get_color_from_hex('#666666'), padding=[dp(10), 0]))
            card.add_widget(buttons)
        self.ids.alerts_grid.add_widget(card)
    
    def get_alert_icon(self, alert_type):
        icons = {
            'Fuite': 'water',
            'Usure': 'wrench',
            'Déformation': 'alert-octagon'
        }
        return icons.get(alert_type, 'help-circle')

    def show_image_popup(self, photo_path):
        from kivymd.uix.dialog import MDDialog
        from kivy.uix.image import Image
        from kivy.metrics import dp
        import os
        app = MDApp.get_running_app()
        if not photo_path or not os.path.exists(photo_path):
            dialog = MDDialog(
                title="Image non disponible",
                text="Aucune image n'est associée à cette alerte ou le fichier est manquant.",
                size_hint=(0.8, None),
                height=dp(200)
            )
            dialog.open()
            return
        image_widget = Image(source=photo_path, allow_stretch=True, keep_ratio=True, size_hint=(1, None), height=dp(350))
        dialog = MDDialog(
            title="Photo de l'anomalie",
            type="custom",
            content_cls=image_widget,
            size_hint=(0.8, None),
            height=dp(420)
        )
        dialog.open()

    def show_comment_dialog(self, alert_id, action):
        app = MDApp.get_running_app()
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(20),
            size_hint_y=None,
            height=dp(200)
        )
        
        comment_field = MDTextField(
            hint_text="Commentaire",
            mode="rectangle",
            multiline=True,
            size_hint=(1, None),
            height=dp(100)
        )
        
        content.add_widget(MDLabel(
            text="Ajouter un commentaire",
            theme_text_color="Primary",
            font_style="H6",
            size_hint_y=None,
            height=dp(40)
        ))
        content.add_widget(comment_field)
        
        dialog = MDDialog(
            title=f"{'Validation' if action == 'validate' else 'Rejet'} de l'alerte",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="ANNULER",
                    theme_text_color="Custom",
                    text_color=app.theme_cls.primary_color,
                    on_release=lambda x: dialog.dismiss()
                ),
                MDFlatButton(
                    text="CONFIRMER",
                    theme_text_color="Custom",
                    text_color=app.theme_cls.primary_color,
                    on_release=lambda x: self.process_alert(alert_id, action, comment_field.text, dialog)
                ),
            ],
        )
        dialog.open()

    def process_alert(self, alert_id, action, comment, dialog):
        app = MDApp.get_running_app()
        status = 'Validé' if action == 'validate' else 'Rejeté'
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE alerts 
            SET status = ?, comment = ?, technician_id = ?
            WHERE id = ?
        """, (status, comment, app.current_user['matricule'], alert_id))
        
        conn.commit()
        conn.close()
        
        dialog.dismiss()
        self.load_alerts()  # Rafraîchir la liste des alertes
        
        # Afficher un snackbar de confirmation
        Snackbar(
            text=f"Alerte {status.lower()} avec succès",
            snackbar_x="10dp",
            snackbar_y="10dp",
            size_hint_x=(Window.width - (dp(10) * 2)) / Window.width,
            bg_color=get_color_from_hex('#4CAF50') if action == 'validate' else get_color_from_hex('#F44336')
        ).open()

    def validate_alert(self, alert_id):
        self.show_comment_dialog(alert_id, 'validate')

    def reject_alert(self, alert_id):
        self.show_comment_dialog(alert_id, 'reject')

class SAMEsApp(MDApp):
    def build(self):
        # Configuration du thème
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.primary_hue = "500"
        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.material_style = "M3"  # Material Design 3
        
        # Configuration de la fenêtre
        Window.softinput_mode = "below_target"
        Window.size = (400, 700)  # Taille mobile standard
        
        # Initialize database
        init_db()
        
        # Load KV file
        return Builder.load_file('sames.kv')
    
    def on_start(self):
        self.timeout = None
        self.current_user = None
        self.current_photo = None
        
        # Charger les ressources
        self.load_status_icons()
    
    def load_status_icons(self):
        self.status_icons = {
            'En attente': {'icon': 'clock-outline', 'color': (1, 0.8, 0, 1)},  # Jaune
            'Vérifiée': {'icon': 'check-circle-outline', 'color': (0, 0.7, 0, 1)},  # Vert
            'Transmise à maintenance': {'icon': 'progress-wrench', 'color': (0, 0.5, 1, 1)},  # Bleu
            'Rejetée': {'icon': 'close-circle-outline', 'color': (0.8, 0, 0, 1)},  # Rouge
            'Traitée': {'icon': 'check-circle', 'color': (0, 0.8, 0, 1)}  # Vert foncé
        }
    
    def get_status_info(self, status):
        return self.status_icons.get(status, {'icon': 'help', 'color': (0.5, 0.5, 0.5, 1)})
    
    def reset_timeout(self):
        if self.timeout:
            Clock.unschedule(self.timeout)
        self.timeout = Clock.schedule_once(self.logout, 120)  # 2 minutes
    
    def logout(self, *args):
        self.current_user = None
        self.current_photo = None
        self.root.transition.direction = 'right'
        self.root.current = 'login'
    
    def toggle_nav_drawer(self, *args):
        try:
            nav_drawer = self.root.get_screen('technician_dashboard').ids.get('nav_drawer', None)
            if nav_drawer:
                nav_drawer.set_state('toggle')
        except Exception as e:
            print(f"Erreur lors de l'ouverture du menu latéral : {e}")

if __name__ == '__main__':
    SAMEsApp().run()
