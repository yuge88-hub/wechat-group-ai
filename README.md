# 微信群 AI Agent

自动读取微信本地数据库，用 AI 帮你整理群聊重要信息。**只读不写，不会自动回复。**

## 功能

- **群聊智能摘要** — 自动筛选 50 个活跃群，过滤噪音，AI 按话题生成结构化报告
- **单群/单人分析** — 指定某个群或联系人，做深度分析（关系、时间线、话题分布）
- **实时监听** — 监控微信数据库变化，新消息到达后几秒内推送重要内容
- **面试/入职提取** — 从聊天记录中自动识别面试邀约、入职通知、offer 状态

## 原理

```
微信本地加密数据库 → 内存提取密钥 → SQLCipher 解密 → AI 分析 → Markdown 报告
```

基于 [weixin-decrypte-script](https://github.com/ZedeX/weixin-decrypte-script) 解密微信 4.x 数据库，用 DeepSeek（或任何 OpenAI 兼容 API）做消息分类和摘要生成。

## 环境要求

- Windows 10/11（微信桌面版 4.x）
- Python 3.10+
- 微信已登录
- 管理员权限（首次提取密钥时需要）

## 快速开始

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 以管理员身份运行，提取微信数据库密钥
cd weixin-decrypte-script
python scan_keys.py

# 3. 解密数据库
python decrypt_db.py --auto "C:\Users\<用户名>\Documents\xwechat_files\<wxid>\db_storage" found_keys.txt

# 4. 设置 DeepSeek API Key
$env:DEEPSEEK_API_KEY = "sk-你的密钥"

# 5. 回到项目根目录，开始使用
cd ..
python -m agent.main --once --lookback 6
```

## 使用方式

```powershell
# 单次扫描（回溯最近 N 小时）
python -m agent.main --once --lookback 6

# 分析特定群或联系人
python -m agent.main --once --group "群名关键词" --lookback 720

# 实时监听（文件变化检测）
python -m agent.main --watch

# 自定义配置文件
python -m agent.main --config my_config.yaml --once
```

## 配置

编辑 `agent/config.yaml`：

```yaml
llm:
  provider: "openai"                          # 或 "anthropic"
  api_key: "${DEEPSEEK_API_KEY}"              # 支持环境变量
  base_url: "https://api.deepseek.com/v1"     # DeepSeek 或其他兼容 API
  model_filter: "deepseek-chat"               # 消息分类模型
  model_digest: "deepseek-chat"               # 摘要生成模型

groups:
  mode: "auto"                    # auto=自动选活跃群, manual=手动指定
  watchlist: []                   # manual 模式下的群名列表
  max_groups: 50                  # 最多监控群数

filter:
  min_text_length: 5              # 最小有意义文本长度
  skip_types: [3, 34, 43, 47, 50, 10000]  # 跳过的消息类型

schedule:
  lookback_hours: 24              # 单次扫描默认回溯时长

output:
  digest_dir: "digests"           # 报告输出目录
  console_output: true            # 控制台实时输出
```

## 项目结构

```
wx-chat/
  agent/                          # AI Agent 核心
    config.py                     # 配置加载
    config.yaml                   # 默认配置
    main.py                       # CLI 入口
    agent_core.py                 # 总调度器
    message_filter.py             # 消息过滤管道
    llm_client.py                 # LLM 客户端（支持 OpenAI/Anthropic）
    prompt_builder.py             # Prompt 模板
    group_manager.py              # 群组选择
    digest_generator.py           # 摘要输出
    state_manager.py              # 状态持久化
    live_watch.py                 # 实时文件监听
  weixin-decrypte-script/         # 微信数据库解密（来自 ZedeX）
  digests/                        # 生成的摘要报告
  state/                          # Agent 运行状态
```

## 支持的大模型

| 提供商 | 配置 |
|--------|------|
| DeepSeek | `base_url: "https://api.deepseek.com/v1"` |
| OpenAI | `base_url: "https://api.openai.com/v1"` |
| 任何 OpenAI 兼容 API | 修改 `base_url` 即可 |

## 免责声明

本项目仅供个人数据整理与学习研究使用。请遵守相关法律法规，尊重他人隐私，不要用于自动回复、骚扰或侵犯他人权益。

## License

MIT
