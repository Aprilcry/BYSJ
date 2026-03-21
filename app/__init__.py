from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_mail import Mail
import os
from datetime import datetime, timedelta

# 创建应用
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

# 配置应用
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://aocjor:XxzAgt8llTP8dqDV@mysql7.sqlpub.com:3312/ljb_bysj'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'app', 'static', 'uploads')
app.config['VIDEO_FOLDER'] = os.path.join(os.getcwd(), 'app', 'static', 'videos')

# 邮件配置
app.config['MAIL_SERVER'] = 'smtp.qq.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@qq.com'  # 替换为你的QQ邮箱
app.config['MAIL_PASSWORD'] = 'your-email-password'  # 替换为你的QQ邮箱授权码
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@qq.com'  # 替换为你的QQ邮箱

# 确保上传和视频目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True)

# 初始化扩展
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
CORS(app)
mail = Mail(app)

# 加载用户的回调函数
@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))

# 导入模型
from app.models import User, Ingredient, UserIngredient, Recipe, RecipeIngredient, RecipeView, SearchRecord, Post, Comment, UserActivity, CookingTip, IngredientCategoryMap, IngredientShelfLife, Message

# 导入路由
from app.routes import auth, user, ingredient, recipe, recommendation, plaza, ai

# 注册蓝图
app.register_blueprint(auth.bp)
app.register_blueprint(user.bp, url_prefix='/user')
app.register_blueprint(ingredient.bp, url_prefix='/ingredient')
app.register_blueprint(recipe.bp, url_prefix='/recipe')
app.register_blueprint(recommendation.bp, url_prefix='/recommendation')
app.register_blueprint(plaza.bp, url_prefix='/plaza')
app.register_blueprint(ai.bp)

# 根路由
from flask import render_template
from flask_login import current_user

@app.route('/')
def index():
    return render_template('index.html')
