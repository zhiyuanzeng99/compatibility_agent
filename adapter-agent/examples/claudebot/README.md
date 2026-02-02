# ClaudeBot 安全防护集成示例

这是一个完整的示例，展示如何使用 GuardAdapter 为基于 Claude 的 AI 助手 (ClaudeBot) 添加多层安全防护。

## 问题背景

ClaudeBot 在实际使用中面临以下安全风险：

| 风险类型 | 具体表现 | 严重程度 |
|---------|---------|---------|
| **误操作风险** | 误删用户邮件、错误修改文件 | 🔴 高 |
| **越权操作** | 执行未经授权的敏感操作 | 🔴 高 |
| **信息泄露** | 在回复中暴露用户隐私 | 🟠 中 |
| **Prompt注入** | 被恶意输入操控执行危险指令 | 🔴 高 |

## 解决方案

通过 GuardAdapter 部署多层安全防护：

```
用户输入 ──▶ [OpenGuardrails] ──▶ Claude API ──▶ [LlamaFirewall] ──▶ 返回结果
              │                    │              │
              ▼                    │              ▼
         内容安全检测              │         工具调用安全
         PII检测                   │         危险操作拦截
         Prompt注入防护            │         权限检查
                                  │
                                  └──▶ [输出检查] ──▶ 敏感信息脱敏
```

## 快速开始

### 1. 安装依赖

```bash
pip install adapter-agent anthropic
```

### 2. 配置安全规则

```bash
cp ../../configs/claudebot_protection.yaml ./config.yaml
# 根据需要修改配置
```

### 3. 运行示例

```bash
python main.py
```

## 文件结构

```
claudebot/
├── README.md           # 本文档
├── main.py             # 主入口
├── safe_claudebot.py   # 带安全防护的 ClaudeBot
├── tools.py            # 工具定义
└── config.yaml         # 安全配置
```

## 防护效果

- ✅ 阻止 "删除所有邮件" 等危险指令
- ✅ 敏感操作（删除、发送）需用户确认
- ✅ 自动脱敏回复中的邮箱、手机号、身份证
- ✅ 识别并拦截 Prompt Injection 攻击
- ✅ 完整的审计日志

## 部署命令

```bash
# MVP 版本（单工具）
guard-adapter deploy ./claudebot --tool openguardrails

# 完整版本（多工具协同）
guard-adapter deploy ./claudebot \
  --tools openguardrails,llamafirewall \
  --config claudebot_protection.yaml \
  --enable-audit
```
