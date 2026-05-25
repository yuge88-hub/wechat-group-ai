"""Chat UI server for WeChat AI Agent — full capability set."""
import sys, os, json, re, time
from collections import Counter

if getattr(sys, 'frozen', False):
    APP_ROOT = os.path.dirname(sys.executable)
    BUNDLE = os.path.join(APP_ROOT, '_internal')
    WXD_PATH = os.path.join(BUNDLE, 'weixin-decrypte-script')
    HTML_DIR = os.path.join(BUNDLE, 'agent')
else:
    APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    WXD_PATH = os.path.join(APP_ROOT, 'weixin-decrypte-script')
    HTML_DIR = os.path.join(APP_ROOT, 'agent')

sys.path.insert(0, WXD_PATH)
sys.path.insert(0, APP_ROOT)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from db_service import DBService
from openai import OpenAI

app = Flask(__name__); CORS(app)
db = None; client = None; MY_WXID = None

# ═══════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════
def init_server():
    global db, client, MY_WXID
    userprofile = os.environ.get('USERPROFILE', '')
    xwechat = os.path.join(userprofile, 'Documents', 'xwechat_files')
    db_dir = None
    if os.path.isdir(xwechat):
        for name in os.listdir(xwechat):
            if name.startswith('wxid_') and '_' in name:
                candidate = os.path.join(xwechat, name, 'db_storage')
                if os.path.isdir(candidate):
                    db_dir = candidate
                    # Extract my wxid from dir name: wxid_xxx_df23 → wxid_xxx
                    parts = name.rsplit('_', 1)
                    if len(parts) == 2:
                        MY_WXID = parts[0]
                    break
    if not db_dir:
        raise FileNotFoundError("Cannot find WeChat data directory")
    db = DBService(db_dir); db.init()
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    client = OpenAI(api_key=api_key, base_url='https://api.deepseek.com/v1')

# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════
def _find(query):
    r = []
    for c in db.get_contacts(keyword=query, limit=10, offset=0).items:
        r.append({'name': c.display_name(), 'id': c.username, 'type': 'contact'})
    for cr in db.get_chatrooms(keyword=query, limit=10, offset=0).items:
        r.append({'name': cr.display_name(), 'id': cr.name, 'type': 'group'})
    for s in db.get_sessions(keyword=query, limit=10, offset=0).items:
        n = s.nick_name or s.username
        r.append({'name': n, 'id': s.username,
                  'type': 'group' if '@chatroom' in s.username else 'contact'})
    return r[:15]

def _msgs(target_id, limit=300, start_time=None):
    msgs, total = db.get_messages(talker=target_id, limit=limit, offset=0, start_time=start_time)
    contact = db._contact_cache.get(target_id)
    name = contact.display_name() if contact else target_id
    items = []
    for m in msgs:
        who = '我' if m.is_self else (m.sender_name or m.sender)
        c = m.content
        if c.startswith('<?xml') or '<msg>' in c: c = '[文件/链接]'
        if c == '[voice]': c = '[语音]'
        if c == '[voip]': c = '[通话]'
        items.append({'time': m.time, 'sender': who, 'content': c, 'is_self': m.is_self,
                       'type': m.type, 'sub_type': m.sub_type})
    return {'name': name, 'id': target_id, 'total': total, 'items': items,
            'text': '\n'.join(f"[{i['time']}] {i['sender']}: {i['content']}" for i in items),
            'time_range': f"{msgs[0].time} ~ {msgs[-1].time}" if msgs else 'N/A'}

def _ask(prompt, max_tok=1000, temp=0.3):
    r = client.chat.completions.create(
        model='deepseek-chat',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=max_tok, temperature=temp)
    return r.choices[0].message.content, r.usage.total_tokens

