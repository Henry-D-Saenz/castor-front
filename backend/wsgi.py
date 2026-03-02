"""WSGI entrypoint for Azure App Service."""
from app import create_app

app = create_app()

