---
name: wechat-agent
description: Analyze local WeChat messages with AI. Read your WeChat database, get group chat digests, analyze personal conversations, extract TODOs, search keywords, find shared files, and monitor real-time messages. All local, read-only, never sends messages.
metadata:
  version: "1.2.0"
  author: yuge88-hub
  repository: https://github.com/yuge88-hub/wechat-group-ai
  platforms: [windows]
  python: ">=3.10"
  wechat: "4.x desktop"
  license: MIT
---

# WeChat AI Agent Skill

Analyze WeChat messages locally using AI. Read, filter, classify, summarize — never send messages or auto-reply.

## Quick Start

```bash
# Clone the project
git clone https://github.com/yuge88-hub/wechat-group-ai.git
cd wechat-group-ai

# Install dependencies
pip install -r requirements.txt
```

Then set your API key and start the chat interface:
```powershell
$env:DEEPSEEK_API_KEY = "sk-your-key"
python -m agent.main --chat
```

Open http://127.0.0.1:5080 in browser.

## What You Can Ask

### Analyze a person's chat
```
分析玲妈妈
总结我和张三的聊天要点
李四的情绪和态度
我和王五聊了什么时间地点
整理赵六的聊天内容
刘七有什么待办和承诺
```

### Analyze group chats
```
最近有什么重要消息
谁@我了
AI大健康群总结
技术讨论群通知和任务
项目群谁最活跃
只看老板在项目群里发了什么
```

### Search & tools
```
搜索合同
帮我找Word文档
帮我找Excel表格
提取待办事项
我的好友统计
```

### CLI mode (no browser)
```powershell
# One-time scan
python -m agent.main --once --lookback 6

# Target specific person or group
python -m agent.main --once --group "Contact Name" --lookback 720

# Real-time file monitoring
python -m agent.main --watch
```

## Prerequisites

1. **Windows 10/11** with WeChat Desktop 4.x logged in
2. **Python 3.10+**
3. **One-time setup** (run as Administrator):
   ```powershell
   cd weixin-decrypte-script
   python scan_keys.py
   python decrypt_db.py --auto "C:\Users\<user>\Documents\xwechat_files\<wxid>\db_storage" found_keys.txt
   ```
4. **DeepSeek API key** (or any OpenAI-compatible endpoint)

## How It Works

```
WeChat local encrypted DB → Memory key extraction → SQLCipher decrypt → AI (DeepSeek) analysis → Structured report
```

All processing is local. No data leaves your machine.

## Available Models

Any OpenAI-compatible API works. Edit `agent/config.yaml`:
```yaml
llm:
  provider: "openai"
  api_key: "${DEEPSEEK_API_KEY}"
  base_url: "https://api.deepseek.com/v1"  # Change for other providers
```
