from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app.models import Post, Comment, User, PostLike, Favorite, PostView, Message, SearchRecord
from app import db, app
import os
import uuid
from datetime import datetime
import re

# 创建蓝图
bp = Blueprint('plaza', __name__)

@bp.route('/')
def index():
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'newest')  # newest 或 hot
    
    # 记录搜索关键词
    if search_query:
        # 查找是否已存在该关键词
        existing_record = SearchRecord.query.filter_by(keyword=search_query).first()
        if existing_record:
            # 更新计数和最后搜索时间
            existing_record.count += 1
            existing_record.last_searched = datetime.utcnow()
        else:
            # 创建新记录
            new_record = SearchRecord(keyword=search_query)
            db.session.add(new_record)
        db.session.commit()
        
        # 搜索功能
        posts = Post.query.filter(
            (Post.title.contains(search_query)) | 
            (Post.content.contains(search_query))
        )
    else:
        # 获取所有帖子
        posts = Post.query
    
    # 排序
    if sort_by == 'hot':
        # 按热度排序：浏览量 + 点赞数 × 2
        posts = sorted(posts.all(), key=lambda p: p.views + p.likes * 2, reverse=True)
    else:
        # 按时间倒序排序
        posts = posts.order_by(Post.created_at.desc()).all()
    
    return render_template('plaza/index.html', posts=posts, search_query=search_query, sort_by=sort_by)

@bp.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    if 'upload' not in request.files:
        # 尝试获取'file'字段（兼容其他编辑器）
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
    else:
        file = request.files['upload']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # 生成安全的文件名
    ext = os.path.splitext(file.filename)[1].lower()
    safe_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}{ext}"
    
    # 确保上传目录存在
    upload_folder = app.config.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'static', 'uploads'))
    os.makedirs(upload_folder, exist_ok=True)
    
    # 安全地保存文件（防范路径遍历攻击）
    file_path = os.path.join(upload_folder, safe_filename)
    file.save(file_path)
    
    # 返回文件URL
    file_url = f"/static/uploads/{safe_filename}"
    
    # CKEditor需要特定的响应格式
    if 'CKEditorFuncNum' in request.args:
        return f"<script>window.parent.CKEDITOR.tools.callFunction({request.args.get('CKEditorFuncNum')}, '{file_url}');</script>"
    else:
        return jsonify({'location': file_url})

@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        # 图片通过富文本编辑器上传，不需要单独处理
        image_url = None
        
        # 处理视频
        video_url = None
        if 'video' in request.files and request.files['video'].filename != '':
            video = request.files['video']
            ext = os.path.splitext(video.filename)[1].lower()
            safe_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}{ext}"
            
            # 确保视频目录存在
            video_folder = app.config.get('VIDEO_FOLDER', os.path.join(app.root_path, 'static', 'videos'))
            os.makedirs(video_folder, exist_ok=True)
            
            # 安全地保存文件（防范路径遍历攻击）
            file_path = os.path.join(video_folder, safe_filename)
            video.save(file_path)
            video_url = f"/static/videos/{safe_filename}"
        
        # 创建帖子
        new_post = Post(
            title=title,
            content=content,
            image_url=image_url,
            video_url=video_url,
            user_id=current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('plaza.index'))
    return render_template('plaza/add.html')

@bp.route('/detail/<int:id>')
def detail(id):
    post = Post.query.get(id)
    # 检查是否是从点赞操作重定向过来的
    referrer = request.headers.get('Referer', '')
    if 'like' not in referrer:
        # 只有不是从点赞操作重定向过来的才增加浏览量
        post.views += 1
        
        # 记录浏览历史
        if current_user.is_authenticated:
            # 检查是否已经存在相同的浏览记录
            existing_view = PostView.query.filter_by(user_id=current_user.id, post_id=id).first()
            if existing_view:
                # 更新浏览时间
                existing_view.viewed_at = datetime.utcnow()
            else:
                # 创建新的浏览记录
                new_view = PostView(user_id=current_user.id, post_id=id)
                db.session.add(new_view)
        
        db.session.commit()
    
    comments = Comment.query.filter_by(post_id=id).order_by(Comment.created_at.desc()).all()
    # 检查用户是否已点赞
    user_liked = False
    if current_user.is_authenticated:
        existing_like = PostLike.query.filter_by(user_id=current_user.id, post_id=id).first()
        if existing_like:
            user_liked = True
    
    # 检查是否已收藏
    favorited = False
    if current_user.is_authenticated:
        existing_favorite = Favorite.query.filter_by(user_id=current_user.id, target_type='post', target_id=id).first()
        if existing_favorite:
            favorited = True
    
    return render_template('plaza/detail.html', post=post, comments=comments, user_liked=user_liked, favorited=favorited)

