"""
ClaudeBot 工具定义

定义 ClaudeBot 可以使用的工具
"""

from typing import Dict, Any, List

# ClaudeBot 工具定义
CLAUDEBOT_TOOLS = [
    {
        "name": "read_email",
        "description": "读取用户的邮件",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "邮件ID"
                },
                "folder": {
                    "type": "string",
                    "description": "邮件文件夹",
                    "default": "inbox"
                }
            },
            "required": ["email_id"]
        }
    },
    {
        "name": "send_email",
        "description": "发送邮件",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "收件人邮箱"
                },
                "subject": {
                    "type": "string",
                    "description": "邮件主题"
                },
                "body": {
                    "type": "string",
                    "description": "邮件正文"
                }
            },
            "required": ["recipient", "subject", "body"]
        }
    },
    {
        "name": "delete_email",
        "description": "删除邮件（危险操作，需要确认）",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "要删除的邮件ID"
                }
            },
            "required": ["email_id"]
        }
    },
    {
        "name": "search_calendar",
        "description": "搜索日历事件",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期 (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期 (YYYY-MM-DD)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "create_event",
        "description": "创建日历事件",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "事件标题"
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间 (ISO格式)"
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间 (ISO格式)"
                },
                "description": {
                    "type": "string",
                    "description": "事件描述"
                }
            },
            "required": ["title", "start_time", "end_time"]
        }
    }
]


# 模拟工具执行
class ToolExecutor:
    """工具执行器（模拟）"""

    def __init__(self):
        # 模拟邮件数据
        self._emails = {
            "email_001": {
                "from": "alice@example.com",
                "subject": "会议通知",
                "body": "明天下午3点开会，地点：会议室A",
                "date": "2024-01-15"
            },
            "email_002": {
                "from": "bob@company.com",
                "subject": "项目进度",
                "body": "项目已完成80%，预计下周交付",
                "date": "2024-01-14"
            }
        }

        # 模拟日历数据
        self._events = [
            {
                "id": "event_001",
                "title": "周会",
                "start": "2024-01-16T10:00:00",
                "end": "2024-01-16T11:00:00"
            }
        ]

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """执行工具"""
        if tool_name == "read_email":
            return self._read_email(args)
        elif tool_name == "send_email":
            return self._send_email(args)
        elif tool_name == "delete_email":
            return self._delete_email(args)
        elif tool_name == "search_calendar":
            return self._search_calendar(args)
        elif tool_name == "create_event":
            return self._create_event(args)
        else:
            return f"未知工具: {tool_name}"

    def _read_email(self, args: Dict) -> str:
        email_id = args.get("email_id")
        email = self._emails.get(email_id)
        if email:
            return f"邮件内容:\n发件人: {email['from']}\n主题: {email['subject']}\n正文: {email['body']}"
        return f"未找到邮件: {email_id}"

    def _send_email(self, args: Dict) -> str:
        recipient = args.get("recipient")
        subject = args.get("subject")
        return f"邮件已发送给 {recipient}，主题: {subject}"

    def _delete_email(self, args: Dict) -> str:
        email_id = args.get("email_id")
        if email_id in self._emails:
            del self._emails[email_id]
            return f"已删除邮件: {email_id}"
        return f"未找到邮件: {email_id}"

    def _search_calendar(self, args: Dict) -> str:
        query = args.get("query", "").lower()
        results = [e for e in self._events if query in e["title"].lower()]
        if results:
            return f"找到 {len(results)} 个事件: {results}"
        return "未找到匹配的事件"

    def _create_event(self, args: Dict) -> str:
        event = {
            "id": f"event_{len(self._events) + 1:03d}",
            "title": args.get("title"),
            "start": args.get("start_time"),
            "end": args.get("end_time")
        }
        self._events.append(event)
        return f"已创建事件: {event['title']}"
