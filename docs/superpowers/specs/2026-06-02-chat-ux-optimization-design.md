# 聊天消息界面用户体验优化设计文档

## 概述

本设计文档针对 BOSS 直聘自动化控制台的聊天消息界面进行用户体验优化，采用增量增强方案，保持现有单文件架构，通过改进 CSS/JS 实现功能增强。

**优化范围**：
- 会话列表优化
- 消息展示优化
- 输入与自动回复优化

**设计原则**：
- 保持现有功能稳定
- 渐进式增强，不影响现有工作流
- 代码简洁，易于维护

---

## 第一部分：会话列表优化

### 当前状态

- 简单列表展示：HR 名称、最后消息预览、未读数
- 无搜索筛选功能
- 无会话分类
- 未读提示不明显

### 优化目标

1. **搜索筛选**：支持按 HR 名称、公司、岗位搜索
2. **会话分类**：活跃/已暂停/已完成三个标签页
3. **未读置顶**：未读会话自动置顶，未读数更醒目
4. **快捷操作**：右键菜单支持置顶、归档、删除等

### 具体实现

#### HTML 结构

```html
<div class="chat-list">
  <div class="chat-list-header">
    <input type="text" placeholder="搜索会话..." class="chat-search">
    <div class="chat-tabs">
      <span class="active">全部</span>
      <span>活跃</span>
      <span>已暂停</span>
    </div>
  </div>
  <div class="chat-list-items" id="conversationList">
    <!-- 会话列表 -->
  </div>
</div>
```

#### CSS 样式

```css
.chat-list-header {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}
.chat-search {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  margin-bottom: 8px;
}
.chat-tabs {
  display: flex;
  gap: 8px;
  font-size: 12px;
}
.chat-tabs span {
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
}
.chat-tabs span.active {
  background: var(--accent);
  color: white;
}
```

#### JavaScript 逻辑

```javascript
// 会话搜索
function filterConversations(keyword) {
  const filtered = conversations.filter(c => 
    c.hr_name?.includes(keyword) || 
    c.hr_company?.includes(keyword) ||
    c.job_title?.includes(keyword)
  );
  renderConversationList(filtered);
}

// 会话分类
function filterByStatus(status) {
  const filtered = status === 'all' 
    ? conversations 
    : conversations.filter(c => c.status === status);
  renderConversationList(filtered);
}

// 未读置顶
function sortConversations() {
  return [...conversations].sort((a, b) => {
    if (a.unread_count > 0 && b.unread_count === 0) return -1;
    if (a.unread_count === 0 && b.unread_count > 0) return 1;
    return new Date(b.last_message_at) - new Date(a.last_message_at);
  });
}
```

---

## 第二部分：消息展示优化

### 当前状态

- 基本气泡布局
- 简单的发送者标签
- 无时间分组
- 无消息状态标识

### 优化目标

1. **时间分组**：按日期分组显示消息，添加时间戳
2. **消息状态**：显示已读/未读/送达/发送失败状态
3. **富文本支持**：支持链接识别、换行显示
4. **滚动优化**：自动滚动到底部，新消息提示

### 具体实现

#### HTML 结构

```html
<div class="chat-messages" id="chatMessages">
  <div class="msg-date-group">
    <div class="msg-date-label">今天</div>
    <div class="msg-bubble msg-hr">
      <div class="msg-label">HR</div>
      <div class="msg-content">消息内容</div>
      <div class="msg-meta">
        <span class="msg-time">14:30</span>
        <span class="msg-status">已读</span>
      </div>
    </div>
  </div>
</div>
```

#### CSS 样式

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
}
.msg-date-label::before,
.msg-date-label::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 30%;
  height: 1px;
  background: var(--border);
}
.msg-date-label::before { left: 0; }
.msg-date-label::after { right: 0; }

