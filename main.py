from datetime import datetime, timedelta
import sqlite3
import random
import string
from passlib.hash import bcrypt
from init_db import init_db, DB_PATH
import os
import cv2
from kivy.graphics.texture import Texture
from kivy.uix.image import Image
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
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineIconListItem
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.textfield import MDTextField
from kivymd.uix.menu import MDDropdownMenu
from config import STATUS_CONFIG, THEME_COLORS
from plyer import notification

class BaseScreen(MDScreen):
    def show_error_dialog(self, text):
        dialog = MDDialog(
            title="Erreur",
            text=text,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())]
        )
        dialog.open()

class LoginScreen(BaseScreen):
    def check_matricule(self):
        matricule = self.ids.matricule.text.strip()
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE matricule=?", (matricule,))
            user = c.fetchone()
        if user and user[0] == 'employee':
            self.ids.password.opacity = 0
            self.ids.password.disabled = True
            self.ids.forgot_password.opacity = 0
            self.ids.forgot_password.disabled = True
        else:
            self.ids.password.opacity = 1
            self.ids.password.disabled = False
            self.ids.forgot_password.opacity = 1
            self.ids.forgot_password.disabled = False

    def verify_login(self):
        matricule = self.ids.matricule.text.strip()
        password = self.ids.password.text.strip()
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT matricule, password, role FROM users WHERE matricule=?", (matricule,))
            user = c.fetchone()
        
        if not user or user[2] not in ('employee', 'technician', 'admin'):
            self.show_error_dialog("Identifiants invalides")
            return
        
        if user[2] == 'employee':
            # Skip password verification for employees
            app = MDApp.get_running_app()
            app.current_user = {'matricule': user[0], 'role': user[2]}
            app.reset_timeout()
            self.manager.current = 'employee_camera'
            return
        
        stored = user[1] or ''
        if not stored:
            self.show_error_dialog("Aucun mot de passe défini pour ce compte")
            return
        
        try:
            ok = bcrypt.verify(password, stored)
        except ValueError:
            self.show_error_dialog("Erreur de mot de passe")
            return
        
        if not ok:
            self.show_error_dialog("Mot de passe incorrect")
            return
        
        app = MDApp.get_running_app()
        app.current_user = {'matricule': user[0], 'role': user[2]}
        app.reset_timeout()
        
        if user[2] == 'technician':
            self.manager.current = 'technician_dashboard'
        else:  # admin
            self.manager.current = 'admin_dashboard'

    def request_password_reset(self):
        matricule = self.ids.matricule.text.strip()
        if not matricule:
            self.show_error_dialog("Veuillez entrer un matricule")
            return
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT matricule, role FROM users WHERE matricule=?", (matricule,))
            user = c.fetchone()
            if not user:
                self.show_error_dialog("Matricule invalide")
                return
            if user[1] == 'employee':
                self.show_error_dialog("La réinitialisation de mot de passe n'est pas disponible pour les employés")
                return
            
            # Générer un code temporaire (6 caractères alphanumériques)
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            expiry = datetime.now() + timedelta(minutes=30)
            
            c.execute('''INSERT OR REPLACE INTO reset_codes (matricule, code, expiry_date)
                        VALUES (?, ?, ?)''', (matricule, code, expiry))
            conn.commit()
        
        # Simuler l'envoi du code via une boîte de dialogue
        dialog = MDDialog(
            title="Code de réinitialisation",
            text=f"Votre code de réinitialisation est : {code}\nValide pendant 30 minutes.",
            buttons=[MDFlatButton(text="OK", on_release=lambda x: (dialog.dismiss(), setattr(self.manager, 'current', 'reset_password')))]
        )
        dialog.open()

