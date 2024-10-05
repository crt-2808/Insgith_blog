from flask import Flask, render_template, redirect, url_for, request, send_from_directory
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from news_integration import get_top_business_headlines
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename
import os
import random
from collections import Counter

# Configuración de las credenciales del servidor SMTP
SMTP_SERVER = "smtp.gmail.com"  # Cambia esto al servidor SMTP que estés usando
SMTP_PORT = 587
SMTP_EMAIL = "ramosbarragan.cristian@gmail.com"
SMTP_PASSWORD = "eibu zjmf oyga qooc"  # Tu contraseña

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
UPLOAD_FOLDER = os.path.join(app.instance_path, 'video')  # Define la carpeta de subida en instance
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024 * 1024  # 16 MB
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
ckeditor = CKEditor(app)
Bootstrap5(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True) 

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLE
class BlogPost(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    post_topic: Mapped[str]=mapped_column(Text, nullable=False, default="Opinion")
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    urlOriginal: Mapped[str]= mapped_column(Text, nullable=False, default="https://crt2808.pythonanywhere.com/")
    visitasRegistradas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Campo de visitas


class User(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(250), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

with app.app_context():
    db.create_all()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_weekly_summary_with_news, 'interval', weeks=1, next_run_time=datetime.now())
    scheduler.start()
    logging.info("Scheduler iniciado y tarea programada para enviar resúmenes semanales.")


def send_email(subject, body, recipients):
    # Configura el mensaje
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    # Añade el cuerpo del mensaje
    msg.attach(MIMEText(body, "plain"))

    try:
        # Conecta con el servidor SMTP y envía el correo
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Inicia la conexión segura
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, recipients, msg.as_string())
            print("Correo enviado con éxito.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")

logging.basicConfig(filename='weekly_email.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_posts_from_news(top_articles):
    for article in top_articles:
        # Verifica que los campos esenciales no sean None o vacíos
        if not article.get('title') or not article.get('description') or not article.get('urlToImage'):
            logging.warning(f"El artículo con título '{article.get('title', 'desconocido')}' tiene campos vacíos. No se creará el post.")
            continue  # Salta al siguiente artículo si hay campos esenciales faltantes

        # Verifica si el título ya existe en la base de datos
        existing_post = BlogPost.query.filter_by(title=article['title']).first()
        
        if existing_post:
            logging.info(f"El post con título '{article['title']}' ya existe en la base de datos. No se creará un nuevo registro.")
            continue  # Salta al siguiente artículo
        
        # Verifica si el autor está presente, de lo contrario usa "Cris Ramos"
        author = article.get('author')
        
        # Crea un nuevo post si el título no existe
        new_post = BlogPost(
            title=article['title'],
            subtitle=article['description'],
            body=article['content'],
            img_url=article.get('urlToImage', "img"),
            author=author if author else 'Cris Ramos',
            date=date.today().strftime("%B %d, %Y"),
            urlOriginal=article.get('url'),
            visitasRegistradas=random.randint(1, 100),
            post_topic='Noticia'
        )
        
        db.session.add(new_post)
    
    db.session.commit()
    logging.info("Posts creados a partir de las noticias.")

def get_weekly_posts():
    today = datetime.now().date()
    last_week = today - timedelta(days=7)
    weekly_posts = BlogPost.query.filter(
        BlogPost.date >= last_week.strftime("%B %d, %Y"),
        BlogPost.date <= today.strftime("%B %d, %Y")
    ).all()
    logging.info(f"Posts obtenidos para la semana del {last_week} al {today}.")
    return weekly_posts

def send_weekly_summary(posts, recipients):
    subject = "Resumen semanal de nuevos posts"
    body = "<html><body><h2>¡Aquí tienes los posts publicados esta semana!</h2>"
    for post in posts:
        body += f"""
        <h3>{post.title}</h3>
        <p><strong>Autor:</strong> {post.author}</p>
        <p><a href="https://crt2808.pythonanywhere.com/post/{post.id}">Leer más</a></p>
        <hr>
        """
    body += "</body></html>"

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = SMTP_EMAIL
    msg['To'] = ", ".join(recipients)
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as connection:
            connection.starttls()
            connection.login(user=SMTP_EMAIL, password=SMTP_PASSWORD)
            for recipient in recipients:
                connection.sendmail(SMTP_EMAIL, recipient, msg.as_string())
        logging.info("Correo semanal enviado con éxito.")
    except Exception as e:
        logging.error(f"Error al enviar el correo semanal: {e}")

def send_weekly_summary_with_news():
    logging.info("Inicio del proceso de resumen semanal con noticias.")
    
    # Obtener las principales noticias de negocios
    top_articles = get_top_business_headlines()
    logging.info(f"Esto es el top articles: {top_articles}")
    
    if top_articles:
        # Ejecutar dentro del contexto de la aplicación
        with app.app_context():
            # Crear posts a partir de las noticias
            create_posts_from_news(top_articles)
    
    # Obtener los posts semanales
    with app.app_context():
        weekly_posts = get_weekly_posts()
        users = User.query.all()
        recipient_emails = [user.email for user in users]
    
        if weekly_posts:
            # Enviar el resumen semanal
            send_weekly_summary(weekly_posts, recipient_emails)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# WTForm
class CreatePostForm(FlaskForm):
    title = StringField("Titulo", validators=[DataRequired()])
    subtitle = StringField("Subtitulo", validators=[DataRequired()])
    author = StringField("Nombre del autor", validators=[DataRequired()])
    img_url = StringField("URL de la Imagen", validators=[DataRequired(), URL()])
    post_topic = StringField("Post Topic")
    video = FileField("Selecciona un video")  # Agrega el campo para el video
    body = CKEditorField("Contenido", validators=[DataRequired()])
    submit = SubmitField("Publicar")


@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory(os.path.join(app.instance_path, 'video'), filename)

@app.template_filter('truncate')
def truncate_filter(text, length=100):
    if len(text) > length:
        return text[:length] + '...'
    return text

@app.route('/publicacionSemanal', methods=['GET'])
def publicacion_semanal():
    try:
        send_weekly_summary_with_news()
        return "Resumen semanal con noticias enviado correctamente.", 200
    except Exception as e:
        logging.error(f"Error al enviar el resumen semanal: {e}")
        return "Error al enviar el resumen semanal.", 500

@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>")
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    return render_template("post.html", post=requested_post)


@app.route("/new-post", methods=["GET", "POST"])
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        print(form)
        # Crear un nuevo post
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=form.author.data,
            date=date.today().strftime("%B %d, %Y"),
            visitasRegistradas=random.randint(1, 100),
            post_topic=form.post_topic.data
        )
        db.session.add(new_post)
        db.session.commit()  # Guarda en la base de datos y obtiene el ID

        # Verificar si se subió un video
        if 'video' in request.files:
            video = request.files['video']
            if video and allowed_file(video.filename):
                # Renombrar el video
                filename = f"video_{new_post.id}{os.path.splitext(video.filename)[1]}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                # Registro de información del archivo de video
                logging.info(f"Archivo de video seleccionado: {video.filename}, tipo: {video.content_type}, tamaño: {video.content_length} bytes.")

                try:
                    # Guardar el video
                    video.save(file_path)
                    logging.info("Video guardado exitosamente", "success")
                except Exception as e:
                    logging.warning(f"Error al guardar el video: {e}", "danger")

        # Obtener correos electrónicos de los usuarios
        users = User.query.all()
        recipient_emails = [user.email for user in users]

        # Enviar correo de notificación
        send_email_notification(new_post.title, new_post.subtitle, recipient_emails)

        return redirect(url_for("get_all_posts"))

    return render_template("make-post.html", form=form)

