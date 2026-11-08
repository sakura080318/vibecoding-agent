import json
import time
from pathlib import Path

from . import ai
from . import tools as game_tools
from .prompt import SYSTEM_PROMPT


SESSIONS_DIR = Path(__file__).resolve().parent.parent / ".vibe" / "sessions"


class Session:
    """一次对话的全部状态。刻意保持为普通类，不做继承和装饰。"""

    def __init__(self, model):
        self.id = time.strftime("%Y%m%d-%H%M%S")
        self.model = model
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.tool_schemas = game_tools.TOOL_SCHEMAS


def run_turn(session, config, user_input, ui):
    """执行一轮完整对话：用户输入 -> （模型 -> 工具)* -> 最终回答。

    ui 是终端界面的回调对象，负责所有显示；本函数只管流程推进。
    """
    session.messages.append({"role": "user", "content": user_input})

    while True:
        ui.on_model_start(session.model)
        assistant_text = ""
        pending_calls = []
        try:
            for event in ai.chat_stream(config, session.messages, session.tool_schemas):
                if event["type"] == "text_delta":
                    assistant_text += event["text"]
                    ui.on_text_delta(event["text"])
                elif event["type"] == "tool_calls":
                    pending_calls = event["calls"]
                elif event["type"] == "done":
                    break
        except KeyboardInterrupt:
            ui.on_text_end()
            raise
        ui.on_text_end()

        if not pending_calls:
            if assistant_text:
                session.messages.append({"role": "assistant", "content": assistant_text})
            break

        openai_tool_calls = []
        for index, call in enumerate(pending_calls):
            call_id = call["id"] or "call_%d" % index
            openai_tool_calls.append({
                "id": call_id,
                "type": "function",
                "function": {"name": call["name"], "arguments": call["arguments"]},
            })
        session.messages.append({
            "role": "assistant",
            "content": assistant_text or None,
            "tool_calls": openai_tool_calls,
        })

        for index, call in enumerate(pending_calls):
            call_id = call["id"] or "call_%d" % index
            ui.on_tool_start(call["name"], call["arguments"])
            result = game_tools.execute_tool(call["name"], call["arguments"])
            ui.on_tool_result(result)
            session.messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result,
            })

    save_session(session)


def save_session(session):
    """把会话保存成 JSON 文件，文件名就是会话 id。"""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"id": session.id, "model": session.model, "messages": session.messages}
    path = SESSIONS_DIR / (session.id + ".json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_latest_session():
    """加载最近一次的会话，用于 --continue 参数。没有历史时返回 None。"""
    if not SESSIONS_DIR.exists():
        return None
    files = sorted(SESSIONS_DIR.glob("*.json"))
    if not files:
        return None
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    session = Session(data["model"])
    session.id = data["id"]
    session.messages = data["messages"]
    return session
