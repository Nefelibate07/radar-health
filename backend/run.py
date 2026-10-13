"""入口:python run.py

用 socketio.run() 而不是 app.run(),这样 threading async_mode 下的 WebSocket 才能正常握手。
"""
from app.config import DEBUG, HOST, PORT
from app.factory import create_app
from app.sockets import socketio

app = create_app()

if __name__ == "__main__":
    # allow_unsafe_werkzeug: 开发阶段用 Flask 自带 server 即可,不引入额外的生产级 WSGI 服务器依赖。
    # 部署上线前应换成 gunicorn/waitress 等,而不是继续用这个开发服务器。
    socketio.run(app, host=HOST, port=PORT, debug=DEBUG, use_reloader=False, allow_unsafe_werkzeug=True)
