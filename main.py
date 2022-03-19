from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LogInForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from datetime import datetime
import smtplib
import os
from dotenv import load_dotenv

# email environmental variables
load_dotenv('.env')
from_email = os.getenv('FROM_EMAIL')
password = os.getenv('PASSWORD')
to_email = os.getenv('TO_EMAIL')
# initialize flask, ckeditor
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)
year = datetime.now().year
# gravatar for user avatars
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False,
                    force_lower=False, use_ssl=False, base_url=None)

# initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# to receive mail from contact page
def send_email(name, email, text):
    message = f'Subject:Message from {name}\n\n' \
              f'Email: {email}\n' \
              f'Message:\n{text}'
    connection = smtplib.SMTP('smtp.gmail.com')
    connection.starttls()
    connection.login(user=from_email, password=password)
    connection.sendmail(from_addr=from_email, to_addrs=to_email, msg=message)


# decorator for admin only functions
def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            # if not admin return error
            return abort(403)
        # else return function
        return func(*args, **kwargs)
    return decorated_function


# decorator for member only functions
def signin_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please sign in to view content.')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return decorated_function


# connects to DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chicken-blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# configures tables
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user_data.id'))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship('Comment', back_populates='blog_post')


class User(UserMixin, db.Model):
    __tablename__ = 'user_data'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    posts = relationship('BlogPost', back_populates='author')
    comments = relationship('Comment', back_populates='author')


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(250))
    author_id = db.Column(db.Integer, db.ForeignKey('user_data.id'))
    author = relationship('User', back_populates='comments')
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    blog_post = relationship('BlogPost', back_populates='comments')


db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts,
                           current_user=current_user, year=year)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash('This email is already registered, please log in.')
            return redirect(url_for('login'))
        secured_password = generate_password_hash(password=form.password.data,
                                                  method='pbkdf2:sha256',
                                                  salt_length=8)
        new_user = User()
        new_user.name = form.name.data
        new_user.email = form.email.data
        new_user.password = secured_password
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, current_user=current_user, year=year)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LogInForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash('Account not found, please register')
            return redirect(url_for('register'))
        elif not check_password_hash(user.password, form.password.data):
            flash('Incorrect password, please try again')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=form, loged_in=current_user.is_authenticated, year=year)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
@signin_required
def show_post(post_id):
    all_comments = Comment.query.all()
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
        comment = Comment(text=form.comment.data,
                          author=current_user,
                          blog_post=requested_post)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post,
                           current_user=current_user, form=form, comments=all_comments, year=year)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user, year=year)


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        send_email(name=request.form['name'],
                   email=request.form['email'],
                   text=request.form['text'])
        return render_template("contact.html", current_user=current_user, msg_sent=True, year=year)
    return render_template("contact.html", current_user=current_user, msg_sent=False, year=year)


@app.route("/new-post", methods=['GET', 'POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user, year=year)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
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
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, current_user=current_user, year=year)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