class ResetPasswordScreen(BaseScreen):
    def reset_password(self):
        matricule = self.ids.matricule.text.strip()
        code = self.ids.code.text.strip()
        new_password = self.ids.new_password.text.strip()
        
        if not all([matricule, code, new_password]):
            self.show_error_dialog("Veuillez remplir tous les champs")
            return
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE matricule=?", (matricule,))
            user = c.fetchone()
            if user and user[0] == 'employee':
                self.show_error_dialog("La réinitialisation de mot de passe n'est pas disponible pour les employés")
                return
            
            c.execute("SELECT code, expiry_date FROM reset_codes WHERE matricule=?", (matricule,))
            reset_data = c.fetchone()
            
            if not reset_data:
                self.show_error_dialog("Aucun code de réinitialisation trouvé")
                return
            
            stored_code, expiry_date = reset_data
            if stored_code != code:
                self.show_error_dialog("Code invalide")
                return
            
            if datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S.%f') < datetime.now():
                self.show_error_dialog("Code expiré")
                return
            
            # Mettre à jour le mot de passe
            hashed_password = bcrypt.hash(new_password)
            c.execute("UPDATE users SET password=? WHERE matricule=?", (hashed_password, matricule))
            c.execute("DELETE FROM reset_codes WHERE matricule=?", (matricule,))
            conn.commit()
        
        Snackbar(
            text="Mot de passe réinitialisé avec succès",
            snackbar_x="10dp",
            snackbar_y="10dp",
            size_hint_x=(Window.width - (dp(10) * 2)) / Window.width,
            bg_color=THEME_COLORS['snackbar_success']
        ).open()
        self.manager.current = 'login'

class EmployeeCameraScreen(BaseScreen):
    def on_enter(self):
        self.capture = None
        self.camera_active = False
        self.preview = Image()
        self.ids.camera_layout.add_widget(self.preview)
        Clock.schedule_once(self.start_camera, 1)

    def on_leave(self):
        self.stop_camera()

    def start_camera(self, dt):
        for camera_index in range(2):
            self.capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if self.capture.isOpened():
                self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera_active = True
                Clock.schedule_interval(self.update_camera, 1.0 / 15.0)
                return
        
        self.show_error_dialog("Impossible d'accéder à la caméra. Essayez de sélectionner une image.")

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
            os.makedirs('assets', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join('assets', f'alert_{timestamp}.jpg')
            cv2.imwrite(filename, frame)
            
            app = MDApp.get_running_app()
            app.current_photo = filename
            self.stop_camera()
            self.manager.current = 'alert_type'
        else:
            self.show_error_dialog("Erreur lors de la capture")

class AlertTypeScreen(BaseScreen):
    def on_enter(self):
        grid = self.ids.type_grid
        grid.clear_widgets()
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT name, description, icon_name FROM anomaly_types")
            anomaly_types = c.fetchall()
        
        for name, description, icon_name in anomaly_types:
            self.add_type_card({'name': name, 'description': description, 'icon': icon_name})

    def add_type_card(self, anomaly):
        card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(200),
            md_bg_color=THEME_COLORS['card_background'],
            radius=[dp(10)],
            elevation=3,
            padding=dp(10),
            spacing=dp(5)
        )
        
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
        card.add_widget(icon_box)
        
        name_label = MDLabel(
            text=anomaly['name'],
            halign='center',
            font_style='H6',
            size_hint_y=None,
            height=dp(30)
        )
        desc_label = MDLabel(
            text=anomaly['description'],
            halign='center',
            theme_text_color="Secondary",
            font_style='Caption',
            size_hint_y=None,
            height=dp(20)
        )
        
        card.add_widget(name_label)
        card.add_widget(desc_label)
        card.bind(on_release=lambda x, name=anomaly['name']: self.select_type(name))
        self.ids.type_grid.add_widget(card)

    def select_type(self, type_name):
        app = MDApp.get_running_app()
        if self.check_daily_alert():
            self.show_error_dialog("Vous avez déjà envoyé une alerte aujourd'hui")
            return
        
        app.current_alert_type = type_name
        self.manager.current = 'alert_description'

    def check_daily_alert(self):
        app = MDApp.get_running_app()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('''SELECT COUNT(*) FROM alerts 
                    WHERE user_matricule=? 
                    AND strftime('%Y-%m-%d', send_date)=?''',
                 (app.current_user['matricule'], today))
                 
        count = c.fetchone()[0]
        conn.close()
        return count > 0