.msg-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  margin-bottom: 8px;
  position: relative;
}
.msg-hr {
  background: var(--sidebar-bg);
  align-self: flex-start;
  border-bottom-left-radius: 4px;
}
.msg-me {
  background: var(--accent);
  color: white;
  align-self: flex-end;
  border-bottom-right-radius: 4px;
}
.msg-meta {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  font-size: 11px;
  color: var(--text-3);
  margin-top: 4px;
}
.msg-status {
  color: var(--green);
}
.msg-status.failed {
  color: var(--red);
}
```

#### JavaScript 逻辑

```javascript
// 按日期分组
function groupMessagesByDate(messages) {
  const groups = {};
  messages.forEach(m => {
    const date = new Date(m.created_at).toLocaleDateString('zh-CN');
    if (!groups[date]) groups[date] = [];
    groups[date].push(m);
  });
  return groups;
}

// 渲染消息
function renderMessages(msgs) {
  const pane = document.getElementById('chatMessages');
  const groups = groupMessagesByDate(msgs);
  
  let html = '';
  Object.entries(groups).forEach(([date, messages]) => {
    html += `<div class="msg-date-group">
      <div class="msg-date-label">${date}</div>
      ${messages.map(m => renderMessageBubble(m)).join('')}
    </div>`;
  });
  
  pane.innerHTML = html;
  scrollToBottom();
}

// 渲染单条消息
function renderMessageBubble(m) {
  const cls = m.sender === 'me' ? 'msg-me' : 'msg-hr';
  const label = m.sender === 'hr' ? 'HR' : '我' + (m.ai_generated ? ' AI代发' : '');
  const time = new Date(m.created_at).toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
  const status = m.delivery_status || 'sent';
  const statusText = {
    'sent': '已发送',
    'delivered': '已送达',
    'read': '已读',
    'failed': '发送失败'
  }[status] || '已发送';
  
  return `<div class="msg-bubble ${cls}">
    <div class="msg-label">${label}</div>
    <div class="msg-content">${formatContent(m.content)}</div>
    <div class="msg-meta">
      <span class="msg-time">${time}</span>
      <span class="msg-status ${status === 'failed' ? 'failed' : ''}">${statusText}</span>
    </div>
  </div>`;
}

// 内容格式化（链接识别、换行）
function formatContent(content) {
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>')
    .replace(/\n/g, '<br>');
}

// 滚动到底部
function scrollToBottom() {
  const pane = document.getElementById('chatMessages');
  pane.scrollTop = pane.scrollHeight;
}
```

---

## 第三部分：输入与自动回复优化

### 当前状态

- 简单的文本输入框
- 基本的自动回复开关
- 无快捷回复模板
- 无输入状态提示

### 优化目标

1. **快捷回复模板**：预设常用回复模板，一键插入
2. **自动回复配置**：改进配置界面，支持自定义规则
3. **输入体验**：支持多行输入、快捷键、输入状态提示
4. **历史记录**：显示最近发送的消息，支持快速重发

### 具体实现

#### HTML 结构

```html
<div class="chat-input-area">
  <div class="quick-replies">
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('greeting')">问候</button>
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('interest')">表达兴趣</button>
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('wechat')">要微信</button>
    <button class="btn btn-xs btn-secondary" onclick="insertTemplate('thanks')">感谢</button>
  </div>
  <div class="input-wrapper">
    <textarea id="chatInput" placeholder="输入消息... (Enter发送，Shift+Enter换行)" rows="1"></textarea>
    <div class="input-actions">
      <button class="btn btn-sm btn-secondary" onclick="toggleAutoReply()">
        <span id="autoReplyIcon">🤖</span> 自动回复
      </button>
      <button class="btn btn-sm btn-primary" id="btnManualSend" onclick="sendManualMessage()">发送</button>
    </div>
  </div>
  <div class="recent-messages" id="recentMessages">
    <!-- 最近发送的消息 -->
  </div>
