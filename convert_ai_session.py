#!/usr/bin/env python3
"""
AI Session 统一转换工具

支持自动识别并转换以下格式的 AI 对话历史为 OpenAI 标准格式:
- Claude JSONL (Claude Desktop/API session)
- Codex JSONL (Codex CLI session)
- Gemini JSON (Gemini CLI session)
- Kilocode JSON (Kilocode API conversation history)
- OpenCode JSON (OpenCode session)

输出格式:
- 符合 OPENAI_FORMAT_SPEC.md 规范
- 包含 messages 数组和 meta 元数据
- 支持 reasoning (推理内容)、tool_call (工具调用)、tool_output (工具结果) 等内容类型
- Token 统计信息统一存储在 meta.token_counts 数组中

特性:
- 自动检测输入文件格式
- 支持多种编码格式 (UTF-8, UTF-16, GBK 等)
- 保留完整的元数据和时间戳信息
- 完全独立运行，不依赖任何项目内其他脚本
- 支持批量转换指定目录下的所有会话文件

使用示例:
    # 单文件转换 - 自动检测格式
    python convert_ai_session.py -i session.json

    # 单文件转换 - 指定输出文件
    python convert_ai_session.py -i session.jsonl -o output.json

    # 单文件转换 - 强制指定格式
    python convert_ai_session.py -i session.jsonl --format claude

    # 批量转换 - 转换指定目录下所有会话文件(仅处理一层目录) 固定输出到convert目录下
    python convert_ai_session.py -d script/session/test
    # 批量转换 - 转换当前目录下所有会话文件(仅处理一层目录) 固定输出到convert目录下
    python convert_ai_session.py -d .

    # 批量转换 - 指定文件匹配模式
    python convert_ai_session.py -d script/session/test --pattern "*.json" --exclude "*_converted.json"
批量转换说明:
    - 仅扫描指定目录下的所有 .json 和 .jsonl 文件(不递归子目录)
    - 默认跳过已转换的文件 (*_converted.json)
    - 转换后的文件命名为: 原文件名_converted.json
    - 可通过 --pattern 和 --exclude 参数自定义文件过滤规则
    - 转换失败的文件会记录错误信息并继续处理其他文件
    - 转换完成后输出统计信息: 成功数/失败数/跳过数
作者: liufei
版本: 1.3.0
更新日期: 2026-03-18
"""
from __future__ import annotations

import json
import sys
import argparse
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, TextIO
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ============================================================================
# 格式检测
# ============================================================================

