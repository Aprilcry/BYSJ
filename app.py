import os

# 设置ultralytics配置目录到当前项目目录
os.environ['ULTRALYTICS_CONFIG_DIR'] = os.path.join(os.getcwd(), 'ultralytics_config')

# 从app包导入应用实例
from app import app, db

# 全局变量，用于标记是否已经初始化
initialized = False

def check_expired_ingredients():
    """检查过期食材并发送邮件提醒"""
    from app.models import User, UserIngredient, Ingredient, IngredientShelfLife, get_local_time, Message
    from app import mail, db
    from flask_mail import Message
    from datetime import timedelta
    
    print("开始检查过期食材...")
    
    # 获取所有用户
    users = User.query.all()
    
    for user in users:
        # 获取用户的食材
        user_ingredients = UserIngredient.query.filter_by(user_id=user.id).all()
        expired_ingredients = []
        
        for user_ingredient in user_ingredients:
            # 获取食材信息
            ingredient = Ingredient.query.get(user_ingredient.ingredient_id)
            if not ingredient:
                continue
            
            # 获取保质期信息
            shelf_life = IngredientShelfLife.query.filter_by(ingredient_name=ingredient.name).first()
            if not shelf_life:
                continue
            
            # 计算是否过期
            if user_ingredient.added_at:
                days_since_added = (get_local_time() - user_ingredient.added_at).days
                if days_since_added > shelf_life.shelf_life_days:
                    expired_ingredients.append({
                        'name': ingredient.name,
                        'added_at': user_ingredient.added_at.strftime('%Y-%m-%d %H:%M'),
                        'expired_days': days_since_added - shelf_life.shelf_life_days
                    })
        
        # 如果有过期食材，发送邮件
        if expired_ingredients and user.email:
            print(f"用户 {user.username} 有 {len(expired_ingredients)} 个过期食材")
            
            # 构建邮件内容
            subject = "食材过期提醒"
            body = f"亲爱的 {user.username}：\n\n"
            body += "以下食材已经过期，请及时处理：\n\n"
            
            for item in expired_ingredients:
                body += f"- {item['name']}（添加时间：{item['added_at']}，已过期 {item['expired_days']} 天）\n"
            
            body += "\n智慧厨艺辅助系统"
            
            # 发送邮件
            try:
                msg = Message(subject, recipients=[user.email])
                msg.body = body
                mail.send(msg)
                print(f"已向 {user.email} 发送过期食材提醒邮件")
            except Exception as e:
                print(f"发送邮件失败：{str(e)}")
            
            # 创建平台内消息通知
            try:
                message_content = body.replace('\n', '<br>')
                new_message = Message(
                    user_id=user.id,
                    title=subject,
                    content=message_content
                )
                db.session.add(new_message)
                db.session.commit()
                print(f"已向用户 {user.username} 创建平台内过期食材提醒消息")
            except Exception as e:
                print(f"创建消息失败：{str(e)}")
                db.session.rollback()
    
    print("过期食材检查完成")


# 使用before_request装饰器，确保这些操作只执行一次
def initialize_app():
    global initialized
    if not initialized:
        with app.app_context():
            # 创建数据库表
            db.create_all()
            # 检查过期食材
            check_expired_ingredients()

def reset_views():
    """重置浏览量"""
    try:
        from check.views_reset import check_and_reset_views
        check_and_reset_views()
    except Exception as e:
        print(f"浏览量重置错误: {e}")

# 应用启动时执行初始化
initialize_app()
# 重置浏览量
reset_views()

# 注册一个before_request处理函数，在第一次请求时初始化推荐器
recommender_initialized = False

def init_recommender_on_first_request():
    global recommender_initialized
    if not recommender_initialized:
        try:
            from app.recommendation.hybrid_recommender import init_recommender
            with app.app_context():
                init_recommender()
            recommender_initialized = True
            print("推荐器初始化完成！")
        except Exception as e:
            print(f"推荐器初始化失败: {e}")
            import traceback
            traceback.print_exc()

# 添加before_request处理函数
app.before_request(init_recommender_on_first_request)

if __name__ == '__main__':
    # 运行应用
    app.run(debug=True)
