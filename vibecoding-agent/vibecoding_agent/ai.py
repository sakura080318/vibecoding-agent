import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


def load_config():
    """从环境变量读取大模型配置，返回一个普通字典。"""
    return {
        "base_url": os.environ.get("VIBE_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "api_key": os.environ.get("VIBE_API_KEY"),
        "model": os.environ.get("VIBE_MODEL", DEFAULT_MODEL),
    }


def config_is_ready(config):
    """判断配置是否完整。没有 API Key 时无法调用云端模型。"""
    return bool(config["api_key"])


def chat_stream(config, messages, tools):
    """调用大模型并逐段返回结果（流式）。

    本函数是一个生成器，依次产出"事件字典"，把 SSE 细节封装在这一层：
      {"type": "text_delta", "text": "..."}   一段增量文本
      {"type": "tool_calls", "calls": [...]}  流结束后拼装完成的工具调用列表
      {"type": "done"}                        本轮流式输出结束
    上层 agent 只需要按顺序处理事件，不用关心网络协议。
    """
    if not config_is_ready(config):
        raise RuntimeError(
            "尚未配置 API Key。请先设置环境变量 VIBE_API_KEY"
            "（可选：VIBE_BASE_URL 指定接口地址，VIBE_MODEL 指定模型名）。"
        )

    body = {
        "model": config["model"],
        "messages": messages,
        "stream": True,
    }
    if tools:
        body["tools"] = tools

    url = config["base_url"] + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + config["api_key"],
    }
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )

    try:
        response = urllib.request.urlopen(request, timeout=300)
    except urllib.error.HTTPError as error:

        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError("模型接口返回错误（HTTP %d）：%s" % (error.code, detail)) from error
    except urllib.error.URLError as error:
        raise RuntimeError("无法连接模型接口 %s：%s" % (url, error.reason)) from error

    tool_calls = {}
    with response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            chunk = json.loads(payload)
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            text = delta.get("content")
            if text:
                yield {"type": "text_delta", "text": text}

            for piece in delta.get("tool_calls") or []:
                index = piece.get("index", 0)
                if index not in tool_calls:
                    tool_calls[index] = {"id": "", "name": "", "arguments": ""}
                slot = tool_calls[index]
                if piece.get("id"):
                    slot["id"] = piece["id"]
                function_info = piece.get("function") or {}
                if function_info.get("name"):
                    slot["name"] = function_info["name"]
                if function_info.get("arguments"):
                    slot["arguments"] += function_info["arguments"]

    if tool_calls:
        calls = [tool_calls[index] for index in sorted(tool_calls)]
        yield {"type": "tool_calls", "calls": calls}
    yield {"type": "done"}
