# 聊天消息界面用户体验优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 BOSS 直聘自动化控制台的聊天消息界面，提升会话管理、消息展示和输入交互体验

**Architecture:** 采用增量增强方案，在现有单文件架构（static/dashboard.html）基础上，通过改进 CSS 样式和 JavaScript 逻辑实现功能增强，不引入新的前端框架

**Tech Stack:** HTML5, CSS3, Vanilla JavaScript, FastAPI (后端不变)

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `static/dashboard.html` | 主要修改文件，包含所有 UI 和交互逻辑 |
| `boss_app.py` | 后端 API，可能需要添加会话筛选接口 |
| `boss_state.py` | 数据层，可能需要添加会话状态查询 |

---

## Task 1: 会话列表搜索筛选功能

**Files:**
- Modify: `static/dashboard.html` (会话列表 HTML 结构)
- Modify: `static/dashboard.html` (CSS 样式)
- Modify: `static/dashboard.html` (JavaScript 逻辑)

- [ ] **Step 1: 添加搜索筛选 HTML 结构**

在 `static/dashboard.html` 中找到 `<div class="chat-list">` 部分，替换为：

```html
<div class="chat-list">
  <div class="chat-list-header">
    <input type="text" id="convSearch" placeholder="搜索会话..." class="chat-search" oninput="filterConversations()">
    <div class="chat-tabs">
      <span class="active" data-status="all" onclick="filterByStatus('all', this)">全部</span>
      <span data-status="active" onclick="filterByStatus('active', this)">活跃</span>
      <span data-status="paused" onclick="filterByStatus('paused', this)">已暂停</span>
    </div>
  </div>
  <div class="chat-list-items" id="conversationList">
    <div class="empty" style="padding:20px;">暂无会话</div>
  </div>
</div>
```

- [ ] **Step 2: 添加搜索筛选 CSS 样式**

在 `<style>` 标签中添加：

```css
.chat-list-header {
  padding: 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.chat-search {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  margin-bottom: 8px;
  outline: none;
  font-family: var(--font);
}
.chat-search:focus {
  border-color: var(--accent);
}
.chat-tabs {
  display: flex;
  gap: 4px;
  font-size: 12px;
}
.chat-tabs span {
  padding: 4px 10px;
  cursor: pointer;
  border-radius: 4px;
  color: var(--text-3);
  transition: all .15s;
}
.chat-tabs span:hover {
  background: var(--hover);
  color: var(--text);
}
.chat-tabs span.active {
  background: var(--accent);
  color: #fff;
}
```

- [ ] **Step 3: 添加搜索筛选 JavaScript 逻辑**

在 `<script>` 标签中添加：

```javascript
// 会话搜索筛选
let currentConvStatus = 'all';

function filterConversations() {
  const keyword = document.getElementById('convSearch')?.value?.toLowerCase() || '';
  let filtered = conversations || [];

  // 按状态筛选
  if (currentConvStatus !== 'all') {
    filtered = filtered.filter(c => c.status === currentConvStatus);
  }

  // 按关键词搜索
  if (keyword) {
    filtered = filtered.filter(c =>
      (c.hr_name || '').toLowerCase().includes(keyword) ||
      (c.hr_company || '').toLowerCase().includes(keyword) ||
      (c.job_title || '').toLowerCase().includes(keyword)
    );
  }

  renderConversationList(filtered);
}

function filterByStatus(status, el) {
  currentConvStatus = status;
  document.querySelectorAll('.chat-tabs span').forEach(s => s.classList.remove('active'));
  if (el) el.classList.add('active');
  filterConversations();
}

function renderConversationList(convs) {
  const list = document.getElementById('conversationList');
  if (!convs || !convs.length) {
    list.innerHTML = '<div class="empty" style="padding:20px;">暂无会话</div>';
    return;
  }

  // 未读置顶排序
  const sorted = [...convs].sort((a, b) => {
    if (a.unread_count > 0 && b.unread_count === 0) return -1;
    if (a.unread_count === 0 && b.unread_count > 0) return 1;
    return new Date(b.last_message_at || 0) - new Date(a.last_message_at || 0);
  });

  list.innerHTML = sorted.map(c => {
    const isActive = activeConvId === c.id;
    const unreadBadge = c.unread_count > 0
      ? '<span class="unread">' + c.unread_count + '</span>'
      : '';
    const preview = (c.last_message_text || '').slice(0, 40);
    const meta = [c.hr_company, (c.job_title || '').slice(0, 15)].filter(Boolean).join(' · ');

    return '<div class="chat-list-item' + (isActive ? ' active' : '') + '" onclick="selectConversation(' + c.id + ')">'
      + '<div class="name">' + esc(c.hr_name || '未知') + ' ' + unreadBadge + '</div>'
      + '<div class="preview">' + esc(preview) + '</div>'
      + '<div style="font-size:10px;color:var(--text-3);margin-top:2px;">' + esc(meta) + '</div>'
      + '</div>';
  }).join('');
}
```

