from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required
from app.models import User
from app import db
import bcrypt
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# 创建蓝图
bp = Blueprint('auth', __name__)

# 邮箱配置
SMTP_SERVER = 'smtp.qq.com'
SMTP_PORT = 587
SMTP_USER = '1518965403@qq.com'
SMTP_PASSWORD = 'mfwngrcfbhfqgadh'

# 生成4位验证码
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=4))

# 发送验证码邮件
def send_verification_email(email, code):
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = email
        msg['Subject'] = '智慧厨艺辅助系统 - 验证码'
        
        # 邮件内容
        body = f'您的验证码是: {code}，有效期为10分钟。请勿将验证码告诉他人。'
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 发送邮件
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        code = request.form['code']
        password = request.form['password']
        
        # 验证验证码
        user = User.query.filter_by(email=email).first()
        if user and user.verification_code == code and user.code_expires_at > datetime.utcnow():
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            user.username = username
            user.password = hashed_password.decode('utf-8')
            user.is_verified = True
            db.session.commit()
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid verification code or code expired')
    return render_template('auth/register.html')

@bp.route('/send-code', methods=['POST'])
def send_code():
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'success': False, 'message': '请输入邮箱'})
    
    # 生成验证码
    code = generate_verification_code()
    
    # 发送邮件
    if send_verification_email(email, code):
        # 保存验证码到数据库
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email)
            db.session.add(user)
        user.verification_code = code
        user.code_expires_at = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        return jsonify({'success': True, 'message': '验证码已发送'})
    else:
        return jsonify({'success': False, 'message': '验证码发送失败'})

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