def _resolve_target(user_msg):
    """Extract target name from various patterns."""
    for kw in ('分析', '总结', '整理', '看', '看看', '关于'):
        if kw in user_msg:
            t = user_msg.split(kw, 1)[-1].strip()
            for sfx in ('的聊天', '的对话', '的微信', '聊了什么', '最近发了什么', '说了什么',
                         '说过什么', '的消息', '在群里', '在群里的发言', '发了什么',
                         '聊天要点', '聊天记录', '聊天总结', '聊天要点总结'):
                t = t.replace(sfx, '')
            t = t.strip().rstrip('，。.!！?？ ')
            if t and len(t) < 30: return t
    # "我和XX" pattern
    for prefix in ('我和', '我跟', '我和我'):
        if prefix in user_msg:
            t = user_msg.split(prefix, 1)[-1].strip()
            for sfx in ('的聊天', '的对话', '聊了什么', '聊天要点', '聊天总结'):
                t = t.replace(sfx, '')
            t = t.strip().rstrip('，。！？ ')
            if t and len(t) < 30: return t
    return None

# ═══════════════════════════════════════════
# CAPABILITY HANDLERS
# ═══════════════════════════════════════════

def analyze_person(target_name, user_msg):
    """Deep analysis of a person's chat — multiple modes."""
    results = _find(target_name)
    if not results: return f'没找到「{target_name}」'
    r = results[0]
    data = _msgs(r['id'], limit=400)

    if not data['items']: return f'「{data["name"]}」暂无聊天记录。'

    header = f"## {data['name']}\n{data['total']}条消息 · {data['time_range']}\n"
    text = data['text'][:8000]

    # ── Mode 1: 待办/承诺提取 ──
    if any(kw in user_msg for kw in ('待办', 'todo', '要做', '承诺', '答应', '约定')):
        prompt = f"""从聊天中提取所有待办、承诺、约定。输出Markdown表格：

| 事项 | 提出方 | 截止时间 | 重要性 | 状态 |
|------|--------|----------|--------|------|
| ... | 对方/我 | 具体日期或"未明确" | 高/中/低 | 待做/已完成/已过期 |

然后列出：
- **我已答应但未完成的事**
- **对方答应但未兑现的事**
- **近期需要跟进的事项**

{text}"""
        result, _ = _ask(prompt, 1200)
        return header + '\n' + result

    # ── Mode 2: 情绪/意图判断 ──
    if any(kw in user_msg for kw in ('情绪', '语气', '态度', '意图', '着急', '生气', '客气', '抱怨', '求助')):
        prompt = f"""分析对话中对方的情绪和意图，输出：

**整体语气**: 正常/着急/生气/客气/抱怨/求助（选一个或多个）

**情绪变化**: 按时间线标注情绪转折点

**真实意图**: 对方到底想要什么？（不只是字面意思）

**是否需要回复**: 是/否，理由

**建议回应方式**: 1-2句话

{text}"""
        result, _ = _ask(prompt, 800)
        return header + '\n' + result

    # ── Mode 3: 关键数据提取 ──
    if any(kw in user_msg for kw in ('时间', '地点', '金额', '数量', '数字', '见面', '地址', '电话', '手机号')):
        prompt = f"""从聊天中提取所有关键信息，结构化输出：

### 时间与事件
- 列出所有涉及具体时间的约定

### 地点与地址
- 列出所有提到的具体地点

### 金额与数量
- 列出所有提到的金额、数量、价格

### 联系方式
- 列出所有提到的手机号、微信号、邮箱

### 文件与链接
- 列出所有分享的文件名和链接标题

{text}"""
        result, _ = _ask(prompt, 1000)
        return header + '\n' + result

    # ── Mode 4: 要点/结论提取 ──
    if any(kw in user_msg for kw in ('要点', '结论', '重点', '核心', '总结', '概括', '提炼')):
        prompt = f"""从聊天中提炼核心要点，输出：

**核心结论** (3-5条，每条一句话):
- ...

**对方主要诉求**:
- ...

**已达成的共识/决定**:
- ...

**存在的分歧/未解决问题**:
- ...

**我需要做什么**:
- ...

{text}"""
        result, _ = _ask(prompt, 1000)
        return header + '\n' + result

    # ── Mode 5: 结构化整理 ──
    if any(kw in user_msg for kw in ('整理', '表格', '清单', '结构化', '归类', '分类')):
        prompt = f"""把聊天内容整理成结构化清单：

### 按主题分类
（自动识别主题并归类）

### 关键信息表
| 类别 | 内容 | 时间 | 相关人 |
|------|------|------|--------|

### 未完成事项清单
- [ ] ...

### 已完成事项
- [x] ...

{text}"""
        result, _ = _ask(prompt, 1200)
        return header + '\n' + result

    # ── Default: 全面深度分析 ──
    prompt = f"""对以下微信聊天做全面深度分析（500字内），直接输出，不要开场白：

## 1. 关系判断
- 双方关系和亲密度（1-10分）

## 2. 沟通模式
- 谁更主动、偏好方式（文字/语音/通话）、回复速度

## 3. 核心话题 TOP5
- 按频率排序，标注占比

## 4. 关键事件时间线
- 重要节点，标注日期

## 5. 待办与承诺
- 双方各自答应了什么还没做

## 6. 对方当前状态
- 最近在忙什么、有什么需求或困扰

## 7. 风险提醒
- 有没有需要注意的（快到期的事、矛盾、误会）

{text}"""
    result, _ = _ask(prompt, 1500)
    return header + '\n' + result


