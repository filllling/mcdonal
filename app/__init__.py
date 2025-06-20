from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev-key'

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # 延迟导入，避免循环导入
    from app.routes.auth import auth_bp
    from app.routes.menu import menu_bp
    from app.routes.main import main_bp
    from app.routes.order import order_bp
    from app.routes.analytics import analytics_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(analytics_bp)

    return app