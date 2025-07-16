import os # Importar el módulo os para acceder a variables de entorno
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import secrets # Todavía necesario para generar nombres de archivo únicos
from werkzeug.utils import secure_filename # Para nombres de archivo seguros

app = Flask(__name__)

# Configuración de la clave secreta desde variables de entorno
# Esto es CRÍTICO para producción en Render.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    # Si la variable de entorno no está configurada (ej. en desarrollo local sin dotenv)
    # puedes tener una clave de respaldo para desarrollo, pero NUNCA para producción.
    # Para producción, Render DEBE proveerla.
    # raise ValueError("No SECRET_KEY set for Flask application. Please set the 'SECRET_KEY' environment variable.")
    # Para facilitar el desarrollo local si no usas dotenv, puedes descomentar la línea de abajo,
    # pero recuerda que es INSEGURO para producción.
    # print("ADVERTENCIA: SECRET_KEY no establecida en entorno. Usando clave por defecto (solo para desarrollo).")
    app.config['SECRET_KEY'] = 'una_clave_secreta_muy_insegura_para_desarrollo' # CAMBIA ESTO EN PRODUCCIÓN

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Carpeta para subir imágenes
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Límite de 16MB para subidas

# Extensiones de archivo permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Verifica si la extensión del archivo está permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # La ruta a la que redirigir si un usuario no está logueado

# Contexto de plantilla global para el año actual en el footer
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# FILTRO PERSONALIZADO PARA TRUNCAR TEXTO
@app.template_filter('truncate')
def truncate_filter(s, length=200, killwords=True, end='...'):
    if len(s) <= length:
        return s
    if killwords:
        return s[:length].rsplit(' ', 1)[0] + end
    return s[:length] + end

# MODELO DE USUARIO
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    profile_image = db.Column(db.String(120), default='default_profile.png')
    bio = db.Column(db.Text, default='¡Hola! Soy un nuevo miembro de la comunidad.')
    comments = db.relationship('Comment', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.username}')"

# FUNCIÓN user_loader PARA FLASK-LOGIN
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# MODELO DE CATEGORÍA
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    posts = db.relationship('Post', backref='category', lazy=True)

    def __repr__(self):
        return f"Category('{self.name}')"

# MODELO DE POST
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(50), default='Anónimo')
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', backref='posts', lazy=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    image_file = db.Column(db.String(120), nullable=True)
    comments = db.relationship('Comment', backref='post', lazy=True, order_by='Comment.date_posted.asc()')


    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"

# MODELO DE COMENTARIO
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    def __repr__(self):
        return f"Comment('{self.content[:20]}...', by User ID: {self.user_id}, on Post ID: {self.post_id}')"


# RUTAS DE LA APLICACIÓN

@app.route('/')
def index():
    # Ya no se cargan posts aquí, solo las categorías para el menú
    categories = Category.query.order_by(Category.name).all()
    return render_template('index.html', categories=categories)