def analyze_group(target_name, user_msg):
    """Group chat analysis — multiple detailed modes."""
    results = _find(target_name)
    if not results: return f'没找到「{target_name}」'
    r = results[0]
    data = _msgs(r['id'], limit=600)

    if not data['items']: return f'「{data["name"]}」暂无消息。'
    header = f"## {data['name']}\n{data['total']}条消息 · {data['time_range']}\n"
    text = data['text'][:8000]

    # ── Mode 1: @我的消息 ──
    if any(kw in user_msg for kw in ('@我', '艾特', '提到我', 'at我')):
        at_msgs = [m for m in data['items'] if not m['is_self'] and
                   ('@' in m['content'] or (MY_WXID and MY_WXID in m['content']))]
        if not at_msgs:
            return f'{header}\n最近没有@你的消息。'
        atext = '\n'.join(f"[{m['time']}] {m['sender']}: {m['content'][:300]}" for m in at_msgs[:40])
        prompt = f"""逐条分析以下@我的消息：

对每条消息标注：
- **谁**: 发送者
- **什么事**: 简要说明
- **需要回复吗**: 是/否
- **优先级**: 高/中/低
- **建议**: 一句话

最后总结：今天/本周有{len(at_msgs)}条@你的消息，需要回复{sum(1 for m in at_msgs if '?' in m.get('content','') or '吗' in m.get('content',''))}条。

{atext[:6000]}"""
        result, _ = _ask(prompt, 1200)
        return (f"{header}## @我的消息 · 共{len(at_msgs)}条\n\n{result}")

    # ── Mode 2: 发言统计 ──
    if any(kw in user_msg for kw in ('统计', '活跃', '谁最', '发言排行', '排行榜')):
        senders = Counter(m['sender'] for m in data['items'] if not m['is_self'])
        top = senders.most_common(20)
        total = len(data['items'])
        # Time distribution
        hours = Counter(m['time'][:13] for m in data['items'] if ' ' in m['time'])
        lines = [f"{header}## 发言统计\n总消息: {total}条 | 发言人: {len(senders)}人\n"]
        lines.append("### 发言排行\n| # | 发言人 | 消息数 | 占比 |\n|---|--------|--------|------|")
        for i, (name, count) in enumerate(top):
            pct = count / total * 100 if total > 0 else 0
            lines.append(f"| {i+1} | {name[:18]} | {count} | {pct:.1f}% |")
        # Topic analysis via LLM
        prompt = f"""分析这个群的讨论话题分布（关键字列表，5个以内），以及这个群属于什么类型：
{text[:4000]}"""
        result, _ = _ask(prompt, 500)
        lines.append(f"\n### 话题分析\n{result}")
        return '\n'.join(lines)

    # ── Mode 3: 任务/通知提取 ──
    if any(kw in user_msg for kw in ('任务', '待办', '安排', '布置', '通知', '公告', '会议')):
        # Filter system messages and @all messages first
        notices = [m for m in data['items']
                   if m['type'] == 10000 or '@所有人' in m['content'] or '@all' in m['content'].lower()][:20]
        task_msgs = [m for m in data['items']
                     if any(kw in m['content'] for kw in ('记得', '别忘了', '请', '需要', '截止',
                            '之前', '之前', '完成', '提交', '报名', '参加', '会议', '开会',
                            '时间', '地点', 'zoom', '腾讯会议', '会议号'))][:50]

        ntext = '\n'.join(f"[{m['time']}] {m['sender']}: {m['content'][:200]}" for m in notices)
        ttext = '\n'.join(f"[{m['time']}] {m['sender']}: {m['content'][:200]}" for m in task_msgs)

        prompt = f"""从群聊中提取所有通知、任务、会议，结构化输出：

### 通知/公告
（列出最近的重要通知，标注发布者和时间）

### 任务清单
| 任务 | 布置人 | 负责人 | 截止时间 | 优先级 |
|------|--------|--------|----------|--------|

### 会议安排
| 会议主题 | 时间 | 方式(线上/线下) | 会议号/地址 |
|----------|------|----------------|-------------|

近期通知:
{ntext[:4000]}

任务相关:
{ttext[:4000]}"""
        result, _ = _ask(prompt, 1200)
        return f"{header}## 通知/任务/会议提取\n{result}"

    # ── Mode 4: 只看特定人 ──
    if any(kw in user_msg for kw in ('发了什么', '说过什么', '发言', '讲过')) and target_name:
        person_msgs = [m for m in data['items'] if target_name in m['sender']]
        if not person_msgs:
            return f'{header}\n没找到「{target_name}」的发言。'
        ptext = '\n'.join(f"[{m['time']}] {m['content'][:300]}" for m in person_msgs[-80:])
        prompt = f"""总结这个人最近在群里的发言：

**发言频率**: {len(person_msgs)}条
**主要观点/内容**:
**提出的问题/需求**:
**给群友的回复/帮助**:

{ptext[:6000]}"""
        result, _ = _ask(prompt, 800)
        return (f"{header}## {target_name}的发言 · {len(person_msgs)}条\n\n{result}")

    # ── Mode 5: 文件/链接整理 ──
    if any(kw in user_msg for kw in ('文件', '链接', '图片', '表格', 'pdf', '文档', '发了什么文件')):
        files = [m for m in data['items'] if m['type'] == 49 or '[文件' in m['content']]
        if not files: return f'{header}\n最近没有文件/链接。'
        ftext = '\n'.join(f"[{m['time']}] {m['sender']}: {m['content'][:250]}" for m in files[-40:])
        prompt = f"""整理群里分享的文件和链接，按类型分类：
- **文档** (Word/PDF/PPT/Excel): 文件名、谁发的
- **链接**: 标题、URL摘要、谁发的
- **图片/截图**: 如果文件名有意义则列出
- **小程序**: 名称、功能

{ftext[:6000]}"""
        result, _ = _ask(prompt, 1000)
        return f"{header}## 文件/链接整理\n{result}"

    # ── Default: 群聊摘要 ──
    recent = [m for m in data['items']
              if m['type'] not in (3, 34, 43, 47, 50, 10000)
              and len(m.get('content', '')) > 5][:120]
    if not recent: return f'{header}\n最近没有有效消息。'
    rtext = '\n'.join(f"[{m['time']}] {m['sender']}: {m['content'][:150]}" for m in recent)

    prompt = f"""生成群聊摘要报告：

### 今日话题概况
（按主题分，每个主题1-2句话）

### 重要通知/决议
（标注发布者和时间）

### 待跟进事项
（需要关注或处理的事）

### 一句话总结
（给这个群今天的讨论一句话定性）

{rtext[:7000]}"""
    result, _ = _ask(prompt, 1200)
    return f"{header}## 群聊摘要\n{len(recent)}条有效消息\n\n{result}"


