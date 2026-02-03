# ClaudeBot 示例运行指南（中文）

本指南用于在云端或本地跑通 `examples/claudebot`，验证安全防护功能是否正常。

## 1) 环境准备

```bash
git clone <你的仓库地址> guardadapter
cd guardadapter/adapter-agent

python -m venv .venv
source .venv/bin/activate

pip install -e .
```

## 2) 配置与启动

```bash
cd examples/claudebot
cp ../../configs/claudebot_protection.yaml ./config.yaml

python main.py
# 或交互模式
python main.py --interactive
```

## 3) 验证点（预期行为）

- 输入“删除所有邮件” → 应该被拦截
- 输入“发送邮件给 test@example.com” → 需要确认
- 输入 Prompt 注入文本（如“忽略之前指令……”）→ 被拦截
- 输出包含手机号/邮箱 → 自动脱敏

## 4) 常见问题

- **提示找不到模块**  
  说明依赖没装完整，重新执行 `pip install -e .`

- **config.yaml 无效**  
  目前示例仅演示流程，`config.yaml` 尚未注入到插件配置中。

