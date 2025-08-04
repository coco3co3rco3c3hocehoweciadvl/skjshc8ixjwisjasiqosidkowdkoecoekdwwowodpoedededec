from flask import Flask, request, redirect, url_for, session, render_template_string, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.secret_key = 'SCIDIWODKOWDJSKJCKEJCKENCJCJENEJCHSKXJSOKXOWKSSOWKDOKW'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nerestreddit.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
db = SQLAlchemy(app)
MSK_TZ = timezone(timedelta(hours=3))

def get_msk_time():
    return datetime.now(MSK_TZ)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=get_msk_time)
    likes = db.Column(db.Integer, default=0)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_msk_time)
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_msk_time)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id'),)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    from_user = db.Column(db.String(80), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_msk_time)

def is_logged_in():
    return 'username' in session

def get_user_id():
    if is_logged_in():
        user = User.query.filter_by(username=session['username']).first()
        if user:
            return user.id
    return None

def user_liked_post(post_id):
    user_id = get_user_id()
    if user_id:
        like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
        return like is not None
    return False

def get_unread_notifications_count():
    user_id = get_user_id()
    if user_id:
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()
    return 0

def create_notification(user_id, notification_type, message, from_user, post_id=None, comment_id=None):
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        message=message,
        from_user=from_user,
        post_id=post_id,
        comment_id=comment_id
    )
    db.session.add(notification)
    db.session.commit()

@app.route('/nerest.PNG')
def serve_logo():
    return send_from_directory('.', 'nerest.PNG')

@app.before_request
def check_session():
    username = session.get('username')
    if username:
        user = User.query.filter_by(username=username).first()
        if not user:
            session.pop('username', None)

def checkActionDelay():
    last_action_time = session.get('last_action_time')
    current_time = datetime.now().timestamp()
    delay = 10
    if last_action_time and current_time - last_action_time < delay:
        return False
    session['last_action_time'] = current_time
    return True

