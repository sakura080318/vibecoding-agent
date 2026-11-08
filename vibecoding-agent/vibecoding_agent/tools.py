import json
import re
import webbrowser

from . import GAMES_DIR, preview


def safe_game_path(filename):
    """把模型给的文件名转换成 games 目录下的安全路径。

    只保留字母、数字、下划线、横线、点号和中文，其余字符替换成下划线，
    防止模型写出 ../ 之类的越界路径（路径分隔符一定不会保留）。
    """
    filename = filename.strip()
    if not filename:
        raise ValueError("文件名不能为空")
    filename = re.sub(r"[^0-9A-Za-z_\-.\u4e00-\u9fff]", "_", filename)
    if not filename.endswith(".html"):
        filename += ".html"
    return GAMES_DIR / filename


def write_game(filename, html):
    """把一个完整的单文件 HTML 游戏写入 games 目录。"""
    html = html.strip()
    if not html:
        return "写入失败：html 参数是空的，请提供完整的 HTML 代码。"
    path = safe_game_path(filename)
    GAMES_DIR.mkdir(exist_ok=True)
    path.write_text(html, encoding="utf-8")
    size_kb = path.stat().st_size / 1024
    return "已写入 %s（%.1f KB）。可以调用 open_in_browser 让用户试玩。" % (path.name, size_kb)


def read_game(filename):
    """读取一个已生成游戏的完整源码，供修改时参考。"""
    path = safe_game_path(filename)
    if not path.exists():
        return "文件不存在：%s。可以先调用 list_games 查看现有游戏。" % path.name
    return path.read_text(encoding="utf-8")


def list_games():
    """列出 games 目录里所有的游戏文件。"""
    if not GAMES_DIR.exists():
        return "games 目录还没有任何游戏。"
    files = sorted(GAMES_DIR.glob("*.html"))
    if not files:
        return "games 目录还没有任何游戏。"
    lines = []
    for path in files:
        size_kb = path.stat().st_size / 1024
        lines.append("- %s（%.1f KB）" % (path.name, size_kb))
    return "现有的游戏：\n" + "\n".join(lines)


def open_in_browser(filename):
    """在浏览器里打开某个游戏。第一次调用会顺带启动本地预览服务器。"""
    path = safe_game_path(filename)
    if not path.exists():
        return "文件不存在：%s。可以先调用 list_games 查看现有游戏。" % path.name
    started = preview.start_server()
    url = preview.game_url(path.name)
    webbrowser.open(url)
    if started:
        return "预览服务器已启动（%s），并已在浏览器打开：%s" % (preview.base_url(), url)
    return "已在浏览器打开：%s" % url


# 工具的 OpenAI 格式描述，会随每次请求发给模型
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_game",
            "description": (
                "把一个完整的单文件 HTML5 小游戏写入 games 目录。"
                "html 参数必须是从 <!DOCTYPE html> 开始的完整可运行代码。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "游戏文件名，例如 snake.html 或 flappy_bird.html",
                    },
                    "html": {
                        "type": "string",
                        "description": "完整的 HTML 页面代码，内联全部 CSS 和 JavaScript",
                    },
                },
                "required": ["filename", "html"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_game",
            "description": "读取 games 目录下某个游戏文件的完整源码，修改已有游戏前先调用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "游戏文件名，例如 snake.html"}
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_games",
            "description": "列出 games 目录里已有的全部游戏文件。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_in_browser",
            "description": "在用户的默认浏览器里打开某个游戏供试玩。写完游戏后应立即调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "游戏文件名，例如 snake.html"}
                },
                "required": ["filename"],
            },
        },
    },
]


def execute_tool(name, arguments):
    """统一的工具执行入口，把模型给出的 JSON 参数分发给对应函数。

    工具出错时不抛异常，而是把错误信息作为结果返回给模型，
    让模型有机会自我修正（例如换一个文件名重试）。
    """
    try:
        args = json.loads(arguments or "{}")
    except ValueError:
        return "工具参数不是合法的 JSON：%s" % (arguments or "")[:200]

    if name == "write_game":
        return write_game(args.get("filename", ""), args.get("html", ""))
    if name == "read_game":
        return read_game(args.get("filename", ""))
    if name == "list_games":
        return list_games()
    if name == "open_in_browser":
        return open_in_browser(args.get("filename", ""))
    return "未知工具：%s" % name
