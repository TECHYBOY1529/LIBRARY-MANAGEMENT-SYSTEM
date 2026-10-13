"""Destructively reset the configured local database and recreate demo data."""
from library_app import create_app
from library_app.seed import reset_demo

app = create_app()
with app.app_context():
    reset_demo()
print("Demo database reset and reseeded.")