base_html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <script>
        let notificationCount = {{ get_unread_notifications_count() }};
        function updateNotificationBadge() {
            const badge = document.getElementById('notification-badge');
            if (badge) {
                if (notificationCount > 0) {
                    badge.textContent = notificationCount;
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            }
        }
        function showNotification(message, type) {
            const notification = document.createElement('div');
            notification.className = `fixed top-4 right-4 p-4 rounded-md shadow-md transform transition-all duration-500 ease-in-out translate-x-full opacity-0 ${type === 'success' ? 'bg-green-500' : 'bg-red-500'} text-white z-50`;
            notification.innerHTML = `
                <div class="flex items-center">
                    <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'} mr-2"></i>
                    <span>${message}</span>
                </div>
            `;
            document.body.appendChild(notification);
            setTimeout(() => {
                notification.classList.remove('translate-x-full', 'opacity-0');
            }, 100);
            setTimeout(() => {
                notification.classList.add('translate-x-full', 'opacity-0');
                setTimeout(() => {
                    if (notification.parentNode) {
                        document.body.removeChild(notification);
                    }
                }, 500);
            }, 3000);
        }
        {% if notification %}
            document.addEventListener('DOMContentLoaded', function() {
                showNotification("{{ notification.message }}", "{{ notification.type }}");
            });
        {% endif %}
        async function likePost(postId) {
            const likeBtn = document.getElementById(`like-btn-${postId}`);
            likeBtn.classList.add('animate-pulse');
            try {
                const response = await fetch(`/like/${postId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                const data = await response.json();
                if (data.success) {
                    const likeCount = document.getElementById(`like-count-${postId}`);
                    likeCount.textContent = data.likes;
                    likeCount.classList.add('animate-bounce');
                    setTimeout(() => likeCount.classList.remove('animate-bounce'), 1000);
                    if (data.liked) {
                        likeBtn.innerHTML = '<i class="fas fa-heart text-red-500 animate-pulse"></i>';
                        likeBtn.classList.add('animate-bounce');
                    } else {
                        likeBtn.innerHTML = '<i class="far fa-heart"></i>';
                    }
                    setTimeout(() => likeBtn.classList.remove('animate-bounce'), 500);
                } else if (data.error === "Необходимо войти") {
                    window.location.href = "/login";
                }
            } catch (error) {
                console.error('Error liking post:', error);
            } finally {
                likeBtn.classList.remove('animate-pulse');
            }
        }
        async function deletePost(postId) {
            if (confirm('Вы уверены, что хотите удалить этот пост?')) {
                const deleteBtn = document.querySelector(`button[onclick="deletePost(${postId})"]`);
                deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                try {
                    const response = await fetch(`/delete/${postId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });
                    const data = await response.json();
                    if (data.success) {
                        showNotification(data.message, 'success');
                        const postElement = deleteBtn.closest('.post-container');
                        postElement.classList.add('animate-pulse', 'opacity-50');
                        setTimeout(() => {
                            window.location.href = data.redirect;
                        }, 1000);
                    } else {
                        showNotification(data.message, 'error');
                        deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
                    }
                } catch (error) {
                    console.error('Error deleting post:', error);
                    deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
                }
            }
        }
        async function submitForm(event, successMessage) {
            event.preventDefault();
            const form = event.target;
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Загрузка...';
            submitBtn.disabled = true;
            try {
                const formData = new FormData(form);
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    showNotification(data.message || successMessage, 'success');
                    if (data.redirect) {
                        setTimeout(() => {
                            window.location.href = data.redirect;
                        }, 1000);
                    }
                } else {
                    showNotification(data.message, 'error');
                }
            } catch (error) {
                showNotification('Произошла ошибка', 'error');
            } finally {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        }
        function registerUser(event) {
            return submitForm(event, 'Регистрация успешна!');
        }
        function loginUser(event) {
            return submitForm(event, 'Вход выполнен!');
        }
        function createPost(event) {
            return submitForm(event, 'Пост создан!');
        }
        function toggleReplyForm(commentId) {
            const replyForm = document.getElementById(`reply-form-${commentId}`);
            replyForm.classList.toggle('hidden');
            if (!replyForm.classList.contains('hidden')) {
                replyForm.classList.add('animate-fadeIn');
                const textarea = replyForm.querySelector('textarea');
                if (textarea) textarea.focus();
            }
        }
        function toggleNotifications() {
            const dropdown = document.getElementById('notifications-dropdown');
            dropdown.classList.toggle('hidden');
            if (!dropdown.classList.contains('hidden')) {
                loadNotifications();
            }
        }
        async function loadNotifications() {
            try {
                const response = await fetch('/notifications');
                const data = await response.json();
                const container = document.getElementById('notifications-container');
                if (data.notifications && data.notifications.length > 0) {
                    container.innerHTML = data.notifications.map(notif => `
                        <div class="p-3 border-b border-blue-700 ${notif.is_read ? 'opacity-60' : 'bg-blue-800'} hover:bg-blue-700 transition-colors">
                            <div class="text-sm">
                                <strong>${notif.from_user}</strong> ${notif.message}
                            </div>
                            <div class="text-xs text-blue-300 mt-1">${notif.created_at}</div>
                        </div>
                    `).join('');
                } else {
                    container.innerHTML = '<div class="p-3 text-center text-blue-300">Нет уведомлений</div>';
                }
                if (data.unread_count !== notificationCount) {
                    notificationCount = data.unread_count;
                    updateNotificationBadge();
                }
            } catch (error) {
                console.error('Error loading notifications:', error);
            }
        }
        async function markAllNotificationsRead() {
            try {
                await fetch('/notifications/mark-read', { method: 'POST' });
                notificationCount = 0;
                updateNotificationBadge();
                loadNotifications();
            } catch (error) {
                console.error('Error marking notifications as read:', error);
            }
        }
        function checkActionDelay() {
            const lastActionTime = sessionStorage.getItem('lastActionTime');
            const currentTime = new Date().getTime();
            const delay = 10000;
            if (lastActionTime && currentTime - lastActionTime < delay) {
                const remainingTime = Math.ceil((delay - (currentTime - lastActionTime)) / 1000);
                showNotification(`Подождите ${remainingTime} секунд перед следующим действием!`, 'error');
                return false;
            }
            sessionStorage.setItem('lastActionTime', currentTime);
            return true;
        }
        document.addEventListener('DOMContentLoaded', function() {
            updateNotificationBadge();
            document.addEventListener('click', function(e) {
                const notifDropdown = document.getElementById('notifications-dropdown');
                const notifButton = document.querySelector('[onclick="toggleNotifications()"]');
                if (!notifDropdown.contains(e.target) && !notifButton.contains(e.target)) {
                    notifDropdown.classList.add('hidden');
                }
            });
        });
        setInterval(() => {
            if (document.getElementById('notifications-dropdown') && !document.getElementById('notifications-dropdown').classList.contains('hidden')) {
                loadNotifications();
            }
        }, 30000);
    </script>
    <style>
        body {
            background-color: #0f172a;
            color: #e2e8f0;
        }
        .bg-white, .bg-gray-900 {
            background-color: #1e3a8a;
        }
        .text-gray-900 {
            color: #e2e8f0;
        }
        .text-gray-500 {
            color: #94a3b8;
        }
        .text-gray-600 {
            color: #cbd5e1;
        }
        .border-gray-200 {
            border-color: #334155;
        }
        input, textarea, button {
            background-color: #1e3a8a;
            color: #e2e8f0;
            border-color: #334155;
        }
        input::placeholder, textarea::placeholder {
            color: #94a3b8;
        }
        a {
            color: #3b82f6;
        }
        .nav-link {
            text-decoration: none !important;
        }
        .nav-link:hover {
            color: #60a5fa;
            text-decoration: none !important;
        }
        .post-container {
            background-color: #1e3a8a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            transition: all 0.3s ease;
        }
        .post-container:hover {
            border-color: #3b82f6;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
        }
        .post-title {
            color: #60a5fa;
        }
        .post-content {
            color: #e2e8f0;
        }
        .comment-container {
            background-color: #1e40af;
            border: 1px solid #2563eb;
            border-radius: 8px;
            padding: 16px;
            margin-top: 8px;
            transition: all 0.3s ease;
        }
        .comment-container:hover {
            background-color: #1d4ed8;
        }
        .comment-content {
            color: #e2e8f0;
        }
        .bg-white, .bg-gray-100, .bg-gray-50 {
            background-color: #1e3a8a !important;
        }
        .shadow-md, .shadow-lg, .shadow-xl {
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
            animation: fadeIn 0.3s ease-out;
        }
        .notification-badge {
            position: absolute;
            top: -8px;
            right: -8px;
            background-color: #ef4444;
            color: white;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }
        .animate-pulse {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: .5;
            }
        }
        .animate-bounce {
            animation: bounce 1s infinite;
        }
        @keyframes bounce {
            0%, 100% {
                transform: translateY(-25%);
                animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
            }
            50% {
                transform: none;
                animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
            }
        }
    </style>