def send_email_notification(title, subtitle, recipients):
    try:
        # Crear el mensaje en formato HTML
        subject = f"Nuevo Post: {title}"
        body = f"""
        <html>
        <body>
            <p>¡Un nuevo post ha sido publicado!</p>
            <p><strong>Título:</strong> {title}</p>
            <p><strong>Subtítulo:</strong> {subtitle}</p>
            <p>Visítanos para leer más: <a href="https://crt2808.pythonanywhere.com/">https://crt2808.pythonanywhere.com/</a></p>
            <p><img src="https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExazN0YzF5dWVieHc1b2Z3MDhzaTVsczB1MTM2YWI2YmhiczNpZnowZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/cNPoJv04YIm9q/giphy.gif" alt="GIF de Celebración" style="width:300px;height:auto;"></p>
        </body>
        </html>
        """

        # Crear el contenedor del mensaje MIME
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SMTP_EMAIL
        msg['To'] = ", ".join(recipients)

        # Adjuntar el cuerpo HTML al mensaje
        msg.attach(MIMEText(body, 'html'))

        # Establecer conexión con el servidor SMTP
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()  # Asegurar la conexión
            connection.login(user=SMTP_EMAIL, password=SMTP_PASSWORD)  # Autenticarse
            for recipient in recipients:
                connection.sendmail(from_addr=SMTP_EMAIL, to_addrs=recipient, msg=msg.as_string())
        print("Correo enviado con éxito.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# Code from previous day
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    msg_sent = False
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        message = request.form["message"]

        # Crear un nuevo usuario
        new_user = User(name=name, email=email, phone=phone, message=message)
        db.session.add(new_user)
        db.session.commit()

        msg_sent = True

    return render_template("contact.html", msg_sent=msg_sent)

@app.route('/adminPanel')
def admin_panel():
    # Consulta para obtener las 5 publicaciones con más visitas
    top_posts = BlogPost.query.order_by(BlogPost.visitasRegistradas.desc()).limit(5).all()
    
    # Contar los diferentes tipos de post_topic
    post_topics = db.session.query(BlogPost.post_topic).all()
    topic_counts = Counter(topic.post_topic for topic in post_topics)

    # Contar las publicaciones por autor
    authors = db.session.query(BlogPost.author).all()
    author_counts = Counter(author.author for author in authors)

    # Dividir los datos para la gráfica de tipos de post
    topic_labels = list(topic_counts.keys())
    topic_values = list(topic_counts.values())
    
    # Dividir los datos para la gráfica de autores
    author_labels = list(author_counts.keys())
    author_values = list(author_counts.values())

    return render_template(
        'admin_panel.html', 
        top_posts=top_posts, 
        topic_labels=topic_labels, 
        topic_values=topic_values,
        author_labels=author_labels,
        author_values=author_values)



if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True, port=5002)