from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import User, UserIngredient, Ingredient, RecipeView, Recipe, Favorite, Post, PostView, Message
from app import db
from datetime import datetime, timedelta

# 创建蓝图
bp = Blueprint('user', __name__, template_folder='templates')

@bp.route('/')
@login_required
def index():
    # 获取用户食材
    user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
    
    # 获取最近浏览记录 - 支持分页
    view_page = request.args.get('view_page', 1, type=int)
    view_per_page = 6
    
    recent_views = []
    viewed_items = set()  # 用于去重
    
    # 获取菜谱浏览记录，按时间倒序排序
    recipe_views = RecipeView.query.filter_by(user_id=current_user.id).order_by(RecipeView.viewed_at.desc()).all()
    for view in recipe_views:
        if view.recipe_id not in viewed_items:
            recipe = Recipe.query.get(view.recipe_id)
            if recipe:
                # 将 UTC 时间转换为东八区时间
                recipe.viewed_at = view.viewed_at + timedelta(hours=8)
                recent_views.append(recipe)
                viewed_items.add(view.recipe_id)
    
    # 获取帖子浏览记录，按时间倒序排序
    post_views = PostView.query.filter_by(user_id=current_user.id).order_by(PostView.viewed_at.desc()).all()
    for view in post_views:
        if view.post_id not in viewed_items:
            post = Post.query.get(view.post_id)
            if post:
                # 将 UTC 时间转换为东八区时间
                post.viewed_at = view.viewed_at + timedelta(hours=8)
                recent_views.append(post)
                viewed_items.add(view.post_id)
    
    # 按浏览时间排序
    recent_views.sort(key=lambda x: x.viewed_at, reverse=True)
    
    # 手动分页
    total_views = len(recent_views)
    view_pagination = {
        'page': view_page,
        'per_page': view_per_page,
        'total': total_views,
        'pages': (total_views + view_per_page - 1) // view_per_page,
        'has_prev': view_page > 1,
        'has_next': view_page < ((total_views + view_per_page - 1) // view_per_page),
        'prev_num': view_page - 1,
        'next_num': view_page + 1,
        'iter_pages': lambda left_edge=1, right_edge=1, left_current=1, right_current=2: range(1, (total_views + view_per_page - 1) // view_per_page + 1)
    }
    
    # 切片获取当前页数据
    start = (view_page - 1) * view_per_page
    end = start + view_per_page
    recent_views = recent_views[start:end]
    
    # 获取收藏记录 - 支持分页
    fav_page = request.args.get('fav_page', 1, type=int)
    fav_per_page = 6
    
    favorites = []
    favorite_records = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    for fav in favorite_records:
        if fav.target_type == 'recipe':
            item = Recipe.query.get(fav.target_id)
        else:
            item = Post.query.get(fav.target_id)
        if item:
            favorites.append(item)
    
    # 手动分页
    total_favs = len(favorites)
    fav_pagination = {
        'page': fav_page,
        'per_page': fav_per_page,
        'total': total_favs,
        'pages': (total_favs + fav_per_page - 1) // fav_per_page,
        'has_prev': fav_page > 1,
        'has_next': fav_page < ((total_favs + fav_per_page - 1) // fav_per_page),
        'prev_num': fav_page - 1,
        'next_num': fav_page + 1,
        'iter_pages': lambda left_edge=1, right_edge=1, left_current=1, right_current=2: range(1, (total_favs + fav_per_page - 1) // fav_per_page + 1)
    }
    
    # 切片获取当前页数据
    start = (fav_page - 1) * fav_per_page
    end = start + fav_per_page
    favorites = favorites[start:end]
    
    return render_template('user/index.html', user_ingredients=user_ingredients, 
                          recent_views=recent_views, view_pagination=view_pagination,
                          favorites=favorites, fav_pagination=fav_pagination)

@bp.route('/ingredients')
@login_required
def ingredients():
    user_ingredients = UserIngredient.query.filter_by(user_id=current_user.id).all()
    return render_template('user/ingredients.html', user_ingredients=user_ingredients)

@bp.route('/add_ingredient', methods=['GET', 'POST'])
@login_required
def add_ingredient():
    if request.method == 'POST':
        ingredient_name = request.form['ingredient_name']
        category = request.form['category']
        added_at = request.form.get('added_at')
        # 查找或创建食材
        ingredient = Ingredient.query.filter_by(name=ingredient_name).first()
        if not ingredient:
            ingredient = Ingredient(name=ingredient_name, category=category)
            db.session.add(ingredient)
            db.session.commit()
        # 添加到用户食材
        user_ingredient = UserIngredient(user_id=current_user.id, ingredient_id=ingredient.id)
        if added_at:
            from datetime import datetime
            from app.models import TZ
            user_ingredient.added_at = TZ.localize(datetime.strptime(added_at, '%Y-%m-%dT%H:%M'))
        db.session.add(user_ingredient)
        db.session.commit()
        return redirect(url_for('ingredient.index'))
    return render_template('user/add_ingredient.html')

@bp.route('/remove_ingredient/<int:id>')
@login_required
def remove_ingredient(id):
    user_ingredient = UserIngredient.query.filter_by(id=id, user_id=current_user.id).first()
    if user_ingredient:
        db.session.delete(user_ingredient)
        db.session.commit()
    return redirect(url_for('user.ingredients'))



@bp.route('/favorite/<string:target_type>/<int:target_id>')
@login_required
def favorite(target_type, target_id):
    print(f"收藏请求: target_type={target_type}, target_id={target_id}, user_id={current_user.id}")
    
    # 检查目标类型是否有效
    if target_type not in ['recipe', 'post']:
        print(f"无效的目标类型: {target_type}")
        return jsonify({'success': False, 'message': '无效的目标类型'})
    
    # 检查目标是否存在
    if target_type == 'recipe':
        target = Recipe.query.get(target_id)
        if target:
            print(f"找到菜谱: {target.title}")
        else:
            print(f"菜谱不存在: {target_id}")
    else:
        target = Post.query.get(target_id)
        if target:
            print(f"找到帖子: {target.title}")
        else:
            print(f"帖子不存在: {target_id}")
    
    if not target:
        return jsonify({'success': False, 'message': '目标不存在'})
    
    # 检查是否已经收藏
    existing_favorite = Favorite.query.filter_by(user_id=current_user.id, target_type=target_type, target_id=target_id).first()
    print(f"现有收藏: {existing_favorite}")
    
    favorited = False
    
    if existing_favorite:
        # 已收藏，取消收藏
        print(f"取消收藏: {target_type} {target_id}")
        db.session.delete(existing_favorite)
    else:
        # 未收藏，添加收藏
        print(f"添加收藏: {target_type} {target_id}")
        new_favorite = Favorite(user_id=current_user.id, target_type=target_type, target_id=target_id)
        db.session.add(new_favorite)
        favorited = True
    
    # 提交事务
    try:
        db.session.commit()
        print(f"事务提交成功，favorited={favorited}")
        
        # 发送消息通知（如果是收藏操作且目标是帖子）
        if favorited and target_type == 'post':
            post = Post.query.get(target_id)
            if post and post.user_id != current_user.id:
                # 向帖子作者发送消息
                message_title = "帖子被收藏"
                message_content = f"您的帖子《{post.title}》被 {current_user.username} 收藏了！"
                new_message = Message(
                    user_id=post.user_id,
                    title=message_title,
                    content=message_content
                )
                db.session.add(new_message)
                db.session.commit()
    except Exception as e:
        print(f"事务提交失败: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': '操作失败'})
    
    # 再次检查收藏状态
    check_favorite = Favorite.query.filter_by(user_id=current_user.id, target_type=target_type, target_id=target_id).first()
    print(f"操作后收藏状态: {check_favorite}")
    
    return jsonify({'success': True, 'favorited': favorited})

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # 获取表单数据
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 更新用户名和邮箱
        current_user.username = username
        current_user.email = email
        
        # 检查是否修改了密码
        if password:
            # 验证密码是否一致
            if password != confirm_password:
                flash('两次输入的密码不一致', 'danger')
                return redirect(url_for('user.settings'))
            # 更新密码
            from werkzeug.security import generate_password_hash
            current_user.password = generate_password_hash(password)
        
        # 保存到数据库
        try:
            db.session.commit()
            flash('设置已保存', 'success')
            return redirect(url_for('user.index'))
        except Exception as e:
            db.session.rollback()
            flash('保存失败，请稍后重试', 'danger')
            return redirect(url_for('user.settings'))
    return render_template('user/settings.html')

@bp.route('/messages')
@login_required
def messages():
    # 获取用户的消息，按时间倒序排序
    messages = Message.query.filter_by(user_id=current_user.id).order_by(Message.created_at.desc()).all()
    # 标记所有消息为已读
    unread_messages = Message.query.filter_by(user_id=current_user.id, is_read=False).all()
    for msg in unread_messages:
        msg.is_read = True
    db.session.commit()
    return render_template('user/messages.html', messages=messages)

@bp.route('/unread-message-count')
@login_required
def unread_message_count():
    # 获取用户未读消息数量
    count = Message.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@bp.route('/account-management')
@login_required
def account_management():
    # 检查用户是否为管理员
    if not current_user.is_admin:
        flash('无权限访问此页面', 'danger')
        return redirect(url_for('user.index'))
    
    # 获取所有用户
    users = User.query.all()
    return render_template('user/account_management.html', users=users)

@bp.route('/delete-user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # 检查用户是否为管理员
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权限执行此操作'})
    
    # 不能删除自己
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': '不能删除自己的账户'})
    
    # 查找用户
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'})
    
    # 标记用户为已注销
    user.is_active = False
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': '用户已成功注销'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})

@bp.route('/restore-user/<int:user_id>', methods=['POST'])
def restore_user(user_id):
    # 检查用户是否为管理员
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权限执行此操作'})
    
    # 查找用户
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'})
    
    # 标记用户为活跃
    user.is_active = True
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': '用户已成功恢复'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})