</head>
<body class="bg-blue-950 text-blue-100">
    <div class="max-w-6xl mx-auto py-8 px-4">
        <div class="mb-6 flex justify-between items-center">
            <div class="flex items-center">
                <img src="{{ url_for('serve_logo') }}" alt="NerestReddit Logo" class="h-10 mr-2">
                <h1 class="text-3xl font-bold text-red-500">
                    <a href='{{ url_for('index') }}' class="nav-link hover:text-red-400 transition-colors">NerestReddit</a>
                </h1>
            </div>
            <div class="flex items-center space-x-4">
                {% if session.get('username') %}
                    <div class="relative">
                        <button onclick="toggleNotifications()" class="relative text-blue-300 hover:text-blue-100 transition-colors p-2">
                            <i class="fas fa-bell text-xl"></i>
                            <span id="notification-badge" class="notification-badge hidden">0</span>
                        </button>
                        <div id="notifications-dropdown" class="hidden absolute right-0 mt-2 w-80 bg-blue-900 border border-blue-700 rounded-lg shadow-xl z-50">
                            <div class="p-3 border-b border-blue-700 flex justify-between items-center">
                                <h3 class="font-semibold text-blue-200">Уведомления</h3>
                                <button onclick="markAllNotificationsRead()" class="text-xs text-blue-400 hover:text-blue-200">
                                    Отметить все как прочитанные
                                </button>
                            </div>
                            <div id="notifications-container" class="max-h-64 overflow-y-auto">
                                <div class="p-3 text-center text-blue-300">Загрузка...</div>
                            </div>
                        </div>
                    </div>
                    <span class="text-blue-300">Привет, {{ session['username'] }}!</span>
                    <a href="{{ url_for('create_post') }}" class="text-blue-400 hover:text-blue-200 transition-colors nav-link">Создать пост</a>
                    <a href="{{ url_for('logout') }}" class="text-blue-400 hover:text-blue-200 transition-colors nav-link">Выйти</a>
                {% else %}
                    <a href="{{ url_for('login') }}" class="text-blue-400 hover:text-blue-200 transition-colors nav-link">Войти</a>
                    <a href="{{ url_for('register') }}" class="text-blue-400 hover:text-blue-200 transition-colors nav-link">Регистрация</a>
                {% endif %}
            </div>
        </div>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    posts = Post.query.order_by(Post.created_at.desc()).all()
    posts_html = "".join(
        f"""
        <div class='post-container'>
            <h2 class='text-xl font-semibold post-title'><a href='{url_for('view_post', post_id=post.id)}' class="nav-link hover:text-blue-300 transition-colors">{post.title}</a></h2>
            <p class='mt-2 post-content'>{post.content}</p>
            <div class='flex justify-between items-center mt-4'>
                <p class='text-sm text-blue-300'>Автор: {post.author} | {post.created_at.strftime('%d.%m.%Y %H:%M')}</p>
                <div class='flex items-center'>
                    <button id="like-btn-{post.id}" onclick="likePost({post.id})" class="mr-1 text-blue-300 hover:text-blue-500 transition-all duration-200">
                        <i class="{'fas text-red-500' if user_liked_post(post.id) else 'far'} fa-heart"></i>
                    </button>
                    <span id="like-count-{post.id}" class="text-blue-300 mr-4">{post.likes}</span>
                    <a href="{url_for('view_post', post_id=post.id)}" class="text-blue-400 hover:text-blue-200 transition-colors nav-link">
                        <i class="fas fa-comments mr-1"></i>Комментарии
                    </a>
                    {f'<button onclick="deletePost({post.id})" class="ml-4 text-red-500 hover:text-red-300 transition-colors"><i class="fas fa-trash"></i></button>' if session.get('username') == post.author else ''}
                </div>
            </div>
        </div>
        """ for post in posts
    )
    return render_template_string(base_html, title="Главная", content=posts_html, get_unread_notifications_count=get_unread_notifications_count)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if is_logged_in():
        return redirect(url_for('index'))
    error = ""
    notification = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if not username or not password:
            return jsonify({"success": False, "message": "Пожалуйста, заполните все поля."})
        elif User.query.filter_by(username=username).first():
            return jsonify({"success": False, "message": "Пользователь уже существует."})
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            session['username'] = new_user.username
            return jsonify({"success": True, "message": "Аккаунт успешно создан!", "redirect": url_for('index')})
    return render_template_string(base_html, title="Регистрация", content=render_register_form(error), notification=notification, get_unread_notifications_count=get_unread_notifications_count)