- [ ] **Step 4: 修改 loadConversations 使用新的渲染函数**

找到 `function loadConversations()` 函数，修改为：

```javascript
function loadConversations() {
  return fetch('/api/conversations').then(r => r.json()).then(d => {
    conversations = d.conversations || [];
    filterConversations();
  });
}
```

- [ ] **Step 5: 测试搜索筛选功能**

1. 启动服务：`python boss_app.py`
2. 打开浏览器访问 `http://127.0.0.1:8010`
3. 切换到"聊天"标签页
4. 测试搜索框：输入 HR 名称、公司名称、岗位名称
5. 测试状态筛选：点击"全部"、"活跃"、"已暂停"
6. 验证未读会话是否置顶显示

- [ ] **Step 6: 提交代码**

```bash
git add static/dashboard.html
git commit -m "feat(chat): add conversation search and filter functionality"
```

---

## Task 2: 消息时间分组显示

**Files:**
- Modify: `static/dashboard.html` (CSS 样式)
- Modify: `static/dashboard.html` (JavaScript 逻辑)

- [ ] **Step 1: 添加时间分组 CSS 样式**

在 `<style>` 标签中添加：

```css
.msg-date-group {
  margin-bottom: 16px;
}
.msg-date-label {
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
  margin-bottom: 12px;
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}
.msg-date-label::before,
.msg-date-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}
```

- [ ] **Step 2: 添加消息格式化函数**

在 `<script>` 标签中添加：

```javascript
// 按日期分组消息
function groupMessagesByDate(messages) {
  const groups = {};
  const today = new Date().toLocaleDateString('zh-CN');
  const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('zh-CN');

  messages.forEach(m => {
    const date = new Date(m.created_at).toLocaleDateString('zh-CN');
    let label = date;
    if (date === today) label = '今天';
    else if (date === yesterday) label = '昨天';

    if (!groups[label]) groups[label] = [];
    groups[label].push(m);
  });
  return groups;
}

// 格式化消息内容（链接识别、换行）
function formatMessageContent(content) {
  if (!content) return '';
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" style="color:inherit;text-decoration:underline;">$1</a>')
    .replace(/\n/g, '<br>');
}

// 获取消息状态文本
function getMessageStatusText(status) {
  const statusMap = {
    'sent': '已发送',
    'delivered': '已送达',
    'read': '已读',
    'failed': '发送失败'
  };
  return statusMap[status] || '已发送';
}
```

- [ ] **Step 3: 修改 renderMessages 函数**

找到 `function renderMessages(msgs)` 函数，替换为：

```javascript
function renderMessages(msgs) {
  const pane = document.getElementById('chatMessages');
  if (!msgs || !msgs.length) {
    pane.innerHTML = '<div class="empty">暂无消息</div>';
    return;
  }

  const groups = groupMessagesByDate(msgs);
  let html = '';

  Object.entries(groups).forEach(([dateLabel, messages]) => {
    html += '<div class="msg-date-group">';
    html += '<div class="msg-date-label">' + dateLabel + '</div>';

    messages.forEach(m => {
      const cls = m.sender === 'me' ? (m.ai_generated ? 'msg-me ai' : 'msg-me') : 'msg-hr';
      const label = m.sender === 'hr' ? 'HR' : '我' + (m.ai_generated ? ' AI代发' : '');
      const time = new Date(m.created_at).toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
      const statusText = getMessageStatusText(m.delivery_status);
      const content = formatMessageContent(m.content);

      html += '<div class="msg-bubble ' + cls + '">'
        + '<div class="msg-label">' + label + '</div>'
        + '<div class="msg-content">' + content + '</div>'
        + '<div class="msg-meta">'
        + '<span class="msg-time">' + time + '</span>'
        + '<span class="msg-status">' + statusText + '</span>'
        + '</div>'
        + '</div>';
    });

    html += '</div>';
  });

  pane.innerHTML = html;
  pane.scrollTop = pane.scrollHeight;
}
```

