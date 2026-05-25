# 微信群 AI 助手 · WeChat Group AI Agent

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
## English

**AI-powered analysis of your WeChat messages — local, private, read-only.**

Reads your local WeChat database, uses AI (DeepSeek or any OpenAI-compatible API) to filter noise, classify importance, extract action items, and generate structured summaries. Never sends messages, never auto-replies — analysis only.

### Features

**Personal Chat Analysis**
- **Analyze a contact** — Relationship, communication style, topics, timeline, intimacy score
- **Summarize chat with X** — Extract key conclusions, agreements, action items
- **Emotion & intent detection** — Is the other person asking for help? Angry? Urgent?
- **Extract key data** — Dates, locations, amounts, phone numbers, files
- **TODO extraction** — Find all promises, commitments, and pending tasks from recent chats

**Group Chat Analysis**
- **Smart digest** — One-click summary of what happened in your groups today
- **@me messages** — See only messages that mention you, ranked by priority
- **Meeting & task extraction** — Extract announcements, tasks, meetings with deadlines
- **Person-specific tracking** — See what a specific person said in a group
- **Activity statistics** — Who's most active? What topics dominate?

**Search & Tools**
- **Full-text search** — Find any keyword across all messages
- **File search** — Locate Word, Excel, PDF, PPT files shared in chats
- **Friend statistics** — Contact list overview

### How It Works

```
WeChat local encrypted DB → Memory key extraction → SQLCipher decrypt → AI analysis → Report
```

1. **Extract keys**: Scan WeChat process memory for SQLCipher encryption keys (admin required, one-time)
2. **Decrypt databases**: Decrypt all local WeChat databases
3. **AI analysis**: DeepSeek or any OpenAI-compatible API classifies and summarizes

All data stays on your machine. Nothing is uploaded.

### Quick Start

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Extract encryption keys (run as Administrator, WeChat must be running)
cd weixin-decrypte-script
python scan_keys.py

# 3. Decrypt databases
python decrypt_db.py --auto "C:\Users\<user>\Documents\xwechat_files\<wxid>\db_storage" found_keys.txt

# 4. Set API key
$env:DEEPSEEK_API_KEY = "sk-your-key"

# 5. Start chat interface
cd ..
python -m agent.main --chat
```

Then open http://127.0.0.1:5080 in your browser.

### CLI Usage

```powershell
# One-time scan (last N hours)
python -m agent.main --once --lookback 6

# Analyze a specific person/group
python -m agent.main --once --group "Contact Name" --lookback 720

# Real-time monitoring (file change detection)
python -m agent.main --watch

# Start chat web UI
python -m agent.main --chat
```

### Requirements

- Windows 10/11
- Python 3.10+
- WeChat Desktop 4.x (logged in)
- Administrator rights (key extraction only, one-time)
- DeepSeek API key (or any OpenAI-compatible endpoint)

### Configuration

Edit `agent/config.yaml`:

```yaml
llm:
  provider: "openai"
  api_key: "${DEEPSEEK_API_KEY}"
  base_url: "https://api.deepseek.com/v1"
  model_filter: "deepseek-chat"
  model_digest: "deepseek-chat"

groups:
  mode: "auto"
  max_groups: 50
  min_members: 5