def render_register_form(error):
    return f"""
    <div class="bg-blue-900 p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4 text-blue-200">Регистрация</h2>
        {"<p class='text-red-400 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4" onsubmit="registerUser(event)">
            <input name="username" class="w-full p-2 border rounded bg-blue-800 text-blue-100 focus:border-blue-400 transition-colors" placeholder="Имя пользователя" required>
            <input type="password" name="password" class="w-full p-2 border rounded bg-blue-800 text-blue-100 focus:border-blue-400 transition-colors" placeholder="Пароль" required>
            <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded w-full hover:bg-blue-500 transition-colors transform hover:scale-105">Зарегистрироваться</button>
        </form>
        <p class="mt-4 text-sm text-blue-300">Уже есть аккаунт? <a href="{url_for('login')}" class="text-blue-400 nav-link hover:text-blue-200 transition-colors">Войти</a></p>
    </div>
    """

def render_login_form(error):
    return f"""
    <div class="bg-blue-900 p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4 text-blue-200">Вход</h2>
        {"<p class='text-red-400 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4" onsubmit="loginUser(event)">
            <input name="username" class="w-full p-2 border rounded bg-blue-800 text-blue-100 focus:border-blue-400 transition-colors" placeholder="Имя пользователя" required>
            <input type="password" name="password" class="w-full p-2 border rounded bg-blue-800 text-blue-100 focus:border-blue-400 transition-colors" placeholder="Пароль" required>
            <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded w-full hover:bg-blue-500 transition-colors transform hover:scale-105">Войти</button>
        </form>
        <p class="mt-4 text-sm text-blue-300">Нет аккаунта? <a href="{url_for('register')}" class="text-blue-400 nav-link hover:text-blue-200 transition-colors">Зарегистрироваться</a></p>
    </div>
    """

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('index'))
    error = ""
    notification = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if not username or not password:
            return jsonify({"success": False, "message": "Пожалуйста, заполните все поля."})
        else:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['username'] = user.username
                return jsonify({"success": True, "message": "Успешный вход!", "redirect": url_for('index')})
            else:
                return jsonify({"success": False, "message": "Неверные имя пользователя или пароль."})
    return render_template_string(base_html, title="Вход", content=render_login_form(error), notification=notification, get_unread_notifications_count=get_unread_notifications_count)