class AlertDescriptionScreen(BaseScreen):
    def submit_alert(self):
        app = MDApp.get_running_app()
        description = self.ids.description.text.strip()
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO alerts 
                        (user_matricule, photo_path, alert_type, description, send_date, status)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (app.current_user['matricule'],
                      app.current_photo,
                      app.current_alert_type,
                      description,
                      datetime.now(),
                      'En attente'))
            conn.commit()
        
        # Envoyer une notification aux techniciens
        notification.notify(
            title="Nouvelle alerte",
            message=f"Nouvelle alerte de type {app.current_alert_type} par {app.current_user['matricule']}",
            app_name="SAMEs"
        )
        
        # Planifier une notification de rappel pour les techniciens
        self.schedule_reminder(app.current_alert_type, app.current_user['matricule'])
        
        self.manager.current = 'alert_status'

    def schedule_reminder(self, alert_type, matricule):
        # Planifier une notification après 24 heures si l'alerte n'est pas traitée
        def check_pending_alert(dt):
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute('''SELECT status FROM alerts 
                            WHERE user_matricule=? AND alert_type=? 
                            AND status='En attente'
                            ORDER BY send_date DESC LIMIT 1''',
                         (matricule, alert_type))
                status = c.fetchone()
                if status and status[0] == 'En attente':
                    notification.notify(
                        title="Alerte en attente",
                        message=f"L'alerte de type {alert_type} par {matricule} attend toujours une action.",
                        app_name="SAMEs"
                    )
        
        Clock.schedule_once(check_pending_alert, 24 * 3600)  # 24 heures

class AlertStatusScreen(BaseScreen):
    def on_enter(self):
        self.update_status()
        Clock.schedule_interval(self.update_status, 30)

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
            status_info = STATUS_CONFIG.get(status[0], {'icon': 'help', 'color': (0.5, 0.5, 0.5, 1)})
            self.ids.status_icon.icon = status_info['icon']
            self.ids.status_icon.text_color = status_info['color']

class AlertHistoryScreen(BaseScreen):
    def on_enter(self):
        self.load_history()

    def load_history(self, filter_type='', sort_by='send_date DESC'):
        app = MDApp.get_running_app()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        query = '''SELECT id, alert_type, send_date, status, photo_path 
                  FROM alerts 
                  WHERE user_matricule=?'''
        params = [app.current_user['matricule']]
        
        if filter_type:
            query += " AND alert_type=?"
            params.append(filter_type)
        
        query += f" ORDER BY {sort_by} LIMIT 50"
        
        c.execute(query, params)
        alerts = c.fetchall()
        conn.close()
        
        self.ids.history_grid.clear_widgets()
        for alert in alerts:
            self.add_history_card(alert)

    def add_history_card(self, alert):
        alert_id, alert_type, send_date, status, photo_path = alert
        card = MDCard(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(100),
            md_bg_color=THEME_COLORS['card_background'],
            radius=[dp(10)],
            elevation=3,
            padding=dp(10)
        )
        
        icon = MDIconButton(
            icon=STATUS_CONFIG.get(status, {'icon': 'help'})['icon'],
            theme_icon_color="Custom",
            icon_color=STATUS_CONFIG.get(status, {'color': (0.5, 0.5, 0.5, 1)})['color']
        )
        
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(5)
        )
        content.add_widget(MDLabel(
            text=f"{alert_type} - {send_date.split('.')[0]}",
            theme_text_color="Primary"
        ))
        content.add_widget(MDLabel(
            text=f"Statut: {status}",
            theme_text_color="Secondary"
        ))
        
        card.add_widget(icon)
        card.add_widget(content)
        card.bind(on_release=lambda x, path=photo_path: self.show_image_popup(path))
        self.ids.history_grid.add_widget(card)

    def show_image_popup(self, photo_path):
        if not photo_path or not os.path.exists(photo_path):
            self.show_error_dialog("Image non disponible")
            return
        
        image_widget = Image(source=photo_path, size_hint=(1, None), height=dp(350))
        dialog = MDDialog(
            title="Photo de l'anomalie",
            type="custom",
            content_cls=image_widget,
            size_hint=(0.8, None),
            height=dp(420)
        )
        dialog.open()

    def show_filter_menu(self):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM anomaly_types")
            types = [row[0] for row in c.fetchall()]
        
        menu_items = [
            {"text": "Tous", "on_release": lambda: self.apply_filters("")}
        ] + [{"text": t, "on_release": lambda t=t: self.apply_filters(t)} for t in types]
        
        self.filter_menu = MDDropdownMenu(
            caller=self.ids.history_grid,
            items=menu_items,
            width_mult=4
        )
        self.filter_menu.open()

    def show_sort_menu(self):
        menu_items = [
            {"text": "Date (récent)", "on_release": lambda: self.apply_filters(self.ids.filter_type.text, "send_date DESC")},
            {"text": "Date (ancien)", "on_release": lambda: self.apply_filters(self.ids.filter_type.text, "send_date ASC")},
            {"text": "Statut", "on_release": lambda: self.apply_filters(self.ids.filter_type.text, "status ASC")}
        ]
        self.sort_menu = MDDropdownMenu(
            caller=self.ids.history_grid,
            items=menu_items,
            width_mult=4
        )
        self.sort_menu.open()

    def apply_filters(self, filter_type=None, sort_by='send_date DESC'):
        if filter_type is None:
            filter_type = self.ids.filter_type.text.strip()
        self.load_history(filter_type, sort_by)