def search_files(user_msg):
    """Search for document files (Word, Excel, PDF, PPT, etc.) in chat history."""
    import sqlite3, shutil, re as _re

    # Determine file type filter from user message
    ext_map = {
        'word': ['.doc', '.docx'], 'doc': ['.doc', '.docx'], '文档': ['.doc', '.docx'],
        'excel': ['.xls', '.xlsx'], '表格': ['.xls', '.xlsx'], 'xls': ['.xls', '.xlsx'],
        'pdf': ['.pdf'], 'ppt': ['.ppt', '.pptx'], '幻灯片': ['.ppt', '.pptx'],
        'txt': ['.txt'], 'csv': ['.csv'],
        'zip': ['.zip', '.rar'], '压缩': ['.zip', '.rar'],
    }
    target_exts = []
    for kw, exts in ext_map.items():
        if kw in user_msg.lower():
            target_exts.extend(exts)

    if not target_exts:
        target_exts = ['.doc', '.docx', '.xls', '.xlsx', '.pdf', '.ppt', '.pptx', '.txt', '.csv', '.zip', '.rar']

    # Scan message DBs for file XML patterns
    msg_dbs = []
    db_dir = db.data_dir
    for root, dirs, files in os.walk(db_dir):
        for f in files:
            if f.startswith('message_') and f.endswith('.decrypted.db'):
                msg_dbs.append(os.path.join(root, f))

    found = []
    seen = set()

    for mdb in msg_dbs[:1]:  # Only scan first message DB (largest)
        tmp = mdb + '.fs_tmp'
        shutil.copy2(mdb, tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row

        tables = [r['name'] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
        ).fetchall()]

        checked = 0
        for tbl in tables:
            if checked >= 200:  # Scan more tables
                break
            if len(found) >= 100:  # Enough results
                break
            try:
                rows = conn.execute(
                    f"SELECT create_time, real_sender_id, message_content "
                    f"FROM [{tbl}] ORDER BY create_time DESC LIMIT 30"
                ).fetchall()
                checked += 1
            except:
                continue

            for row in rows:
                # Decompress if needed (ZSTD)
                c = row['message_content']
                if isinstance(c, bytes):
                    if c[:4] == b'\x28\xb5\x2f\xfd':
                        try:
                            import zstandard
                            dctx = zstandard.ZstdDecompressor()
                            c = dctx.decompress(c, max_output_size=10*1024*1024)
                        except:
                            continue
                    try:
                        c = c.decode('utf-8', errors='ignore')
                    except:
                        continue
                c = str(c)

                # Check if it's a file message
                if '<type>6</type>' not in c and '<appmsg' not in c:
                    continue
                # Skip if it's a link/share, not a file
                if '<type>5</type>' in c and '<type>6</type>' not in c:
                    continue

                # Extract filename
                title_m = _re.search(r'<title>(.*?)</title>', c)
                filename = title_m.group(1) if title_m else 'unknown'

                # Filter by extension
                ext_match = ''
                for ext in target_exts:
                    if filename.lower().endswith(ext) or ext in c.lower():
                        ext_match = ext
                        break
                if not ext_match:
                    continue

                # Extract size
                size_m = _re.search(r'<totallen>(\d+)</totallen>', c)
                filesize = int(size_m.group(1)) if size_m else 0

                ts = row['create_time']
                sid = row['real_sender_id']
                key = f"{ts}|{filename}"
                if key not in seen:
                    seen.add(key)
                    found.append({
                        'time': ts, 'filename': filename,
                        'size': filesize, 'ext': ext_match, 'sender_id': sid,
                    })
        conn.close()
        os.remove(tmp)

    if not found:
        return '没有找到文件。试试「找Word文档」或「找Excel表格」'

    found.sort(key=lambda x: x['time'], reverse=True)
    from datetime import datetime

    # Resolve sender names
    lines = [f"## 文件搜索 · 找到{len(found)}个\n"]
    for f in found[:40]:
        name = db._name2id_cache.get(f['sender_id'], str(f['sender_id']))
        contact = db._contact_cache.get(name)
        sender = contact.display_name() if contact else name
        ts = datetime.fromtimestamp(f['time']).strftime('%m/%d %H:%M')
        size_str = f"{f['size']/1024:.0f}KB" if f['size'] > 0 else "?"
        lines.append(f"- [{ts}] **{sender[:12]}** — `{f['filename'][:50]}` ({size_str})")

    if len(found) > 40:
        lines.append(f"\n... 还有{len(found)-40}个文件")
    return '\n'.join(lines)


