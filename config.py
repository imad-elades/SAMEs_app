# config.py
STATUS_CONFIG = {
    'En attente': {'icon': 'clock-outline', 'color': (1, 0.8, 0, 1)},  # Jaune
    'Validé': {'icon': 'check-circle', 'color': (0, 0.8, 0, 1)},       # Vert
    'Rejeté': {'icon': 'close-circle', 'color': (0.8, 0, 0, 1)}        # Rouge
}

THEME_COLORS = {
    'background': (0.95, 0.96, 0.98, 1),      # Gris clair
    'card_background': (1, 1, 1, 1),           # Blanc
    'separator': (0.8, 0.8, 0.8, 1),           # Gris moyen
    'snackbar_success': (0.2, 0.6, 0.2, 1),    # Vert sombre
    'snackbar_error': (0.8, 0.2, 0.2, 1),      # Rouge sombre
    'primary': (0.13, 0.33, 0.67, 1),          # Bleu profond
    'accent': (0.95, 0.65, 0, 1),              # Orange doux
}