class TechnicianDashboardScreen(BaseScreen):
    def on_enter(self):
        self.load_alerts()

    def load_alerts(self, filter_type='', sort_by='send_date DESC'):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        query = '''SELECT a.*, t.icon_name 
                  FROM alerts a 
                  JOIN anomaly_types t ON a.alert_type = t.name
                  WHERE a.status='En attente' '''
        params = []
        
        if filter_type:
            query += " AND a.alert_type=?"
            params.append(filter_type)
        
        query += f" ORDER BY {sort_by} LIMIT 20"
        
        c.execute(query, params)
        alerts = c.fetchall()
        conn.close()
        
        self.ids.alerts_grid.clear_widgets()
        for alert in alerts:
            self.add_alert_card(alert)

    def add_alert_card(self, alert):
        app = MDApp.get_running_app()
        alert_id, user_matricule, photo_path, alert_type, description, send_date, validation_date, status, comment, technician_id, icon_name = alert
        
        card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(420),
            md_bg_color=THEME_COLORS['card_background'],
            radius=[dp(10)],
            elevation=3,
            padding=dp(10)
        )

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
        header.add_widget(MDLabel(
            text=send_date.split('.')[0],
            theme_text_color="Secondary",
            halign='right'
        ))

        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(220)
        )
        
        type_box = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40)
        )
        icon = MDIconButton(
            icon=icon_name or 'help-circle',
            theme_icon_color="Custom",
            icon_color=app.theme_cls.primary_color
        )
        type_box.add_widget(icon)
        type_box.add_widget(MDLabel(
            text=f"Type: {alert_type}",
            theme_text_color="Primary"
        ))
        content.add_widget(type_box)
        
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=THEME_COLORS['separator']))
        
        status_label = MDLabel(
            text=f"Statut: {status}",
            theme_text_color="Custom",
            text_color=STATUS_CONFIG.get(status, {'color': app.theme_cls.primary_color})['color'],
            font_style="Subtitle2"
        )
        content.add_widget(status_label)
        
        content.add_widget(MDLabel(
            text=f"Employé: {user_matricule or '?'}",
            theme_text_color="Secondary"
        ))
        
        if description:
            content.add_widget(MDLabel(
                text=f"Description: {description}",
                theme_text_color="Secondary"
            ))
        
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=THEME_COLORS['separator']))
        
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
        
        image_button = MDFillRoundFlatIconButton(
            text="Voir l'image",
            icon="image",
            on_release=lambda x, path=photo_path: self.show_image_popup(path)
        )
        content.add_widget(image_button)
        
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
        
        filters = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(48),
            spacing=dp(10),
            padding=[dp(10), 0]
        )
        filter_button = MDFillRoundFlatIconButton(
            text="Filtrer",
            icon="filter",
            on_release=lambda x: self.show_filter_menu()
        )
        filters.add_widget(filter_button)
        
        card.add_widget(filters)
        card.add_widget(header)
        card.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=THEME_COLORS['separator']))
        card.add_widget(content)
        if status == 'En attente':
            card.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=THEME_COLORS['separator']))
            card.add_widget(buttons)
        self.ids.alerts_grid.add_widget(card)

    def show_filter_menu(self):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM anomaly_types")
            types = [row[0] for row in c.fetchall()]
        
        menu_items = [
            {"text": "Tous", "on_release": lambda: self.apply_filters("")}
        ] + [{"text": t, "on_release": lambda t=t: self.apply_filters(t)} for t in types]
        
        self.filter_menu = MDDropdownMenu(
            caller=self.ids.alerts_grid,
            items=menu_items,
            width_mult=4
        )
        self.filter_menu.open()

    def show_sort_menu(self):
        menu_items = [
            {"text": "Date (récent)", "on_release": lambda: self.apply_filters(self.ids.filter_type.text, "send_date DESC")},
            {"text": "Date (ancien)", "on_release": lambda: self.apply_filters(self.ids.filter_type.text, "send_date ASC")},
            {"text": "Statut", "on_release": lambda: self.apply_filters(self.ids.filter_type.text, "status ASC")}
        ]
        self.sort_menu = MDDropdownMenu(
            caller=self.ids.alerts_grid,
            items=menu_items,
            width_mult=4
        )
        self.sort_menu.open()

    def apply_filters(self, filter_type=None, sort_by='send_date DESC'):
        if filter_type is None:
            filter_type = self.ids.filter_type.text.strip()
        self.load_alerts(filter_type, sort_by)

    def show_image_popup(self, photo_path):
        if not photo_path or not os.path.exists(photo_path):
            self.show_error_dialog("Image non disponible ou fichier manquant")
            return
        
        image_widget = Image(source=photo_path, size_hint=(1, None), height=dp(350))
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
            SET status = ?, comment = ?, technician_id = ?, validation_date = ?
            WHERE id = ?
        """, (status, comment, app.current_user['matricule'], datetime.now(), alert_id))
        
        conn.commit()
        conn.close()
        
        dialog.dismiss()
        self.load_alerts()
        
        Snackbar(
            text=f"Alerte {status.lower()} avec succès",
            snackbar_x="10dp",
            snackbar_y="10dp",
            size_hint_x=(Window.width - (dp(10) * 2)) / Window.width,
            bg_color=THEME_COLORS['snackbar_success'] if action == 'validate' else THEME_COLORS['snackbar_error']
        ).open()

    def validate_alert(self, alert_id):
        self.show_comment_dialog(alert_id, 'validate')

    def reject_alert(self, alert_id):
        self.show_comment_dialog(alert_id, 'reject')

class AdminDashboardScreen(BaseScreen):
    def on_enter(self):
        self.load_users()

    def load_users(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT matricule, role FROM users ORDER BY matricule")
        users = c.fetchall()
        conn.close()
        
        self.ids.users_grid.clear_widgets()
        for user in users:
            self.add_user_card(user)

    def add_user_card(self, user):
        matricule, role = user
        card = MDCard(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(80),
            md_bg_color=THEME_COLORS['card_background'],
            radius=[dp(10)],
            elevation=3,
            padding=dp(10)
        )
        
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(5)
        )
        content.add_widget(MDLabel(
            text=f"Matricule: {matricule}",
            theme_text_color="Primary"
        ))
        content.add_widget(MDLabel(
            text=f"Rôle: {role}",
            theme_text_color="Secondary"
        ))
        
        card.add_widget(content)
        self.ids.users_grid.add_widget(card)

class SAMEsApp(MDApp):
    def build(self):
        self.kv_file = None  # Prevent multiple loading of sames.kv
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.primary_hue = "500"
        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.material_style = "M3"
        
        Window.softinput_mode = "below_target"
        Window.size = (400, 700)
        
        init_db()
        return Builder.load_file('sames.kv')

    def on_start(self):
        self.timeout = None
        self.current_user = None
        self.current_photo = None
        self.current_alert_type = None

    def reset_timeout(self):
        if self.timeout:
            Clock.unschedule(self.timeout)
        self.timeout = Clock.schedule_once(self.logout, 120)

    def logout(self, *args):
        self.current_user = None
        self.current_photo = None
        self.current_alert_type = None
        self.root.transition.direction = 'right'
        self.root.current = 'login'

    def toggle_theme(self):
        self.theme_cls.theme_style = "Dark" if self.theme_cls.theme_style == "Light" else "Light"

if __name__ == '__main__':
    SAMEsApp().run()