def search_messages(user_msg):
    """Full-text search across all messages."""
    # Extract keyword
    kw = None
    for prefix in ('搜索', '找', '查找', '帮我找', '搜'):
        if prefix in user_msg:
            kw = user_msg.split(prefix, 1)[-1].strip().rstrip('，。！？')
            break
    if not kw:
        kw = user_msg.strip()

    results, total = db.search_messages(keyword=kw, limit=30, offset=0)
    if not results:
        return f'没找到包含「{kw}」的消息。'

    lines = [f"## 搜索「{kw}」 · 找到{total}条\n"]
    for r in results[:20]:
        name = r.get('sender_name', '') or str(r.get('sender_id', ''))
        lines.append(f"- [{r.get('time','')}] **{name[:15]}**: {r.get('content','')[:150]}")

    if total > 20:
        lines.append(f"\n... 还有{total-20}条结果")
    return '\n'.join(lines)


def todo_extraction():
    """Extract TODOs from recent messages."""
    now = int(time.time())
    start = now - 14 * 86400  # last 2 weeks
    sessions = db.get_sessions(keyword='', limit=100, offset=0)

    all_items = []
    for s in sessions.items:
        if '@chatroom' in s.username or 'gh_' in s.username:
            continue
        try:
            msgs, _ = db.get_messages(talker=s.username, start_time=str(start), limit=0, offset=0)
        except:
            continue
        for m in msgs:
            if m.is_self:
                continue
            c = m.content or ''
            if any(kw in c for kw in ('记得', '别忘了', '帮我', '要做', '明天', '今天', '下周',
                                        '尽快', '抓紧', '安排', '弄一下', '处理', '发我', '给我')):
                contact = db._contact_cache.get(s.username)
                name = contact.display_name() if contact else s.username
                all_items.append(f"[{m.time}] [{name}] {c[:200]}")

    if not all_items:
        return '最近没有发现待办事项。'

    text = '\n'.join(all_items[:80])
    prompt = f"""从以下聊天中提取所有待办事项，输出Markdown表格：
| 事项 | 来源 | 截止时间 | 优先级 |
|------|------|----------|--------|

{text[:6000]}"""
    result, _ = _ask(prompt)
    return f"## 待办事项提取（最近两周）\n{result}"


