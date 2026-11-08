import argparse

from . import __version__
from . import agent
from . import ai
from . import commands
from .tools import GAMES_DIR
from .tui import BOLD, CYAN, DIM, RESET, YELLOW, Ui, enable_ansi

BANNER = """\
==================================================
  VibeCoding Agent · 小游戏制造机
  描述你的想法，我来把它做成可以玩的小游戏
=================================================="""

PROMPT = CYAN + "❯ " + RESET


def main():
    enable_ansi()
    args = _parse_args()

    if args.version:
        print("vibecoding-agent %s" % __version__)
        return

    config = ai.load_config()
    print(CYAN + BOLD + BANNER + RESET)
    print("  模型：%s%s" % (config["model"], DIM + "（环境变量 VIBE_MODEL 可切换）" + RESET))
    print("  游戏目录：%s" % GAMES_DIR)

    if not ai.config_is_ready(config):
        print()
        print(YELLOW + "  尚未配置模型服务。请先设置环境变量：" + RESET)
        print("    VIBE_API_KEY   你的 API Key（必填）")
        print("    VIBE_BASE_URL  接口地址，默认 https://api.openai.com/v1")
        print("    VIBE_MODEL     模型名，默认 %s" % ai.DEFAULT_MODEL)
        print("  例如（DeepSeek）：set VIBE_API_KEY=sk-xxx & set VIBE_BASE_URL=https://api.deepseek.com/v1 & set VIBE_MODEL=deepseek-chat")

    if args.continue_:
        session = agent.load_latest_session()
        if session is None:
            print(YELLOW + "  没有可续接的历史会话，已创建新会话。" + RESET)
            session = agent.Session(config["model"])
        else:
            print(DIM + "  已续接会话 %s" % session.id + RESET)
    else:
        session = agent.Session(config["model"])

    ui = Ui()

    task_text = " ".join(args.task).strip()
    if task_text:
        print()
        _run_turn_safely(session, config, task_text, ui)
        return

    print(DIM + "  输入 /help 查看命令，Ctrl+C 或 /quit 退出" + RESET)
    while True:
        print()
        try:
            text = input(PROMPT).strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break

        if not text:
            continue
        if text.startswith("/"):
            commands.run_command(session, config, text)
            continue
        _run_turn_safely(session, config, text, ui)


def _run_turn_safely(session, config, text, ui):
    """执行一轮对话，把网络错误和用户中断都转成友好提示，不让程序崩溃。"""
    try:
        agent.run_turn(session, config, text, ui)
    except KeyboardInterrupt:
        ui.on_interrupted()
    except RuntimeError as error:
        ui.on_error(str(error))


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="vibe", description="终端里的小游戏生成 Agent"
    )
    parser.add_argument(
        "task", nargs="*", help="一次性任务描述，例如：vibe 做一个贪吃蛇游戏"
    )
    parser.add_argument(
        "-c", "--continue", dest="continue_", action="store_true",
        help="继续上一次会话",
    )
    parser.add_argument("--version", action="store_true", help="显示版本号")
    return parser.parse_args()
