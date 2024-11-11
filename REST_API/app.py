from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'mysecret'  # Změňte na tajný klíč
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Zde nastavujeme stránku pro přihlášení

# Model pro uživatele
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Přidání administrátorského pole

# Model pro blogové příspěvky
class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Sloupec author_id
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    visible_to = db.Column(db.String, default='')  # ID uživatelů oddělené čárkou

    author = db.relationship('User', backref=db.backref('posts', lazy=True))

# Vytvoření tabulek v rámci kontextu aplikace
with app.app_context():
    db.create_all()  # Vytvoření tabulek

# Registrace nového uživatele
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Kontrola existence uživatelského jména
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another one.')
            return render_template('register.html')

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password)

        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! You can now log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

# Přihlášení uživatele
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login failed. Check your username and/or password.')
    return render_template('login.html')

# Odhlášení uživatele
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Endpoint: Vytvoření nového blog postu
@app.route('/api/blog', methods=['POST'])
@login_required
def create_blog_post():
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    new_post = BlogPost(author_id=current_user.id, content=data['content'])
    db.session.add(new_post)
    db.session.commit()
    return jsonify({'id': new_post.id}), 201

# Endpoint: Zobrazení všech blog postů
@app.route('/api/blog', methods=['GET'])
@login_required
def get_all_blog_posts():
    if current_user.is_admin:
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    else:
        posts = BlogPost.query.filter(BlogPost.visible_to.like(f'%{current_user.id}%')).order_by(BlogPost.created_at.desc()).all()
        
    result = [{'id': post.id, 'author_id': post.author_id, 'content': post.content, 'created_at': post.created_at} for post in posts]
    return jsonify(result), 200

# Endpoint: Zobrazení blog postu dle ID
@app.route('/api/blog/<int:blog_id>', methods=['GET'])
def get_blog_post(blog_id):
    post = BlogPost.query.get(blog_id)
    if not post:
        return jsonify({'error': 'Blog post not found'}), 404

    result = {'id': post.id, 'author_id': post.author_id, 'content': post.content, 'created_at': post.created_at}
    return jsonify(result), 200

# Endpoint: Smazání blog postu dle ID
@app.route('/api/blog/<int:blog_id>', methods=['DELETE'])
@login_required
def delete_blog_post(blog_id):
    post = BlogPost.query.get(blog_id)
    if not post:
        return jsonify({'error': 'Blog post not found'}), 404

    # Kontrola, zda je uživatel autorem nebo administrátor
    if post.author_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Blog post deleted'}), 200

# Endpoint: Částečný update blog postu dle ID
@app.route('/api/blog/<int:blog_id>', methods=['PATCH'])
@login_required
def update_blog_post(blog_id):
    post = BlogPost.query.get(blog_id)
    if not post:
        return jsonify({'error': 'Blog post not found'}), 404

    # Kontrola, zda je uživatel autorem nebo administrátor
    if post.author_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    if 'content' in data:
        post.content = data['content']

    db.session.commit()
    return jsonify({'message': 'Blog post updated'}), 200

# Hlavní stránka: Zobrazení všech blog postů
@app.route('/')
def index():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('index.html', posts=posts)

# Formulář: Vytvoření nového příspěvku přes formulář
@app.route('/create-post', methods=['POST'])
@login_required
def create_post_form():
    author = current_user.username  # Používáme aktuálního uživatele
    content = request.form['content']

    new_post = BlogPost(author_id=current_user.id, content=content)
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('index'))

# Endpoint: Zobrazení dokumentace API
@app.route('/api/about', methods=['GET'])
def about():
    documentation = {
        "description": "Toto API umožňuje uživatelům spravovat blogové příspěvky.",
        "endpoints": {
            "/api/register": {
                "method": "POST",
                "description": "Registrace nového uživatele.",
                "payload": {
                    "username": "string, unikátní uživatelské jméno",
                    "password": "string, heslo uživatele"
                },
                "response": {
                    "success": "boolean",
                    "message": "string, zpráva o výsledku registrace"
                }
            },
            "/api/login": {
                "method": "POST",
                "description": "Přihlášení uživatele.",
                "payload": {
                    "username": "string, uživatelské jméno",
                    "password": "string, heslo"
                },
                "response": {
                    "success": "boolean",
                    "message": "string, zpráva o výsledku přihlášení"
                }
            },
            "/api/logout": {
                "method": "GET",
                "description": "Odhlášení uživatele.",
                "response": {
                    "message": "string, zpráva o úspěšném odhlášení"
                }
            },
            "/api/blog": {
                "method": "POST",
                "description": "Vytvoření nového blogového příspěvku.",
                "payload": {
                    "content": "string, text blogového příspěvku"
                },
                "response": {
                    "id": "integer, ID nového příspěvku"
                }
            },
            "/api/blog": {
                "method": "GET",
                "description": "Zobrazení všech blogových příspěvků.",
                "response": {
                    "posts": [
                        {
                            "id": "integer, ID příspěvku",
                            "author_id": "integer, ID autora",
                            "content": "string, obsah příspěvku",
                            "created_at": "datetime, datum vytvoření příspěvku"
                        }
                    ]
                }
            },
            "/api/blog/<blog_id>": {
                "method": "GET",
                "description": "Zobrazení blogového příspěvku dle ID.",
                "response": {
                    "id": "integer, ID příspěvku",
                    "author_id": "integer, ID autora",
                    "content": "string, obsah příspěvku",
                    "created_at": "datetime, datum vytvoření příspěvku"
                }
            },
            "/api/blog/<blog_id>": {
                "method": "DELETE",
                "description": "Smazání blogového příspěvku dle ID.",
                "response": {
                    "message": "string, zpráva o úspěšném smazání příspěvku"
                }
            },
            "/api/blog/<blog_id>": {
                "method": "PATCH",
                "description": "Částečný update blogového příspěvku dle ID.",
                "payload": {
                    "content": "string, nový obsah příspěvku"
                },
                "response": {
                    "message": "string, zpráva o úspěšném updatu příspěvku"
                }
            },
            "/api/about": {
                "method": "GET",
                "description": "Zobrazení dokumentace API."
            }
        },
        "authorization": {
            "description": "Všechny chráněné endpointy vyžadují, aby byl uživatel přihlášen.",
            "token": "Po přihlášení bude uživatel moci volat chráněné endpointy."
        }
    }
    return jsonify(documentation), 200

if __name__ == '__main__':
    app.run(debug=True)
