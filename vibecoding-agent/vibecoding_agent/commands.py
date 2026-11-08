import time

from . import preview
from . import tools as game_tools
from .prompt import SYSTEM_PROMPT
from .tui import DIM, RESET

HELP_TEXT = """\
可用命令：
  /help            显示本帮助
  /new             开始新会话（清空当前对话历史）
  /games           列出已生成的游戏
  /open <文件名>   在浏览器中打开某个游戏
  /serve           启动本地预览服务器
  /session         查看当前会话信息
  /model           查看当前使用的模型
  /quit            退出"""


def run_command(session, config, text):
    """处理一条以 / 开头的输入。"""
    parts = text.split(maxsplit=1)
    name = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""

    if name in ("/quit", "/exit", "/q"):
        raise SystemExit(0)

    if name == "/help":
        print(HELP_TEXT)

    elif name == "/new":
        session.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        session.id = time.strftime("%Y%m%d-%H%M%S")
        print("%s已开始新会话（%s）%s" % (DIM, session.id, RESET))

    elif name == "/games":
        print(game_tools.list_games())

    elif name == "/open":
        if not argument:
            print("用法：/open <文件名>，例如 /open snake.html")
        else:
            print(game_tools.open_in_browser(argument))

    elif name == "/serve":
        started = preview.start_server()
        if started:
            print("预览服务器已启动：%s" % preview.base_url())
        else:
            print("预览服务器已在运行：%s" % preview.base_url())

    elif name == "/session":
        print("会话 %s · 共 %d 条消息" % (session.id, len(session.messages)))

    elif name == "/model":
        print("当前模型：%s（用环境变量 VIBE_MODEL 可切换）" % session.model)

    else:
        print("未知命令：%s。输入 /help 查看可用命令。" % name)