@app.route('/category/<int:category_id>')
def category_posts(category_id):
    category = Category.query.get_or_404(category_id)
    posts = Post.query.filter_by(category=category).order_by(Post.date_posted.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template('category_posts.html', category=category, posts=posts, categories=categories)


# RUTA DE REGISTRO
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Manejo de la imagen de perfil
        profile_image_filename = 'default_profile.png' # Valor por defecto
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = secrets.token_hex(8) + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                profile_image_filename = unique_filename
            elif file.filename != '':
                flash('Tipo de archivo de imagen no permitido. Solo PNG, JPG, JPEG, GIF.', 'danger')
                return render_template('register.html')


        user = User.query.filter_by(username=username).first()
        if user:
            flash('Ese nombre de usuario ya existe. Por favor, elige otro.', 'danger')
        else:
            new_user = User(username=username, profile_image=profile_image_filename)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('¡Tu cuenta ha sido creada con éxito! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

# RUTA DE LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'¡Bienvenido de nuevo, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Login fallido. Por favor, revisa tu nombre de usuario y contraseña.', 'danger')
    return render_template('login.html')

# RUTA DE LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

# RUTA PARA VER PERFIL DE USUARIO
@app.route('/user/<string:username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    user_posts = Post.query.filter_by(user=user).order_by(Post.date_posted.desc()).all()
    return render_template('user_profile.html', user=user, posts=user_posts)

# RUTA PARA EDITAR PERFIL DE USUARIO
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio = request.form['bio']
        
        # Manejo de la imagen de perfil
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file.filename == '':
                pass
            elif file and allowed_file(file.filename):
                if current_user.profile_image != 'default_profile.png':
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_image)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                filename = secure_filename(file.filename)
                unique_filename = secrets.token_hex(8) + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                current_user.profile_image = unique_filename
            else:
                flash('Tipo de archivo de imagen no permitido. Solo PNG, JPG, JPEG, GIF.', 'danger')
                return render_template('edit_profile.html', user=current_user)

        try:
            db.session.commit()
            flash('Perfil actualizado con éxito!', 'success')
            return redirect(url_for('user_profile', username=current_user.username))
        except Exception as e:
            print(f"Error al actualizar perfil: {e}")
            flash('Hubo un error al actualizar el perfil.', 'danger')
    return render_template('edit_profile.html', user=current_user)


# RUTA PARA CREAR NUEVOS POSTS
@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        post_title = request.form['title']
        post_content = request.form['content']
        post_author = request.form.get('author', current_user.username)
        category_id = request.form.get('category_id')

        # Manejo de la imagen del post
        post_image_filename = None
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = secrets.token_hex(8) + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                post_image_filename = unique_filename
            elif file.filename != '':
                flash('Tipo de archivo de imagen no permitido. Solo PNG, JPG, JPEG, GIF.', 'danger')
                return render_template('create_post.html', categories=categories)

        new_post = Post(title=post_title, content=post_content, author=post_author, user=current_user, image_file=post_image_filename)

        if category_id:
            new_post.category_id = category_id

        try:
            db.session.add(new_post)
            db.session.commit()
            flash('¡Publicación creada con éxito!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error al añadir el post: {e}")
            flash('Hubo un error al crear la publicación.', 'danger')
            return redirect(url_for('create_post'))
    return render_template('create_post.html', categories=categories)

# RUTA PARA LA PÁGINA DE DETALLE DE UN POST INDIVIDUAL
@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    can_edit_delete = False
    if current_user.is_authenticated and post.user_id == current_user.id:
        can_edit_delete = True

    # Lógica para añadir un comentario
    if request.method == 'POST' and current_user.is_authenticated:
        comment_content = request.form['comment_content']
        if comment_content:
            new_comment = Comment(content=comment_content, user_id=current_user.id, post_id=post.id)
            try:
                db.session.add(new_comment)
                db.session.commit()
                flash('Comentario añadido con éxito!', 'success')
                return redirect(url_for('post_detail', post_id=post.id))
            except Exception as e:
                print(f"Error al añadir comentario: {e}")
                flash('Hubo un error al añadir el comentario.', 'danger')
        else:
            flash('El comentario no puede estar vacío.', 'warning')
    
    return render_template('post_detail.html', post=post, can_edit_delete=can_edit_delete)

# RUTA PARA ELIMINAR UN COMENTARIO
@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        flash('Comentario no encontrado.', 'danger')
        return redirect(url_for('index'))

    if comment.user_id != current_user.id and comment.post.user_id != current_user.id:
        flash('No tienes permiso para eliminar este comentario.', 'danger')
        return redirect(url_for('post_detail', post_id=comment.post.id))

    post_id = comment.post.id
    try:
        db.session.delete(comment)
        db.session.commit()
        flash('Comentario eliminado con éxito!', 'success')
        return redirect(url_for('post_detail', post_id=post_id))
    except Exception as e:
        print(f"Error al eliminar comentario: {e}")
        flash('Hubo un error al eliminar el comentario.', 'danger')
        return redirect(url_for('post_detail', post_id=post_id))


# RUTA PARA EDITAR UN POST EXISTENTE
@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Publicación no encontrada.', 'danger')
        return redirect(url_for('index'))

    if post.user_id != current_user.id:
        flash('No tienes permiso para editar esta publicación.', 'danger')
        return redirect(url_for('post_detail', post_id=post.id))

    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.author = request.form.get('author', current_user.username)
        category_id = request.form.get('category_id')

        if category_id:
            post.category_id = category_id
        else:
            post.category_id = None

        # Manejo de la imagen del post
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file.filename == '':
                pass
            elif file and allowed_file(file.filename):
                if post.image_file:
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_file)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                filename = secure_filename(file.filename)
                unique_filename = secrets.token_hex(8) + '_' + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                post.image_file = unique_filename
            else:
                flash('Tipo de archivo de imagen no permitido. Solo PNG, JPG, JPEG, GIF.', 'danger')
                return render_template('edit_post.html', post=post, categories=categories)
        elif request.form.get('clear_image'):
            if post.image_file:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_file)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                post.image_file = None


        try:
            db.session.commit()
            flash('¡Publicación actualizada con éxito!', 'success')
            return redirect(url_for('post_detail', post_id=post.id))
        except Exception as e:
            print(f"Error al actualizar el post: {e}")
            flash('Hubo un error al actualizar la publicación.', 'danger')
            return render_template('edit_post.html', post=post, categories=categories)
    else:
        return render_template('edit_post.html', post=post, categories=categories)


# RUTA PARA ELIMINAR UN POST
@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Publicación no encontrada.', 'danger')
        return redirect(url_for('index'))

    if post.user_id != current_user.id:
        flash('No tienes permiso para eliminar esta publicación.', 'danger')
        return redirect(url_for('post_detail', post_id=post.id))

    try:
        # Eliminar comentarios asociados al post antes de eliminar el post
        for comment in post.comments:
            db.session.delete(comment)
        
        # Eliminar la imagen del post si existe
        if post.image_file:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_file)
            if os.path.exists(image_path):
                os.remove(image_path)

        db.session.delete(post)
        db.session.commit()
        flash('¡Publicación eliminada con éxito!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error al eliminar el post: {e}")
        flash('Hubo un error al eliminar la publicación.', 'danger')
        return redirect(url_for('post_detail', post_id=post.id))

if __name__ == '__main__':
    # Asegurarse de que la carpeta de uploads exista
    uploads_path = os.path.join(app.root_path, 'static', 'uploads')
    if not os.path.exists(uploads_path):
        try:
            os.makedirs(uploads_path)
            print(f"Carpeta de subidas creada: {uploads_path}")
        except Exception as e:
            print(f"ERROR: No se pudo crear la carpeta de subidas '{uploads_path}'. Error: {e}")

    app.run(debug=True)