```

### Disclaimer

This project is for personal data organization and research purposes only. Please comply with local laws and respect others' privacy. Do not use for automated replies, spam, or any activity that violates WeChat's terms of service.

### License

MIT

---

<a name="chinese"></a>
## 中文

**用 AI 整理你的微信消息 — 本地运行、保护隐私、只读不写。**

读取微信本地数据库，用 AI（DeepSeek 或任何 OpenAI 兼容接口）自动过滤噪音、判断重要性、提取待办事项、生成结构化摘要。不发送消息、不自动回复、纯分析。

### 功能

**个人聊天分析**

| 输入 | 能力 |
|------|------|
| 分析玲妈妈 | 关系判断、沟通风格、话题分布、时间线、亲密度评分 |
| 总结我和XX的聊天要点 | 提炼核心结论、共识、分歧 |
| XX的情绪和态度 | 判断语气（正常/着急/生气/客气）、真实意图 |
| 我和XX聊了什么时间地点 | 提取所有时间、地点、金额、手机号、文件 |
| 整理XX的聊天 | 按主题归类，输出结构化表格和清单 |
| XX有什么待办和承诺 | 提取双方答应的事，标注完成状态 |

**微信群分析**

| 输入 | 能力 |
|------|------|
| 最近有什么重要消息 | 智能摘要，按话题分组 |
| 谁@我了 | 只看@你的消息，标注优先级 |
| XX群总结 | 今日话题、重要通知、待跟进事项 |
| XX群通知和任务 | 提取公告、任务清单、会议安排 |
| XX群谁最活跃 | 发言排行榜 + 话题分析 |
| 只看XX在群里发过什么 | 过滤特定人发言并总结 |
| XX群发了什么文件 | 整理群文件和链接 |

**搜索与工具**

| 输入 | 能力 |
|------|------|
| 搜索合同 | 全文关键词精准搜索 |
| 帮我找Word文档 | 扫描所有文件（Word/Excel/PDF/PPT） |
| 提取待办事项 | 从最近两周聊天挖出所有待办 |
| 我的好友统计 | 通讯录人数一览 |

### 原理

```
微信本地加密数据库 → 内存提取密钥 → SQLCipher 解密 → AI 分析 → Markdown 报告
```

1. **提取密钥**：扫描微信进程内存获取 SQLCipher 加密密钥（需管理员权限，仅首次）
2. **解密数据库**：批量解密所有本地数据库
3. **AI 分析**：DeepSeek 或兼容 API 做消息分类和摘要生成

所有数据只在你的电脑上处理，不上传、不泄露。

### 快速开始

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 提取密钥（以管理员身份运行，微信必须已登录）
cd weixin-decrypte-script
python scan_keys.py

# 3. 解密数据库
python decrypt_db.py --auto "C:\Users\<用户名>\Documents\xwechat_files\<wxid>\db_storage" found_keys.txt

# 4. 设置 API Key
$env:DEEPSEEK_API_KEY = "sk-你的密钥"

# 5. 启动聊天界面
cd ..
python -m agent.main --chat
```

浏览器打开 http://127.0.0.1:5080 即可使用。

### 命令行用法

```powershell
# 单次扫描（回溯 N 小时）
python -m agent.main --once --lookback 6

# 分析指定联系人或群
python -m agent.main --once --group "联系人名称" --lookback 720

# 实时监听（文件变化检测，秒级响应）
python -m agent.main --watch

# 启动聊天 Web 界面
python -m agent.main --chat
```

### 打包为 EXE

```powershell
pip install pyinstaller
pyinstaller wx-agent.spec
# 输出在 dist/wx-agent/
```

### 环境要求

- Windows 10/11
- Python 3.10+
- 微信桌面版 4.x（已登录）
- 管理员权限（仅首次提取密钥时需要）
- DeepSeek API Key（或任何 OpenAI 兼容接口）

### 项目结构

```
wx-chat/
  agent/                          # AI Agent 核心
    chat_server.py                # 聊天服务器（全能力）
    chat.html                     # 聊天 Web 界面
    main.py                       # CLI 入口
    agent_core.py                 # 总调度器
    message_filter.py             # 消息过滤管道
    llm_client.py                 # LLM 客户端
    prompt_builder.py             # Prompt 模板
    group_manager.py              # 群组选择
    digest_generator.py           # 摘要输出
    state_manager.py              # 状态持久化
    live_watch.py                 # 实时文件监听
    config.py / config.yaml       # 配置
  weixin-decrypte-script/         # 微信数据库解密（ZedeX/weixin-decrypte-script）
  digests/                        # 生成的摘要报告
  state/                          # Agent 运行状态
```

### 支持的大模型

| 提供商 | base_url |
|--------|----------|
| DeepSeek | `https://api.deepseek.com/v1` |
| OpenAI | `https://api.openai.com/v1` |
| 任何 OpenAI 兼容 API | 修改 `base_url` 即可 |

### 免责声明

本项目仅供个人数据整理与学习研究使用。请遵守当地法律法规，尊重他人隐私。不得用于自动回复、骚扰或任何违反微信服务条款的行为。

### License

MIT — 详见 [LICENSE](LICENSE)
