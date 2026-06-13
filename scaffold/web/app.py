"""sre-scaffold Web 应用 —— Flask 工厂。"""

from flask import Flask

from services.session import init_app as init_session


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object("config")

    # 服务端 session（cookie 只存 session_id）
    init_session(app)

    from routes.select import bp as select_bp
    from routes.config import bp as config_bp
    from routes.deploy import bp as deploy_bp

    app.register_blueprint(select_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(deploy_bp)

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