- [ ] **Step 4: 测试消息时间分组**

1. 打开聊天界面，选择一个有消息的会话
2. 验证消息是否按日期分组显示
3. 验证"今天"、"昨天"等标签是否正确显示
4. 验证链接是否可点击
5. 验证消息状态是否正确显示

- [ ] **Step 5: 提交代码**

```bash
git add static/dashboard.html
git commit -m "feat(chat): add message date grouping and content formatting"
```

---

## Task 3: 快捷回复模板功能

**Files:**
- Modify: `static/dashboard.html` (HTML 结构)
- Modify: `static/dashboard.html` (CSS 样式)
- Modify: `static/dashboard.html` (JavaScript 逻辑)

- [ ] **Step 1: 添加快捷回复 HTML 结构**

找到聊天输入区域 `<div class="chat-input-area">`，替换为：

```html
<div class="chat-input-area">
  <div class="quick-replies" id="quickReplies">
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('greeting')">问候</button>
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('interest')">表达兴趣</button>
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('wechat')">要微信</button>
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('thanks')">感谢</button>
  </div>
  <div class="input-wrapper">
    <textarea id="chatInput" placeholder="输入消息... (Enter发送，Shift+Enter换行)" rows="1"></textarea>
    <div class="input-actions">
      <button class="btn btn-sm btn-secondary" id="btnAutoReplyToggle" onclick="toggleAutoReply()">自动回复</button>
      <button class="btn btn-sm btn-primary" id="btnManualSend" onclick="sendManualMessage()">发送</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: 添加快捷回复 CSS 样式**

在 `<style>` 标签中添加：

```css
.quick-replies {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.input-wrapper textarea {
  flex: 1;
  border: 1px solid var(--border);
  padding: 10px 12px;
  font-size: 14px;
  resize: none;
  outline: none;
  min-height: 40px;
  max-height: 120px;
  font-family: var(--font);
  border-radius: 8px;
  transition: border-color .2s;
  line-height: 1.5;
}
.input-wrapper textarea:focus {
  border-color: var(--accent);
}
.input-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
```

- [ ] **Step 3: 添加快捷回复 JavaScript 逻辑**

在 `<script>` 标签中添加：

```javascript
// 快捷回复模板
const QUICK_TEMPLATES = {
  greeting: '您好！我对这个岗位很感兴趣，想了解一下具体情况。',
  interest: '非常感谢您的回复！我对这个机会很感兴趣，希望能进一步沟通。',
  wechat: '方便加个微信吗？我的微信号是：[您的微信号]',
  thanks: '非常感谢您的时间和信息！'
};

function insertTemplate(type) {
  const input = document.getElementById('chatInput');
  input.value = QUICK_TEMPLATES[type] || '';
  input.focus();
  autoResizeTextarea(input);
}

// 输入框自适应高度
function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// 绑定输入框事件
document.addEventListener('DOMContentLoaded', function() {
  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.addEventListener('input', function() {
      autoResizeTextarea(this);
    });
  }
});
```

- [ ] **Step 4: 修改 sendManualMessage 函数**

找到 `function sendManualMessage()` 函数，修改 Enter 键处理：

```javascript
// 在 chatInput 的 onkeydown 中添加：
// onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendManualMessage();}"
```

- [ ] **Step 5: 测试快捷回复功能**

1. 打开聊天界面，选择一个会话
2. 点击"问候"按钮，验证输入框是否填入模板内容
3. 点击"表达兴趣"、"要微信"、"感谢"按钮
4. 测试 Enter 发送和 Shift+Enter 换行
5. 验证输入框是否自适应高度

- [ ] **Step 6: 提交代码**

```bash
git add static/dashboard.html
git commit -m "feat(chat): add quick reply templates and textarea auto-resize"
```

---

## Task 4: 自动回复状态显示优化

**Files:**
- Modify: `static/dashboard.html` (CSS 样式)
- Modify: `static/dashboard.html` (JavaScript 逻辑)

- [ ] **Step 1: 添加自动回复状态 CSS 样式**

在 `<style>` 标签中添加：

```css
.auto-reply-on {
  background: var(--green) !important;
  color: #fff !important;
  border-color: var(--green) !important;
}
.auto-reply-off {
  background: var(--surface) !important;
  color: var(--text-3) !important;
}
```

- [ ] **Step 2: 修改 selectConversation 函数**

找到 `function selectConversation(id)` 函数，修改自动回复按钮显示逻辑：

```javascript
function selectConversation(id) {
  activeConvId = id;
  loadConversations();
  loadMessages(id);

  let conv = conversations.find(c => c.id === id);
  if (!conv) return;

  const autoReplyBtnClass = conv.auto_reply_enabled ? 'btn btn-sm auto-reply-on' : 'btn btn-sm auto-reply-off';
  const autoReplyText = conv.auto_reply_enabled ? '🤖 AI回复中' : '⏸ 暂停AI回复';

  document.getElementById('chatHeader').innerHTML =
    '<div class="info">'
    + '<span class="name">' + esc(conv.hr_name || '未知') + '</span><br>'
    + '<span class="company">' + esc(conv.hr_company || '') + ' · ' + esc((conv.job_title || '').slice(0, 20)) + '</span>'
    + '</div>'
    + '<div style="display:flex;gap:6px;">'
    + '<button class="' + autoReplyBtnClass + '" id="btnAutoReplyToggle" onclick="toggleAutoReply()">' + autoReplyText + '</button>'
    + '<button class="btn btn-sm btn-primary" id="btnManualSend" onclick="sendManualMessage()">发送</button>'
    + '</div>';

  document.getElementById('btnManualSend').disabled = false;
  document.getElementById('btnAutoReplyToggle').disabled = false;
  syncConversation(id);
}
```

- [ ] **Step 3: 修改 toggleAutoReply 函数**

找到 `function toggleAutoReply()` 函数，添加 Toast 提示：

```javascript
function toggleAutoReply() {
  if (!activeConvId) return;
  let conv = conversations.find(c => c.id === activeConvId);
  if (!conv) return;

  const newState = !conv.auto_reply_enabled;
  fetch('/api/conversations/' + activeConvId + '/auto-reply', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({enabled: newState})
  })
  .then(r => r.json())
  .then(() => {
    loadConversations().then(() => selectConversation(activeConvId));
    showToast(newState ? '自动回复已开启' : '自动回复已暂停');
  });
}

