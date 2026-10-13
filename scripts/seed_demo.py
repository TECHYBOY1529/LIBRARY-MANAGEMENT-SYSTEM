from library_app import create_app
from library_app.seed import seed_demo

app = create_app()
with app.app_context():
    seed_demo()
print("Fictional demo data is ready.")
