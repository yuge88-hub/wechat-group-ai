# 微信群 AI 助手 · WeChat Group AI Agent

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
## English

**AI-powered analysis of your WeChat messages — local, private, read-only.**

Reads your local WeChat database, uses AI (DeepSeek or any OpenAI-compatible API) to filter noise, classify importance, extract action items, and generate structured summaries. Never sends messages, never auto-replies — analysis only.

### Features

####  Personal Chat Analysis
Deep-dive into your one-on-one conversations with AI-powered insights:

| You say | It does |
|---------|---------|
| **Analyze [name]** | Full deep analysis: relationship type & intimacy score (1-10), communication patterns (who initiates more? text vs voice?), topic distribution by frequency, key event timeline with dates, outstanding promises from both sides, the other person's current state & needs, risk alerts (deadlines, conflicts) |
| **Summarize chat with [name]** | Extracts core conclusions, agreements reached, unresolved disagreements, and what you need to do next — all in a structured breakdown |
| **[name]'s emotion & attitude** | Analyzes tone (normal/urgent/angry/polite/complaining), detects the real intention behind words, tells you whether you need to reply, and suggests how to respond |
| **Extract key data from [name]** | Pulls out every date, time, address, phone number, amount, price, and file mentioned in the conversation — organized by category |
| **Organize [name]'s chat** | Restructures messy chat into categorized topics, structured tables (time/topic/contact/status), completed vs pending checklists |
| **[name]'s TODOs & promises** | Extracts all commitments with a table: task, who promised, deadline, priority (high/medium/low), status (pending/done/overdue). Separately lists what YOU promised vs what THEY promised |
| **Global TODO extraction** | Scans all recent 1-on-1 chats (last 2 weeks) and extracts every action item into one master checklist |

####  Group Chat Analysis
Never scroll through 99+ messages again:

| You say | It does |
|---------|---------|
| **Recent important messages** | Scans active groups, filters noise (images/voice/stickers/system messages), classifies importance 1-5 via AI, generates a topic-grouped digest with action items, shared links, and statistics. Processing ~500 messages in 6 hours across 50 groups |
| **Who @me** | Scans ALL groups for messages mentioning you. Shows who, what, when, whether you need to reply, and priority level. Fully filters noise |
| **[Group] summary** | One-click group digest: today's topics by category, important announcements with sender & time, pending items to follow up on |
| **[Group] notices & tasks** | Extracts structured tables: announcements/notices (with publisher & time), task list (who assigned → who's responsible → deadline → priority), meeting schedule (topic → time → online/offline → meeting ID/address) |
| **[Group] activity stats** | Speaker leaderboard with message count & percentage, time distribution analysis, LLM-powered topic breakdown. Helps decide which groups to mute |
| **[Person] in [Group]** | Filters and summarizes everything a specific person said in a group: main viewpoints, questions asked, help provided to others |
| **[Group] shared files** | Organizes files & links by type: documents (Word/PDF/PPT/Excel), links (with titles), mini-programs. Shows filename, sender, and time |

####  Search & Discovery
Find anything in your chat history:

| You say | It does |
|---------|---------|
| **Search [keyword]** | Full-text search across ALL messages. Returns time, sender, and content preview for every match. Example: "Search contract", "Search meeting", "Search 138****" |
| **Find Word documents** | Scans message databases for shared files by type. Supports: Word (.doc/.docx), Excel (.xls/.xlsx), PDF, PowerPoint (.ppt/.pptx), TXT, CSV, ZIP/RAR. Shows filename, sender, file size, and date. Narrow down: "Find Excel files", "Find PDF" |
| **Friend statistics** | Contact list overview: total contacts, mutual friends, one-way contacts, deleted markers. Honest about limitations (WeChat doesn't locally store who blocked you) |

####  Real-Time Monitoring
- **File-change detection**: Monitors encrypted WeChat database files every 5 seconds
- **Instant processing**: New message → auto re-decrypt → filter → AI classify → important items pop up immediately
- **Natural language**: Just type in the chat UI — AI understands your intent and routes to the right analysis

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

####  个人聊天分析
深度分析你与任何人的一对一对话：

| 你说 | 它做什么 |
|------|----------|
| **分析[某人]** | 全面深度分析：关系类型与亲密度评分(1-10)、沟通模式（谁更主动？文字还是语音？）、话题分布与频率、关键事件时间线（标注日期）、双方各自的待办与承诺、对方当前状态与需求、风险提醒（快到期的事/误会/矛盾） |
| **总结我和[某人]的聊天要点** | 提炼核心结论、已达成的共识、存在的分歧、你需要做什么——结构化输出 |
| **[某人]的情绪和态度** | 分析语气（正常/着急/生气/客气/抱怨/求助）、判断字面背后的真实意图、告诉你是否需要回复、建议回应方式 |
| **我和[某人]聊了什么时间地点** | 提取所有时间、地点、金额、价格、手机号、文件名——按类别整理 |
| **整理[某人]的聊天** | 自动识别主题并归类，输出结构化表格（时间/事项/联系人/状态）、已完成与未完成清单 |
| **[某人]有什么待办和承诺** | 提取表格：事项、提出方、截止时间、优先级（高/中/低）、状态（待做/已完成/已过期）。单独列出「我答应了但没做的」和「对方答应了但没兑现的」 |
| **提取待办事项** | 扫描最近两周所有一对一聊天，挖出全部待办汇总成一张总清单 |

####  微信群分析
告别爬 99+ 条消息：

| 你说 | 它做什么 |
|------|----------|
| **最近有什么重要消息** | 自动选择活跃群 → 过滤噪音（图片/语音/表情/系统消息）→ AI 1-5分重要性分类 → 按话题生成摘要报告。一次处理 50 个群、数百条消息 |
| **谁@我了** | 扫描所有群，找出@你的消息。标注谁发的、什么事、要不要回复、优先级。完全过滤噪音 |
| **[群名]总结** | 今日话题分类、重要通知（标注发布者和时间）、待跟进事项 |
| **[群名]通知和任务** | 结构化提取：通知/公告清单、任务表（布置人→负责人→截止时间→优先级）、会议安排（主题→时间→线上/线下→会议号/地址） |
| **[群名]谁最活跃** | 发言排行榜（消息数+占比）、AI 话题分析。帮你判断哪些群值得关注、哪些可以免打扰 |
| **只看[某人]在[群名]发了什么** | 过滤并总结特定人在群里的所有发言：主要观点、提出的问题、给别人的回复 |
| **[群名]发了什么文件** | 按类型整理群文件和链接：文档类（Word/PDF/PPT/Excel）、链接类（含标题）、小程序。标注文件名、发送者、时间 |

####  搜索与发现
在海量聊天记录中精准定位：

| 你说 | 它做什么 |
|------|----------|
| **搜索[关键词]** | 全库全文搜索，返回每条匹配消息的时间、发送者、内容预览。例如「搜索合同」「搜索会议」「搜索138」 |
| **帮我找Word文档** | 扫描消息数据库中的文件。支持：Word(.doc/.docx)、Excel(.xls/.xlsx)、PDF、PPT(.ppt/.pptx)、TXT、CSV、ZIP/RAR。显示文件名、发送者、文件大小、日期。可细化：「找Excel」「找PDF」 |
| **我的好友统计** | 通讯录总览：联系人总数、好友数、单向联系人、已删除标记。诚实标注限制（无法从本地数据库判断谁拉黑了你） |

####  实时监听
- **文件变化检测**：每 5 秒监控微信加密数据库文件的修改时间
- **即时处理**：新消息 → 自动重新解密 → 过滤 → AI 分类 → 重要消息秒级弹出
- **自然语言交互**：在聊天界面直接输入中文，AI 自动理解意图并路由到对应分析功能

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