def friend_stats():
    """Count friends and analyze contact list."""
    import sqlite3, shutil
    contact_db = db._contact_db
    if not contact_db or not os.path.exists(contact_db):
        return '无法访问联系人数据库。'

    tmp = contact_db + '.fs_tmp'
    shutil.copy2(contact_db, tmp)
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row

    base = "WHERE username NOT LIKE 'gh_%' AND username NOT LIKE '%@chatroom' AND username NOT LIKE '%@openim'"
    total = conn.execute(f"SELECT COUNT(*) FROM contact {base}").fetchone()[0]
    friends = conn.execute(f"SELECT COUNT(*) FROM contact {base} AND local_type != 3").fetchone()[0]
    nonfriends = conn.execute(f"SELECT COUNT(*) FROM contact {base} AND local_type = 3").fetchone()[0]
    deleted = conn.execute(f"SELECT COUNT(*) FROM contact {base} AND delete_flag != 0").fetchone()[0]

    conn.close()
    os.remove(tmp)

    return f"""## 微信通讯录统计

| 类别 | 数量 |
|------|------|
| 联系人总数 | {total} |
| 好友（双向） | {friends} |
| 单向/非好友 | {nonfriends} |
| 已删除标记 | {deleted} |

> 注：「好友」指通讯录中保存的联系人。部分人可能已将你删除，但微信本地数据库无法直接判断对方是否拉黑你。如果发消息提示「需要好友验证」则说明已被删。"""


