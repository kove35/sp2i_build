"""
Point d'entree recommande pour Streamlit Cloud.

Streamlit Cloud detecte plus facilement un fichier racine que
`frontend/app.py`. Ce wrapper garde le projet compatible local + cloud.
"""

from frontend.app import *  # noqa: F401,F403
