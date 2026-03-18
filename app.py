import os

# 设置ultralytics配置目录到当前项目目录
os.environ['ULTRALYTICS_CONFIG_DIR'] = os.path.join(os.getcwd(), 'ultralytics_config')

# 从app包导入应用实例
from app import app, db

if __name__ == '__main__':
    # 创建数据库表
    with app.app_context():
        db.create_all()
    # 运行应用
    app.run(debug=True)
