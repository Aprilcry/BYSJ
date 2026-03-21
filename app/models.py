from app import db
from datetime import datetime
from flask_login import UserMixin
import pytz

# 东八区时区
TZ = pytz.timezone('Asia/Shanghai')

# 获取东八区当前时间
def get_local_time():
    return datetime.now(TZ)

# 用户模型
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6))
    code_expires_at = db.Column(db.DateTime)
    reset_token = db.Column(db.String(100))
    reset_token_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=get_local_time)
    ingredients = db.relationship('UserIngredient', backref='user', lazy=True)
    recipe_views = db.relationship('RecipeView', backref='user', lazy=True)
    post_views = db.relationship('PostView', backref='user', lazy=True)

# 食材模型
class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255))
    user_ingredients = db.relationship('UserIngredient', backref='ingredient', lazy=True)
    recipe_ingredients = db.relationship('RecipeIngredient', backref='ingredient', lazy=True)

# 用户食材关联模型
class UserIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=get_local_time)

# 菜谱模型
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    video_url = db.Column(db.String(255))
    image_url = db.Column(db.String(255))
    prep_time = db.Column(db.Integer, nullable=False)  # 准备时间（分钟）
    cook_time = db.Column(db.Integer, nullable=False)  # 烹饪时间（分钟）
    difficulty = db.Column(db.String(20), nullable=False)  # 难度
    category = db.Column(db.String(50), nullable=False)
    taste = db.Column(db.String(20), nullable=False, default='咸口')  # 口味
    created_at = db.Column(db.DateTime, default=get_local_time)
    views = db.Column(db.Integer, default=0)
    month_views = db.Column(db.Integer, default=0)
    day_views = db.Column(db.Integer, default=0)
    ingredients = db.relationship('RecipeIngredient', backref='recipe', lazy=True)
    recipe_views = db.relationship('RecipeView', backref='recipe', lazy=True)

# 菜谱食材关联模型
class RecipeIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)

# 菜谱浏览记录模型
class RecipeView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=get_local_time)

# 帖子浏览记录模型
class PostView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=get_local_time)

# 搜索记录模型
class SearchRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), nullable=False)
    count = db.Column(db.Integer, default=1)
    last_searched = db.Column(db.DateTime, default=get_local_time)

# 厨艺广场帖子模型
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255))
    video_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    post_likes = db.relationship('PostLike', lazy=True, cascade='all, delete-orphan')
    post_views = db.relationship('PostView', backref='post', lazy=True)
    user = db.relationship('User', backref='posts')

# 厨艺广场评论模型
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_time)
    user = db.relationship('User', backref='comments')

# 帖子点赞模型
class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_time)
    # 添加唯一约束，确保一个用户只能对一个帖子点赞一次
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)
    user = db.relationship('User', backref='post_likes')
    post = db.relationship('Post')

# 收藏模型
class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)  # 'recipe' 或 'post'
    target_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_time)
    # 添加唯一约束，确保一个用户只能收藏一个目标一次
    __table_args__ = (db.UniqueConstraint('user_id', 'target_type', 'target_id', name='unique_user_target_favorite'),)
    user = db.relationship('User', backref='favorites')

# 用户行为记录模型
class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # view, like, comment, post
    target_id = db.Column(db.Integer, nullable=False)  # 帖子ID或评论ID
    created_at = db.Column(db.DateTime, default=get_local_time)
    user = db.relationship('User', backref='activities')

# 厨艺知识模型
class CookingTip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_time)

# 食材分类映射模型
class IngredientCategoryMap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredient_name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)

# 食材保质期映射模型
class IngredientShelfLife(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredient_name = db.Column(db.String(100), unique=True, nullable=False)
    shelf_life_days = db.Column(db.Integer, nullable=False)  # 保质期（天）

# 消息模型
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_time)
    user = db.relationship('User', backref='messages')
