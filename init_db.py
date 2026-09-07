import os
from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Create all tables
    db.create_all()
    
    # Check if admin exists
    admin = User.query.filter_by(username='manager').first()
    if not admin:
        admin = User(
            username='manager',
            password=generate_password_hash('Manager@2026'),
            role='admin',
            name='System Manager'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created successfully!")
    else:
        print("✅ Admin user already exists!")
    
    print("=" * 50)
    print("✅ Database initialized successfully!")
    print("=" * 50)
    print("👤 Login Credentials:")
    print("   Username: manager")
    print("   Password: Manager@2026")
    print("=" * 50)
