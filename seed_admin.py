from app import create_app
from cpl.models import db, Admin

app = create_app()

with app.app_context():
    admin = Admin(username="skmishra2801")
    admin.set_password("Guddu2801#")   # change this

    db.session.add(admin)
    db.session.commit()

    print("Admin user created successfully!")
