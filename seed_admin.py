from app import create_app
from cpl.models import db, User, RoleEnum

app = create_app()

with app.app_context():

    # Check if admin already exists
    existing = User.query.filter_by(username="skmishra2801").first()
    if existing:
        print("Admin user already exists.")
    else:
        admin = User(
            username="skmishra2801",
            email="skmishra2801@example.com",  # MUST provide email (required field)
            role=RoleEnum.admin
        )

        admin.set_password("Guddu2801#")

        db.session.add(admin)
        db.session.commit()

        print("Admin created successfully!")