@bp.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form['content']
    new_comment = Comment(
        content=content,
        post_id=post_id,
        user_id=current_user.id
    )
    db.session.add(new_comment)
    db.session.commit()
    
    # 发送消息通知
    post = Post.query.get(post_id)
    if post and post.user_id != current_user.id:
        # 向帖子作者发送消息
        message_title = "帖子被评论"
        # 处理评论内容，限制长度为10个字符
        comment_preview = content[:10] + '...' if len(content) > 10 else content
        message_content = f"您的帖子《{post.title}》被 {current_user.username} 评论了：{comment_preview}"
        new_message = Message(
            user_id=post.user_id,
            title=message_title,
            content=message_content
        )
        db.session.add(new_message)
        db.session.commit()
    
    return redirect(url_for('plaza.detail', id=post_id))

@bp.route('/like/<int:id>')
@login_required
def like(id):
    post = Post.query.get(id)
    # 检查用户是否已经点赞
    existing_like = PostLike.query.filter_by(user_id=current_user.id, post_id=id).first()
    liked = False
    if existing_like:
        # 已点赞，取消点赞
        db.session.delete(existing_like)
        post.likes -= 1
    else:
        # 未点赞，添加点赞
        new_like = PostLike(user_id=current_user.id, post_id=id)
        db.session.add(new_like)
        post.likes += 1
        liked = True
    # 发送消息通知（如果是点赞操作）
    if liked and post.user_id != current_user.id:
        # 向帖子作者发送消息
        message_title = "帖子被点赞"
        message_content = f"您的帖子《{post.title}》被 {current_user.username} 点赞了！"
        new_message = Message(
            user_id=post.user_id,
            title=message_title,
            content=message_content
        )
        db.session.add(new_message)
        db.session.commit()
    
    # 检查是否是AJAX请求
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'liked': liked,
            'likes': post.likes
        })
    else:
        return redirect(url_for('plaza.detail', id=id))

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get(id)
    if not post or (post.user_id != current_user.id and not current_user.is_admin):
        abort(403)
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        # 图片通过富文本编辑器上传，不需要单独处理
        
        # 处理视频
        if 'video' in request.files and request.files['video'].filename != '':
            video = request.files['video']
            ext = os.path.splitext(video.filename)[1].lower()
            safe_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}{ext}"
            
            # 确保视频目录存在
            video_folder = app.config.get('VIDEO_FOLDER', os.path.join(app.root_path, 'static', 'videos'))
            os.makedirs(video_folder, exist_ok=True)
            
            # 安全地保存文件（防范路径遍历攻击）
            file_path = os.path.join(video_folder, safe_filename)
            video.save(file_path)
            post.video_url = f"/static/videos/{safe_filename}"
        
        # 更新帖子
        post.title = title
        post.content = content
        post.updated_at = datetime.utcnow()
        
        db.session.commit()
        return redirect(url_for('plaza.detail', id=id))
    
    return render_template('plaza/edit.html', post=post)

@bp.route('/delete/<int:id>')
@login_required
def delete(id):
    post = Post.query.get(id)
    if post and (post.user_id == current_user.id or current_user.is_admin):
        # 删除相关评论
        comments = Comment.query.filter_by(post_id=id).all()
        for comment in comments:
            db.session.delete(comment)
        # 删除相关的点赞记录
        post_likes = PostLike.query.filter_by(post_id=id).all()
        for like in post_likes:
            db.session.delete(like)
        # 删除相关的浏览记录
        post_views = PostView.query.filter_by(post_id=id).all()
        for view in post_views:
            db.session.delete(view)
        # 删除相关的收藏记录
        favorites = Favorite.query.filter_by(target_type='post', target_id=id).all()
        for favorite in favorites:
            db.session.delete(favorite)
        # 删除帖子
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('plaza.index'))

# 导入 app
from app import app