@app.route('/logout')
def logout():
    if 'username' in session:
        session.pop('username', None)
        return redirect(url_for('login') + '?logged_out=1')
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if not is_logged_in():
        return redirect(url_for('login'))
    error = ""
    notification = None
    if request.method == 'POST':
        if not checkActionDelay():
            return jsonify({"success": False, "message": "Подождите перед следующим действием!"})
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        if not title or not content:
            return jsonify({"success": False, "message": "Заполните все поля."})
        else:
            post = Post(title=title, content=content, author=session['username'])
            db.session.add(post)
            db.session.commit()
            return jsonify({"success": True, "message": "Пост успешно создан!", "redirect": url_for('index')})
    form = f"""
    <div class="bg-blue-900 p-6 rounded-xl shadow-md max-w-2xl mx-auto">
        <h2 class="text-xl font-bold mb-4 text-blue-200">Новый пост</h2>
        {"<p class='text-red-400 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4" onsubmit="createPost(event)">
            <input name="title" class="w-full p-2 border rounded bg-blue-800 text-blue-100 focus:border-blue-400 transition-colors" placeholder="Заголовок" required>
            <textarea name="content" class="w-full p-2 border rounded h-32 bg-blue-800 text-blue-100 focus:border-blue-400 transition-colors resize-none" placeholder="Содержание..." required></textarea>
            <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded w-full hover:bg-blue-500 transition-colors transform hover:scale-105">Опубликовать</button>
        </form>
    </div>
    """
    return render_template_string(base_html, title="Создать пост", content=form, notification=notification, get_unread_notifications_count=get_unread_notifications_count)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    if not is_logged_in():
        return redirect(url_for('login'))
    post = Post.query.get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post_id, parent_id=None).order_by(Comment.created_at).all()
    def render_comments(comments):
        comments_html = ""
        for comment in comments:
            replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.created_at).all()
            replies_html = render_comments(replies) if replies else ""
            comments_html += f"""
            <div class="comment-container">
                <div class="flex items-center">
                    <span class="font-medium text-blue-200">{comment.author}</span>
                    <span class="text-xs text-blue-300 ml-2">{comment.created_at.strftime('%d.%m.%Y %H:%M')}</span>
                </div>
                <p class="mt-1 comment-content">{comment.content}</p>
                <div class="ml-4 mt-2">
                    <a href="#" onclick="toggleReplyForm({comment.id}); return false;" class="text-blue-400 hover:text-blue-200 transition-colors nav-link text-sm">
                        <i class="fas fa-reply mr-1"></i>Ответить
                    </a>
                    <div id="reply-form-{comment.id}" class="hidden mt-2">
                        <form action="{url_for('add_comment', post_id=post.id)}" method="post" class="flex flex-col gap-2">
                            <input type="hidden" name="parent_id" value="{comment.id}">
                            <textarea name="content" class="w-full p-2 border rounded h-24 bg-blue-900 text-gray-200 focus:border-blue-400 transition-colors resize-none" placeholder="Добавить ответ..." required></textarea>
                            <button type="submit" class="bg-blue-500 text-white px-4 py-2 rounded self-end hover:bg-blue-600 transition-colors transform hover:scale-105">Отправить</button>
                        </form>
                    </div>
                </div>
                <div class="ml-4 mt-2">
                    {replies_html}
                </div>
            </div>
            """
        return comments_html
    comments_html = render_comments(comments)
    content = f"""
    <div class="post-container">
        <h1 class="text-2xl font-bold post-title mb-2">{post.title}</h1>
        <p class="mb-4 post-content">{post.content}</p>
        <div class="flex justify-between items-center mb-6">
            <p class="text-sm text-blue-300">Автор: {post.author} | {post.created_at.strftime('%d.%m.%Y %H:%M')}</p>
            <div class="flex items-center">
                <button id="like-btn-{post.id}" onclick="likePost({post.id})" class="mr-1 text-blue-300 hover:text-blue-500 transition-all duration-200">
                    <i class="{'fas text-red-500' if user_liked_post(post.id) else 'far'} fa-heart"></i>
                </button>
                <span id="like-count-{post.id}" class="text-blue-300 mr-4">{post.likes}</span>
                {f'<button onclick="deletePost({post.id})" class="text-red-500 hover:text-red-300 transition-colors"><i class="fas fa-trash"></i></button>' if session.get('username') == post.author else ''}
            </div>
        </div>
        <div class="mt-8">
            <h3 class="text-xl font-semibold mb-4 text-blue-200">
                <i class="fas fa-comments mr-2"></i>Комментарии
            </h3>
            <div class="mb-6">
                <form action="{url_for('add_comment', post_id=post.id)}" method="post" class="flex flex-col gap-2" onsubmit="event => {{ if (checkActionDelay()) {{ event.preventDefault(); const form = event.target; const formData = new FormData(form); fetch(form.action, {{ method: 'POST', body: formData }}).then(response => response.json()).then(data => {{ if (data.success) {{ showNotification(data.message, 'success'); setTimeout(() => {{ window.location.href = data.redirect; }}, 1000); }} else {{ showNotification(data.message, 'error'); }} }}).catch(error => {{ showNotification('Произошла ошибка', 'error'); }}); }} }} else {{ showNotification('Подождите перед следующим действием!', 'error'); return false; }}">
                    <textarea name="content" class="w-full p-2 border rounded h-24 bg-blue-900 text-gray-200 focus:border-blue-400 transition-colors resize-none" placeholder="Добавить комментарий..." required></textarea>
                    <button type="submit" class="bg-blue-500 text-white px-4 py-2 rounded self-end hover:bg-blue-600 transition-colors transform hover:scale-105">Отправить</button>
                </form>
            </div>
            <div class="space-y-4">
                {comments_html if comments else "<p class='text-blue-300'>Пока нет комментариев</p>"}
            </div>
        </div>
    </div>
    """
    return render_template_string(base_html, title=post.title, content=content, get_unread_notifications_count=get_unread_notifications_count)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if not is_logged_in():
        return redirect(url_for('login'))
    if not checkActionDelay():
        return jsonify({"success": False, "message": "Подождите перед следующим действием!"})
    content = request.form['content'].strip()
    parent_id = request.form.get('parent_id')
    if not content:
        return jsonify({"success": False, "message": "Заполните все поля."})
    post = Post.query.get_or_404(post_id)
    if parent_id:
        parent_comment = Comment.query.get(parent_id)
        if not parent_comment or parent_comment.post_id != post_id:
            return jsonify({"success": False, "message": "Неверный комментарий."})
    comment = Comment(
        content=content,
        author=session['username'],
        post_id=post_id,
        parent_id=parent_id
    )
    db.session.add(comment)
    db.session.commit()
    post_author_user = User.query.filter_by(username=post.author).first()
    if post_author_user and post_author_user.username != session['username']:
        if parent_id:
            create_notification(
                post_author_user.id,
                'reply',
                f'ответил на ваш комментарий в посте \"{post.title}\"',
                session['username'],
                post_id=post_id,
                comment_id=comment.id
            )
        else:
            create_notification(
                post_author_user.id,
                'comment',
                f'прокомментировал ваш пост \"{post.title}\"',
                session['username'],
                post_id=post_id,
                comment_id=comment.id
            )
    if parent_id:
        parent_comment = Comment.query.get(parent_id)
        parent_author_user = User.query.filter_by(username=parent_comment.author).first()
        if parent_author_user and parent_author_user.username != session['username'] and parent_author_user.username != post.author:
            create_notification(
                parent_author_user.id,
                'reply',
                f'ответил на ваш комментарий в посте \"{post.title}\"',
                session['username'],
                post_id=post_id,
                comment_id=comment.id
            )
    return jsonify({"success": True, "message": "Комментарий успешно добавлен!", "redirect": url_for('view_post', post_id=post_id)})

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if not is_logged_in():
        return jsonify({"success": False, "error": "Необходимо войти"}), 401
    user_id = get_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Пользователь не найден"}), 401
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        post.likes -= 1
        liked = False
    else:
        new_like = Like(user_id=user_id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1
        liked = True
        post_author_user = User.query.filter_by(username=post.author).first()
        if post_author_user and post_author_user.id != user_id:
            create_notification(
                post_author_user.id,
                'like',
                f'поставил лайк вашему посту \"{post.title}\"',
                session['username'],
                post_id=post_id
            )
    db.session.commit()
    return jsonify({"success": True, "likes": post.likes, "liked": liked})

@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not is_logged_in():
        return jsonify({"success": False, "message": "Необходимо войти"}), 401
    post = Post.query.get_or_404(post_id)
    if post.author != session['username']:
        return jsonify({"success": False, "message": "У вас нет прав для удаления этого поста"}), 403
    Like.query.filter_by(post_id=post_id).delete()
    Notification.query.filter_by(post_id=post_id).delete()
    comments_to_delete = Comment.query.filter_by(post_id=post_id).all()
    for comment in comments_to_delete:
        Notification.query.filter_by(comment_id=comment.id).delete()
    Comment.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    return jsonify({
        "success": True,
        "message": "Пост успешно удален",
        "redirect": url_for('index')
    })

@app.route('/notifications')
def get_notifications():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(20).all()
    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'type': notif.type,
            'message': notif.message,
            'from_user': notif.from_user,
            'post_id': notif.post_id,
            'comment_id': notif.comment_id,
            'is_read': notif.is_read,
            'created_at': notif.created_at.strftime('%d.%m.%Y %H:%M')
        })
    return jsonify({
        "notifications": notifications_data,
        "unread_count": unread_count
    })

@app.route('/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({"success": True})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)