</div>
```

#### CSS 样式

```css
.chat-input-area {
  padding: 12px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}
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
}
.input-wrapper textarea:focus {
  border-color: var(--accent);
}
.input-actions {
  display: flex;
  gap: 6px;
}
.recent-messages {
  margin-top: 8px;
  max-height: 100px;
  overflow-y: auto;
}
.recent-msg-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  font-size: 12px;
  color: var(--text-3);
  cursor: pointer;
  border-radius: 4px;
}
.recent-msg-item:hover {
  background: var(--hover);
}
.recent-msg-item .msg-preview {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recent-msg-item .msg-time {
  font-size: 11px;
  margin-left: 8px;
}
```

#### JavaScript 逻辑

```javascript
// 快捷回复模板
const TEMPLATES = {
  greeting: '您好！我对这个岗位很感兴趣，想了解一下具体情况。',
  interest: '非常感谢您的回复！我对这个机会很感兴趣，希望能进一步沟通。',
  wechat: '方便加个微信吗？我的微信号是：[您的微信号]',
  thanks: '非常感谢您的时间和信息！'
};

function insertTemplate(type) {
  const input = document.getElementById('chatInput');
  input.value = TEMPLATES[type] || '';
  input.focus();
}

// 改进的自动回复切换
function toggleAutoReply() {
  if (!activeConvId) return;
  const conv = conversations.find(c => c.id === activeConvId);
  if (!conv) return;
  
  const newState = !conv.auto_reply_enabled;
  fetch(`/api/conversations/${activeConvId}/auto-reply`, {
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

// 显示提示
function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}

// 最近消息记录
const recentMessages = [];
function addRecentMessage(content) {
  recentMessages.unshift({
    content,
    time: new Date()
  });
  if (recentMessages.length > 5) recentMessages.pop();
  renderRecentMessages();
}

function renderRecentMessages() {
  const el = document.getElementById('recentMessages');
  if (!recentMessages.length) {
    el.innerHTML = '';
    return;
  }
  
  el.innerHTML = recentMessages.map(m => `
    <div class="recent-msg-item" onclick="insertRecentMessage('${m.content.replace(/'/g, "\\'")}')">
      <span class="msg-preview">${m.content}</span>
      <span class="msg-time">${m.time.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'})}</span>
    </div>
  `).join('');
}

function insertRecentMessage(content) {
  const input = document.getElementById('chatInput');
  input.value = content;
  input.focus();
}

// 改进的发送消息
function sendManualMessage() {
  if (!activeConvId) return;
  const input = document.getElementById('chatInput');
  const content = input.value.trim();
  if (!content) return;
  
  input.value = '';
  input.disabled = true;
  const btn = document.getElementById('btnManualSend');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '发送中...';
  }
  
  fetch(`/api/conversations/${activeConvId}/send`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content})
  })
  .then(r => r.json())
  .then(() => {
    loadMessages(activeConvId);
    loadConversations();
    addRecentMessage(content);
  })
  .catch(e => {
    showToast('发送失败: ' + (e.message || '网络错误'));
  })
  .finally(() => {
    input.disabled = false;
    input.focus();
    if (btn) {
      btn.disabled = false;
      btn.textContent = '发送';
    }
  });
}

// 输入框自适应高度
document.getElementById('chatInput').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
```

---

## 实施计划

### 阶段一：会话列表优化

1. 添加搜索筛选 UI
2. 实现会话分类标签页
3. 实现未读置顶排序
4. 测试搜索和筛选功能

### 阶段二：消息展示优化

1. 添加时间分组显示
2. 实现消息状态标识
3. 改进消息气泡样式
4. 实现自动滚动和新消息提示

### 阶段三：输入与自动回复优化

1. 添加快捷回复模板面板
2. 改进自动回复切换 UI
3. 实现最近消息记录
4. 实现输入框自适应高度

### 阶段四：测试与优化

1. 功能测试
2. 性能优化
3. 用户反馈收集
4. 细节调整

---

## 验证标准

1. **会话列表**：搜索响应时间 < 100ms，筛选准确率 100%
2. **消息展示**：时间分组正确，状态显示准确，滚动流畅
3. **输入与自动回复**：模板插入正确，自动回复切换正常，历史记录准确
4. **整体体验**：界面响应流畅，无卡顿，操作符合直觉

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 样式冲突 | 中 | 使用 BEM 命名规范，避免全局样式污染 |
| 性能问题 | 低 | 虚拟滚动优化长列表，防抖处理搜索输入 |
| 兼容性问题 | 低 | 使用标准 CSS/JS，避免实验性特性 |
| 数据一致性 | 中 | 实时同步会话状态，WebSocket 推送更新 |