def detect_format(file_path: Path) -> str:
    """
    自动检测文件格式

    返回: 'claude_jsonl' | 'codex_jsonl' | 'kilocode' | 'opencode' | 'gemini' | 'unknown'
    """
    # JSONL 格式检测
    if file_path.suffix == '.jsonl':
        return detect_jsonl_format(file_path)

    # JSON 格式检测
    data = None
    for encoding in ['utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'gbk', 'gb2312']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                data = json.load(f)
            break
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

    if data is None:
        return 'unknown'

    # Gemini 格式: {"sessionId": "...", "messages": [...], "startTime": "..."}
    if isinstance(data, dict) and 'sessionId' in data and 'messages' in data:
        messages = data.get('messages', [])
        if isinstance(messages, list) and len(messages) > 0:
            first_msg = messages[0]
            if isinstance(first_msg, dict) and 'type' in first_msg and first_msg.get('type') in ('user', 'gemini'):
                return 'gemini'

    # OpenCode 格式: {"info": {...}, "messages": [...]}
    if isinstance(data, dict) and 'info' in data and 'messages' in data:
        info = data.get('info', {})
        if isinstance(info, dict) and 'id' in info:
            return 'opencode'

    # Kilocode 格式: [{"role": "user", "content": [...], "ts": 123}]
    if isinstance(data, list) and len(data) > 0:
        first_item = data[0]
        if isinstance(first_item, dict) and 'role' in first_item and 'content' in first_item and 'ts' in first_item:
            content = first_item.get('content', [])
            if isinstance(content, list) and len(content) > 0:
                if isinstance(content[0], dict) and 'type' in content[0]:
                    return 'kilocode'

    return 'unknown'


def detect_jsonl_format(file_path: Path) -> str:
    """
    检测 JSONL 文件的具体格式

    返回: 'codex_jsonl' | 'claude_jsonl' | 'unknown'
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 10:
                    break
                line = line.strip()
                if line:
                    lines.append(line)

            if not lines:
                return 'unknown'

            first_obj = json.loads(lines[0])

            # Claude 格式特征
            if 'sessionId' in first_obj:
                return 'claude_jsonl'

            event_type = first_obj.get('type')
            if event_type in ('user', 'assistant', 'progress', 'file-history-snapshot', 'system'):
                if 'message' in first_obj or 'parentUuid' in first_obj or 'isSidechain' in first_obj:
                    return 'claude_jsonl'

            # Codex 格式特征
            if 'payload' in first_obj:
                return 'codex_jsonl'

            if event_type in ('session_meta', 'turn_context', 'event_msg', 'response_item'):
                return 'codex_jsonl'

            # 检查更多行
            claude_indicators = 0
            codex_indicators = 0

            for line in lines[1:]:
                try:
                    obj = json.loads(line)
                    if any(k in obj for k in ('sessionId', 'parentUuid', 'isSidechain', 'userType')):
                        claude_indicators += 1
                    if 'payload' in obj or obj.get('type') in ('session_meta', 'turn_context'):
                        codex_indicators += 1
                except json.JSONDecodeError:
                    continue

            if claude_indicators > codex_indicators:
                return 'claude_jsonl'
            elif codex_indicators > claude_indicators:
                return 'codex_jsonl'

            return 'codex_jsonl'

    except Exception as e:
        print(f"警告: 检测 JSONL 格式时出错: {str(e)}")
        return 'unknown'


# ============================================================================
# Claude JSONL 转换器 (原 claude_jsonl_to_openai_messages.py)
# ============================================================================

def _claude_read_jsonl(stream: TextIO) -> Iterable[dict]:
    """读取 JSONL 文件，每行一个 JSON 对象"""
    for line_no, line in enumerate(stream, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {line_no}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"Expected object at line {line_no}, got {type(obj).__name__}")
        yield obj


@dataclass
class ClaudeConverterOptions:
    """Claude 转换器选项配置"""
    include_thinking: bool = True
    include_toolcall_content: bool = True
    include_token_count: bool = True
    messages_only: bool = False


@dataclass
class ClaudeConverterState:
    """Claude 转换器状态"""
    session_id: str | None = None
    token_counts: list = field(default_factory=list)
    session_meta: dict = field(default_factory=dict)
    skipped_events: list = field(default_factory=list)


def convert_claude_jsonl_to_messages(
    events: Iterable[dict],
    *,
    options: ClaudeConverterOptions,
) -> dict:
    """
    将 Claude session JSONL 转换为 OpenAI 消息格式
    Args:
        events: JSONL 事件迭代器
        options: 转换选项
    Returns:
        包含 messages 和 meta 的字典
    """
    state = ClaudeConverterState()
    messages: list = []

    for obj in events:
        event_type = obj.get("type")
        timestamp = obj.get("timestamp")

        # 提取 session 元数据
        if event_type == "user" and state.session_id is None:
            state.session_id = obj.get("sessionId")
            state.session_meta = {
                "session_id": obj.get("sessionId"),
                "version": obj.get("version"),
                "git_branch": obj.get("gitBranch"),
                "cwd": obj.get("cwd"),
            }

        # 处理用户消息
        if event_type == "user":
            message = obj.get("message", {})
            role = message.get("role")
            content = message.get("content")

            if role == "user" and isinstance(content, str):
                user_msg = {
                    "role": "user",
                    "content": [{"type": "text", "text": content}],
                }
                if timestamp:
                    user_msg["_metadata"] = {"timestamp": timestamp}
                messages.append(user_msg)
            elif role == "user" and isinstance(content, list):
                # 处理工具结果
                user_msg = {
                    "role": "user",
                    "content": []
                }
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_result":
                            tool_msg = {
                                "role": "tool",
                                "tool_call_id": item.get("tool_use_id", ""),
                                "content": [{"type": "tool_output", "text": item.get("content", "")}]
                            }
                            if timestamp:
                                tool_msg["_metadata"] = {"timestamp": timestamp}
                            messages.append(tool_msg)
                        else:
                            user_msg["content"].append(item)

                # 如果有非工具结果的内容，添加用户消息
                if user_msg["content"]:
                    if timestamp:
                        user_msg["_metadata"] = {"timestamp": timestamp}
                    messages.append(user_msg)

        # 处理助手消息
        elif event_type == "assistant":
            message = obj.get("message", {})
            role = message.get("role")
            content = message.get("content")
            usage = message.get("usage")

            if role == "assistant" and isinstance(content, list):
                assistant_msg = {
                    "role": "assistant",
                    "content": [],
                }

                tool_calls = []

                for item in content:
                    if not isinstance(item, dict):
                        continue

                    item_type = item.get("type")

                    # 处理思考过程
                    if item_type == "thinking" and options.include_thinking:
                        thinking_text = item.get("thinking", "")
                        if thinking_text:
                            assistant_msg["content"].append({
                                "type": "reasoning",
                                "text": thinking_text
                            })

                    # 处理文本内容
                    elif item_type == "text":
                        text = item.get("text", "")
                        if text:
                            assistant_msg["content"].append({
                                "type": "text",
                                "text": text
                            })

                    # 处理工具调用
                    elif item_type == "tool_use":
                        tool_id = item.get("id", "")
                        tool_name = item.get("name", "")
                        tool_input = item.get("input", {})

                        tool_call = {
                            "id": tool_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_input, ensure_ascii=False)
                            }
                        }
                        tool_calls.append(tool_call)

                        # 可选：在 content 中也包含工具调用信息
                        if options.include_toolcall_content:
                            assistant_msg["content"].append({
                                "type": "tool_call",
                                "tool_call_id": tool_id,
                                "name": tool_name,
                                "arguments": json.dumps(tool_input, ensure_ascii=False)
                            })

                # 添加工具调用字段
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls

                # 添加时间戳和元数据
                if timestamp:
                    assistant_msg["_metadata"] = {"timestamp": timestamp}

                # 只有当消息有内容或工具调用时才添加
                if assistant_msg["content"] or tool_calls:
                    messages.append(assistant_msg)

                # 收集 token 统计信息
                if usage and options.include_token_count:
                    token_entry = {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": usage.get("input_tokens", 0),
                                "cached_input_tokens": usage.get("cache_read_input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                            },
                            "last_token_usage": {
                                "input_tokens": usage.get("input_tokens", 0),
                                "cached_input_tokens": usage.get("cache_read_input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                            }
                        },
                        "rate_limits": {
                            "primary": None,
                            "secondary": None,
                            "credits": None,
                            "plan_type": None
                        }
                    }
                    if timestamp:
                        token_entry["_timestamp"] = timestamp
                    state.token_counts.append(token_entry)

        # 记录其他类型的事件
        elif event_type in ("progress", "system", "file-history-snapshot"):
            if options.include_token_count:
                state.skipped_events.append({
                    "type": event_type,
                    "timestamp": timestamp,
                    "data": obj.get("data") or obj.get("subtype")
                })

    # 构建结果
    result: dict = {"messages": messages}
    if not options.messages_only:
        result["meta"] = {
            "session_meta": state.session_meta,
            "token_counts": state.token_counts if options.include_token_count else None,
            "skipped_events_count": len(state.skipped_events),
            "skipped_events": state.skipped_events[:10] if state.skipped_events else []
        }

    return result
