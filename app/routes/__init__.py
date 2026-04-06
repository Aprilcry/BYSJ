# 路由模块初始化文件
from app.routes import auth, user, recipe, ingredient, plaza, recommendation, ai, dashboard

def register_routes(app):
    app.register_blueprint(auth.auth)
    app.register_blueprint(user.user)
    app.register_blueprint(recipe.recipe)
    app.register_blueprint(ingredient.ingredient)
    app.register_blueprint(plaza.plaza)
    app.register_blueprint(recommendation.recommendation)
    app.register_blueprint(ai.ai)
    app.register_blueprint(dashboard.dashboard)