def run_digest():
    """Group digest."""
    from agent.message_filter import MessageFilter
    from agent.prompt_builder import (build_classify_prompt, format_blocks_for_classify,
                                       build_digest_prompt, format_blocks_for_digest)
    from agent.config import FilterConfig

    sessions = db.get_sessions(keyword='', limit=80, offset=0)
    groups = [{'id': s.username, 'name': s.nick_name or s.username}
              for s in sessions.items if '@chatroom' in s.username][:25]
    now = int(time.time()); start = now - 6 * 3600
    all_msgs = []
    for g in groups:
        try:
            m, _ = db.get_messages(talker=g['id'], start_time=str(start), limit=0, offset=0)
            all_msgs.extend(m)
        except: pass
    if not all_msgs: return '最近没有新消息。'

    filt = MessageFilter(FilterConfig())
    blocks = filt.pipeline(all_msgs)
    if not blocks: return f'过滤后无有效消息。'

    BATCH = 25; all_cls = []
    for i in range(0, len(blocks), BATCH):
        batch = blocks[i:i+BATCH]
        t = format_blocks_for_classify(batch)
        sp, up = build_classify_prompt(t, time_range='最近6小时')
        r = client.chat.completions.create(model='deepseek-chat',
            messages=[{'role': 'system', 'content': sp}, {'role': 'user', 'content': up}],
            max_tokens=2048, temperature=0.1)
        try:
            d = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', r.choices[0].message.content.strip()))
            all_cls.extend(d if isinstance(d, list) else [d])
        except: pass

    important = []
    for i, cls in enumerate(all_cls):
        if i < len(blocks) and cls.get('importance', 0) >= 3:
            b = blocks[i]
            important.append({
                'importance': cls.get('importance', 0), 'summary_zh': cls.get('summary_zh', ''),
                'topic_tags': cls.get('topic_tags', []), 'group_name': b.group_name,
                'sender_name': b.sender_name, 'content': b.combined_content[:200], 'time': b.time_start,
            })
    if not important: return f'分析了{len(all_msgs)}条消息，没有特别重要的。'

    imp_text = format_blocks_for_digest([
        {'importance': i['importance'], 'summary_zh': i['summary_zh'],
         'topic_tags': i['topic_tags'],
         'block': {'group_name': i['group_name'], 'sender_name': i['sender_name'],
                   'content': i['content'], 'time': i['time']}}
        for i in important
    ])
    sp, up = build_digest_prompt(imp_text, 6, time.strftime('%Y-%m-%d %H:%M:%S'))
    r = client.chat.completions.create(model='deepseek-chat',
        messages=[{'role': 'system', 'content': sp}, {'role': 'user', 'content': up}],
        max_tokens=4096, temperature=0.3)
    return (f"> {len(all_msgs)}条消息 | {len(important)}条重要 | {len(groups)}个群\n\n"
            f"{r.choices[0].message.content}")


# ═══════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════
@app.route('/')
def index():
    return send_from_directory(HTML_DIR, 'chat.html')


