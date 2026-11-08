import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

from . import GAMES_DIR

PREVIEW_PORT = 8612

_server_lock = threading.Lock()
_server = None 


class QuietHandler(SimpleHTTPRequestHandler):
    """静态文件请求处理器：把根目录固定到 games，并关闭访问日志。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(GAMES_DIR), **kwargs)

    def log_message(self, format, *args):
        pass  


def start_server():
    """在后台线程里启动预览服务器。

    返回 True 表示这次调用新建了服务器；False 表示本来就在运行
    （包括端口被上次会话占用的情况，直接复用即可）。
    """
    global _server
    with _server_lock:
        if _server is not None:
            return False
        GAMES_DIR.mkdir(exist_ok=True)
        try:
            _server = HTTPServer(("127.0.0.1", PREVIEW_PORT), QuietHandler)
        except OSError:
            return False
        thread = threading.Thread(target=_server.serve_forever, daemon=True)
        thread.start()
        return True


def base_url():
    """预览服务器的根地址。"""
    return "http://127.0.0.1:%d" % PREVIEW_PORT


def game_url(filename):
    """某个游戏页面的完整 URL，中文文件名需要做 URL 编码。"""
    return base_url() + "/" + urllib.parse.quote(filename)
