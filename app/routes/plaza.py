from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Post, Comment, User, PostLike, Favorite, PostView, Message
from app import db
import os
from datetime import datetime

# 创建蓝图
bp = Blueprint('plaza', __name__)

@bp.route('/')
def index():
    search_query = request.args.get('search', '')
    
    if search_query:
        # 搜索功能
        posts = Post.query.filter(
            (Post.title.contains(search_query)) | 
            (Post.content.contains(search_query))
        ).order_by(Post.created_at.desc()).all()
    else:
        # 推荐算法
        if current_user.is_authenticated:
            # 获取用户已查看的帖子
            viewed_posts = [view.post_id for view in PostView.query.filter_by(user_id=current_user.id).all()]
            
            # 获取所有帖子
            all_posts = Post.query.all()
            
            # 计算每个帖子的推荐分数
            scored_posts = []
            for post in all_posts:
                # 基础分数：点赞数 + 浏览数 * 0.1 + 评论数 * 0.5
                base_score = post.likes + post.views * 0.1 + len(post.comments) * 0.5
                
                # 时间衰减因子：越新的帖子分数越高
                days_since_creation = (datetime.utcnow() - post.created_at).days
                time_factor = max(0.1, 1 / (1 + days_since_creation * 0.1))
                
                # 已查看惩罚：如果用户已查看过该帖子，降低分数
                viewed_penalty = 0.3 if post.id in viewed_posts else 1.0
                
                # 最终分数
                final_score = base_score * time_factor * viewed_penalty
                scored_posts.append((post, final_score))
            
            # 按分数排序
            scored_posts.sort(key=lambda x: x[1], reverse=True)
            posts = [post for post, score in scored_posts]
        else:
            # 未登录用户使用时间排序
            posts = Post.query.order_by(Post.created_at.desc()).all()
    
    return render_template('plaza/index.html', posts=posts, search_query=search_query)

@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        # 处理图片
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            image_filename = f"{title.replace(' ', '_')}.jpg"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            image_url = f"/static/uploads/{image_filename}"
        else:
            image_url = None
        
        # 处理视频
        if 'video' in request.files and request.files['video'].filename != '':
            video = request.files['video']
            video_filename = f"{title.replace(' ', '_')}.mp4"
            video_path = os.path.join(app.config['VIDEO_FOLDER'], video_filename)
            video.save(video_path)
            video_url = f"/static/videos/{video_filename}"
        else:
            video_url = None
        
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

@bp.route('/delete/<int:id>')
@login_required
def delete(id):
    post = Post.query.get(id)
    if post and post.user_id == current_user.id:
        # 删除相关评论
        comments = Comment.query.filter_by(post_id=id).all()
        for comment in comments:
            db.session.delete(comment)
        # 删除帖子
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('plaza.index'))

# 导入 app
from app import app