@app.route('/api/chat', methods=['POST'])
def handle_chat():
    user_msg = request.get_json().get('message', '').strip()
    if not user_msg:
        return jsonify({'reply': '请输入内容'})

    msg = user_msg

    # ─── Intent Routing ───

    # 0. Generic placeholder
    if msg in ('分析某人的聊天', '分析某人', '分析XX', '分析某个人', '搜索关键词'):
        return jsonify({'reply': '请告诉我具体信息。比如「分析玲妈妈」或「搜索合同」'})

    # 1. File/document search
    if any(kw in msg for kw in ('文档', '表格', 'excel', 'word', 'pdf', 'ppt', 'doc', 'xls')):
        if any(kw in msg for kw in ('找', '搜索', '搜', '有没有', '帮我', '列出')):
            return jsonify({'reply': search_files(msg)})

    # 2. TODO extraction
    if any(kw in msg for kw in ('待办', 'todo', '要做的事', '承诺', '别忘了', '未完成')):
        return jsonify({'reply': todo_extraction()})

    # 3. @me messages (global)
    if any(kw in msg for kw in ('@我', '艾特我', '提到我', '谁找我', '谁@我')):
        sessions = db.get_sessions(keyword='', limit=50, offset=0)
        results = []; cut = int(time.time()) - 7*86400
        for s in sessions.items:
            if '@chatroom' not in s.username: continue
            try: d = _msgs(s.username, limit=200, start_time=str(cut))
            except: continue
            at_msgs = [m for m in d['items'] if not m['is_self'] and
                       ('@' in m['content'] or (MY_WXID and MY_WXID in m['content']))]
            if at_msgs:
                name = s.nick_name or s.username
                for m in at_msgs[:5]:
                    results.append(f"- [{m['time']}] **{name}** {m['sender']}: {m['content'][:150]}")
        if results:
            return jsonify({'reply': '## 最近@你的消息\n\n' + '\n'.join(results[:40])})
        return jsonify({'reply': '最近一周没有@你的消息。'})

    # 4. Group digest
    if any(kw in msg for kw in ('最近消息', '摘要', '总结群', '群消息', '有什么重要',
                                  '群聊总结', '今天群里', '群摘要', '发生什么')):
        return jsonify({'reply': run_digest()})

    # 5. Friend stats
    if any(kw in msg for kw in ('好友统计', '通讯录', '多少好友', '联系人统计', '多少联系人')):
        return jsonify({'reply': friend_stats()})

    # 6. General search (keyword/全文)
    if any(kw in msg for kw in ('搜索', '找', '查找', '搜', '找出', '帮我找', '有没有', '提到', '包含')):
        if any(kw in msg for kw in ('文档', '表格', '文件', 'word', 'excel', 'pdf', 'ppt', '待办')):
            return jsonify({'reply': search_files(msg)})
        return jsonify({'reply': search_messages(msg)})

    # 7. Analyze person or group (target name extracted)
    target = _resolve_target(msg)
    if target and target not in ('消息', '聊天', '对话', '微信', '某人', 'XX', '某某', '谁',
                                   '这个人', '那个人', '关键词', '文件', '文档', '表格'):
        is_group = any(kw in msg for kw in ('群', '@我', '艾特', '发言排行', '统计',
                                              '谁在群里', '群里', '群聊'))
        if is_group:
            return jsonify({'reply': analyze_group(target, msg)})
        else:
            return jsonify({'reply': analyze_person(target, msg)})

    # 8. Fallback: LLM
    prompt = f"""你是微信群AI助手。用户说: "{msg}"

判断意图并输出JSON: {{"action": "analyze_person|analyze_group|search|digest|todo|chat", "target": "目标名或null", "reply": "如果是闲聊就回复这句，告诉用户你能做什么"}}

如果用户想分析某人的聊天，action=analyze_person, target=人名
如果用户想看群聊总结或摘要，action=digest
如果用户想搜索，action=search, target=关键词
如果是闲聊打招呼，action=chat

只输出JSON:"""
    try:
        resp = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=300, temperature=0)
        intent = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', resp.choices[0].message.content.strip()))
    except:
        intent = {'action': 'chat', 'reply': '你可以：\n• 分析某人 — 「分析玲妈妈」\n• 群聊摘要 — 「最近有什么重要消息」\n• 搜索 — 「搜索合同」\n• 待办 — 「提取待办事项」\n• @我 — 「谁@我了」'}

    if intent.get('action') == 'analyze_person' and intent.get('target'):
        return jsonify({'reply': analyze_person(intent['target'], msg)})
    elif intent.get('action') == 'analyze_group' and intent.get('target'):
        return jsonify({'reply': analyze_group(intent['target'], msg)})
    elif intent.get('action') == 'digest':
        return jsonify({'reply': run_digest()})
    elif intent.get('action') == 'todo':
        return jsonify({'reply': todo_extraction()})
    elif intent.get('action') == 'search' and intent.get('target'):
        return jsonify({'reply': search_messages(intent['target'])})
    else:
        return jsonify({'reply': intent.get('reply', '你好！我可以帮你分析微信聊天。试试输入「分析玲妈妈」或「最近消息」')})


def start_server(port=5080):
    init_server()
    import webbrowser
    webbrowser.open(f'http://127.0.0.1:{port}')
    app.run(host='127.0.0.1', port=port, debug=False)
