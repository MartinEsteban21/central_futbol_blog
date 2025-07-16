from app import app, db # Importa la instancia de app y db de tu app.py

print("Iniciando la creación/actualización de la base de datos...")
with app.app_context(): # Asegura que db.create_all() se ejecuta en el contexto de la aplicación
    db.create_all()
print("Base de datos creada/actualizada con éxito.")