// Toast 提示
function showToast(message) {
  const existing = document.querySelector('.toast-message');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'toast-message';
  toast.textContent = message;
  toast.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:var(--text);color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;z-index:9999;animation:fadeInUp .3s;';
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}
```

- [ ] **Step 4: 添加 Toast 动画 CSS**

在 `<style>` 标签中添加：

```css
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translate(-50%, 10px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}
```

- [ ] **Step 5: 测试自动回复状态显示**

1. 打开聊天界面，选择一个会话
2. 验证自动回复按钮状态是否正确显示
3. 点击切换自动回复状态
4. 验证 Toast 提示是否显示
5. 验证按钮样式是否随状态变化

- [ ] **Step 6: 提交代码**

```bash
git add static/dashboard.html
git commit -m "feat(chat): improve auto-reply status display and toast notifications"
```

---

## Task 5: 整体测试与优化

**Files:**
- Modify: `static/dashboard.html` (可能的样式调整)

- [ ] **Step 1: 测试完整聊天流程**

1. 启动服务：`python boss_app.py`
2. 打开浏览器访问 `http://127.0.0.1:8010`
3. 切换到"聊天"标签页
4. 测试会话搜索：输入 HR 名称、公司名称
5. 测试状态筛选：点击"全部"、"活跃"、"已暂停"
6. 选择一个会话，查看消息时间分组
7. 测试快捷回复模板
8. 测试自动回复切换
9. 发送消息并验证显示

- [ ] **Step 2: 检查响应式布局**

1. 调整浏览器窗口大小
2. 验证会话列表和消息区域是否正确响应
3. 验证快捷回复按钮是否自动换行
4. 验证输入框是否自适应

- [ ] **Step 3: 性能优化检查**

1. 测试大量会话时的搜索性能
2. 测试长消息列表的滚动流畅度
3. 验证没有内存泄漏（长时间使用后）

- [ ] **Step 4: 最终提交**

```bash
git add static/dashboard.html
git commit -m "feat(chat): complete chat UX optimization with search, date groups, quick replies, and auto-reply status"
```

---

## 验证清单

- [ ] 会话搜索功能正常工作
- [ ] 状态筛选功能正常工作
- [ ] 未读会话置顶显示
- [ ] 消息按日期正确分组
- [ ] 消息状态正确显示
- [ ] 链接可点击
- [ ] 快捷回复模板正常插入
- [ ] 输入框自适应高度
- [ ] 自动回复状态正确显示
- [ ] Toast 提示正常显示
- [ ] 响应式布局正常
- [ ] 性能良好，无卡顿
