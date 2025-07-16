import os
from app import app, db, Category # Importa app, db y Category desde tu app.py

# Ruta al archivo de la base de datos
db_path = os.path.join(app.root_path, 'blog.db')

print("--- INICIANDO PROCESO DE CREACIÓN DE BASE DE DATOS ---")

# Eliminar la base de datos existente si RECREATE_DATABASE es True (o si queremos forzarlo)
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print(f"Base de datos existente '{db_path}' eliminada para recreación.")
    except Exception as e:
        print(f"ERROR: No se pudo eliminar la base de datos '{db_path}'. Asegúrate de que no esté en uso. Error: {e}")
        # Si no se puede eliminar, el proceso no puede continuar de forma limpia.
        exit(1) # Salir del script con un error

# Crear las tablas de la base de datos
with app.app_context():
    print("Creando/actualizando tablas de la base de datos...")
    try:
        db.create_all()
        print("Tablas de la base de datos creadas/actualizadas con éxito.")
        
        # Añadir categorías por defecto si no existen
        if not Category.query.first():
            print("Añadiendo categorías de fútbol por defecto...")
            default_categories = ['Noticias', 'Análisis de Partidos', 'Jugadores', 'Tácticas', 'Mercado de Fichajes', 'Resultados']
            for cat_name in default_categories:
                if not Category.query.filter_by(name=cat_name).first():
                    db.session.add(Category(name=cat_name))
            db.session.commit()
            print("Categorías añadidas.")
        else:
            print("Las categorías por defecto ya existen.")
    except Exception as e:
        print(f"ERROR: Fallo al crear/actualizar tablas de la base de datos o añadir categorías. Error: {e}")
        exit(1) # Salir del script con un error

print("--- PROCESO DE CREACIÓN DE BASE DE DATOS COMPLETADO ---")

