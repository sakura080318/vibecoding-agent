import json
import os
import sys
import threading

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


def enable_ansi():
    """在 Windows 控制台开启 ANSI 转义支持；其他平台这条空命令没有副作用。"""
    os.system("")


class Spinner:
    """等待模型响应时显示的加载动画，用独立线程驱动。"""

    FRAMES = "|/-\\"

    def __init__(self, hint):
        self.hint = hint
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        index = 0
        while not self._stop_event.wait(0.12):
            frame = self.FRAMES[index % len(self.FRAMES)]
            sys.stdout.write("\r  %s%s %s…%s " % (DIM, frame, self.hint, RESET))
            sys.stdout.flush()
            index += 1

    def start(self):
        self._thread.start()

    def stop(self):
        """停止动画并清掉当前行。重复调用是安全的。"""
        if not self._thread.is_alive():
            return
        self._stop_event.set()
        self._thread.join()
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()


class Ui:
    """Agent 流程层使用的显示回调集合。"""

    def __init__(self):
        self._spinner = None
        self._printed_text = False

    def on_model_start(self, model):
        """模型开始响应：先收尾上一段输出，再显示加载动画。"""
        self.on_text_end()
        self._spinner = Spinner("思考中")
        self._spinner.start()

    def on_text_delta(self, text):
        """收到一段增量文本：第一次收到时先停掉动画，然后原样流出。"""
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None
        sys.stdout.write(text)
        sys.stdout.flush()
        self._printed_text = True

    def on_text_end(self):
        """一轮流式输出结束：停动画，如果打过文本就补一个换行。"""
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None
        if self._printed_text:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._printed_text = False

    def on_tool_start(self, name, arguments):
        """模型发起工具调用：显示工具名和精简后的参数。"""
        self.on_text_end()
        print("  %s● %s %s%s" % (BOLD + CYAN, name, DIM + _short_arguments(arguments), RESET))

    def on_tool_result(self, result):
        """工具执行完毕：显示结果的第一行。"""
        first_line = result.splitlines()[0] if result else ""
        color = GREEN if result.startswith("已写入") else DIM
        print("    %s└ %s%s" % (color, first_line, RESET))

    def on_error(self, message):
        """发生错误：红色提示，保持会话可以继续。"""
        self.on_text_end()
        print("  %s✗ 错误：%s%s" % (RED, message, RESET))

    def on_interrupted(self):
        """用户中断了本轮回答。"""
        self.on_text_end()
        print("  %s（已中断本轮回答）%s" % (YELLOW, RESET))


def _short_arguments(arguments):
    """把工具参数压成一行短文本用于展示，避免把整个 HTML 打到屏幕上。"""
    try:
        data = json.loads(arguments or "{}")
    except ValueError:
        return (arguments or "")[:60]
    pieces = []
    for key, value in data.items():
        text = str(value).replace("\n", " ")
        if len(text) > 40:
            text = text[:40] + "…"
        pieces.append("%s=%s" % (key, text))
    return " ".join(pieces)
