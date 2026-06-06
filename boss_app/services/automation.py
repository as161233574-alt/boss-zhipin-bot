"""
BossAutomation — 继承 BossScraper，增加点击/输入/聊天等交互能力。
服务层 (Service Layer) — 从 boss_automation.py 提取。
"""

import asyncio
import json
import random
import re
import time
from typing import Optional, List

from playwright.async_api import Locator

from .scraper import BossScraper, async_pause, decode_salary, STATE_FILE


def _keywords_match(job_title: str, job_desc: str, search_keywords: str) -> bool:
    """检查岗位是否匹配搜索关键词。过滤通用词，支持子串拆分匹配。"""
    if not search_keywords or not search_keywords.strip():
        return True

    title_lower = (job_title or "").lower()
    desc_lower = (job_desc or "").lower()
    combined = title_lower + " " + desc_lower

    raw_keywords = [k.strip().lower() for k in re.split(r'[,，、\s]+', search_keywords) if k.strip()]
    generic_words = {"实习", "实习生", "岗位", "招聘", "工程师", "开发", "应届", "兼职", "全职"}
    core_keywords = [k for k in raw_keywords if len(k) >= 2 and k not in generic_words]

    if not core_keywords:
        return True

    for kw in core_keywords:
        if kw in combined:
            return True

    # 拆分长关键词为子串再匹配
    for kw in core_keywords:
        if len(kw) >= 4:
            parts = re.findall(r'[a-z]+', kw)
            cleaned = re.sub(r'实习|生|岗位|招聘|应届|兼职|全职', '', kw)
            cn_parts = re.findall(r'[一-鿿]{2,}', cleaned)
            parts.extend(cn_parts)
            for part in parts:
                if len(part) >= 2 and part not in generic_words and part in combined:
                    return True

    return False


def check_job_match(job_data: dict) -> tuple[bool, str]:
    """检查岗位是否匹配用户的期望条件。

    返回 (is_match, reason)
    """
    from ..models.settings import get_setting

    # 获取用户设置（带容错）
    try:
        exp_min = int(get_setting("experience_min", "0"))
    except (ValueError, TypeError):
        exp_min = 0
    try:
        exp_max = int(get_setting("experience_max", "3"))
    except (ValueError, TypeError):
        exp_max = 3
    try:
        salary_min = float(get_setting("salary_min", "0") or "0")
    except (ValueError, TypeError):
        salary_min = 0
    try:
        salary_max = float(get_setting("salary_max", "999") or "999")
    except (ValueError, TypeError):
        salary_max = 999
    salary_unit = get_setting("salary_unit", "K")

    # 检查岗位标题是否包含关键词（可选过滤）
    search_keywords = get_setting("search_keywords", "")
    if search_keywords:
        job_title = job_data.get("title", "") or job_data.get("job_title", "")
        job_desc = (job_data.get("description") or "")[:500]
        if not _keywords_match(job_title, job_desc, search_keywords):
            return False, "关键词不匹配: 岗位标题不含搜索关键词"

    # 检查经验要求
    experience = job_data.get("experience", "")
    if experience:
        # 解析经验要求，如"1-3年"、"应届生"、"经验不限"
        exp_match = re.search(r"(\d+)\s*[-~]\s*(\d+)\s*年", experience)
        if exp_match:
            job_exp_min = int(exp_match.group(1))
            job_exp_max = int(exp_match.group(2))
            # 用户经验范围与岗位要求不匹配
            if exp_max < job_exp_min or exp_min > job_exp_max:
                return False, f"经验不匹配: 岗位要求{experience}, 用户期望{exp_min}-{exp_max}年"
        elif "应届" in experience or "经验不限" in experience:
            pass  # 应届生可以投递
        elif "年以上" in experience:
            exp_year_match = re.search(r"(\d+)\s*年以上", experience)
            if exp_year_match:
                job_exp_min = int(exp_year_match.group(1))
                if exp_max < job_exp_min:
                    return False, f"经验不匹配: 岗位要求{experience}, 用户期望{exp_min}-{exp_max}年"

    # 检查薪资范围
    salary = job_data.get("salary", "")
    if salary:
        salary_decoded = decode_salary(salary)
        # 解析薪资，如"15-25K"、"200-300元/天"
        salary_match = re.search(r"(\d+)\s*[-~]\s*(\d+)\s*([Kk]|元/天|元/月)?", salary_decoded)
        if salary_match:
            job_salary_min = float(salary_match.group(1))
            job_salary_max = float(salary_match.group(2))
            job_unit = salary_match.group(3) or "K"

            # 统一单位比较
            if job_unit == "K" and salary_unit == "K":
                if job_salary_min > salary_max or job_salary_max < salary_min:
                    return False, f"薪资不匹配: 岗位{salary}, 用户期望{salary_min}-{salary_max}{salary_unit}"
            elif job_unit == "元/天" and salary_unit == "元/天":
                if job_salary_min > salary_max or job_salary_max < salary_min:
                    return False, f"薪资不匹配: 岗位{salary}, 用户期望{salary_min}-{salary_max}{salary_unit}"
            else:
                # 单位不同，需要转换
                # K/月 -> 元/天: K * 1000 / 21.75
                # 元/天 -> K/月: 元 * 21.75 / 1000
                if job_unit == "K" and salary_unit == "元/天":
                    job_min_daily = job_salary_min * 1000 / 21.75
                    job_max_daily = job_salary_max * 1000 / 21.75
                    if job_min_daily > salary_max or job_max_daily < salary_min:
                        return False, f"薪资不匹配: 岗位{salary}, 用户期望{salary_min}-{salary_max}{salary_unit}"
                elif job_unit == "元/天" and salary_unit == "K":
                    job_min_monthly = job_salary_min * 21.75 / 1000
                    job_max_monthly = job_salary_max * 21.75 / 1000
                    if job_min_monthly > salary_max or job_max_monthly < salary_min:
                        return False, f"薪资不匹配: 岗位{salary}, 用户期望{salary_min}-{salary_max}{salary_unit}"

    return True, "匹配"
from ..core.database import init_db, get_db
from ..models.application import (
    add_application,
    get_application_by_url,
    update_application_status,
    get_today_application_count,
    get_application,
)
from ..models.conversation import (
    get_or_create_conversation,
    get_conversation,
    list_active_conversations,
    find_conversation_by_hr_name,
    update_conversation_last_message,
    update_conversation_status,
    update_conversation_interest,
    update_conversation_wechat,
    mark_resume_sent,
    mark_phone_shared,
)
from ..models.message import (
    add_message,
    get_messages,
    get_recent_messages,
    replace_conversation_messages,
    message_exists,
)
from ..models.settings import (
    get_setting,
    increment_daily_stat,
    get_today_auto_reply_count,
    get_daily_stats,
)

# ── 选择器配置（BOSS UI 改版时只改这里，也可通过设置表覆盖）──
SELECTORS = {
    "apply_button": [
        'button:has-text("立即沟通")',
        'a:has-text("立即沟通")',
        'button:has-text("立即投递")',
        'a:has-text("立即投递")',
        'button:has-text("投递简历")',
        'a:has-text("投递简历")',
        '[class*="btn-chat"]',
        '[class*="start-chat"]',
        '[class*="btn-start"]',
        'span:has-text("立即沟通")',
        'div:has-text("立即沟通")',
    ],
    "chat_input": [
        "#chat-input",
        'div[contenteditable="true"]',
        '[class*="chat-input"]',
        '[placeholder*="请输入"]',
    ],
    "chat_send_button": [
        'button[type="send"]',
        ".btn-send",
        'button:has-text("发送")',
        'button[class*="send"]',
    ],
    "conversation_items": [
        'li[role="listitem"]',
        ".friend-content",
        '[class*="chat-item"]',
    ],
    "message_items_in_chat": [
        "li.message-item",
        'li[class*="message-item"]',
        '[class*="message-item"]',
    ],
    "unread_badge": [
        '[class*="unread"]',
        '[class*="badge"]',
        ".red-dot",
    ],
    "greeting_dialog_close": [
        'button[class*="close"]',
        '[class*="dialog-close"]',
        'span:has-text("×")',
        '[class*="modal-close"]',
        'svg[class*="close"]',
    ],
    "resume_attach_btn": [
        'div.toolbar-btn:has-text("发简历")',
        'div:has-text("发简历")',
        'button:has-text("发简历")',
        'span:has-text("发简历")',
    ],
    "resume_confirm_btn": [
        ".btn-sure-v2.btn-confirm",
        ".choose-resume-dialog .btn-confirm",
        'button:has-text("发送")',
        '.boss-popup__content button:has-text("发送")',
    ],
    "wechat_share_btn": [
        ".btn-weixin",
        'div:has-text("换微信")',
        'span:has-text("换微信")',
        '[class*="btn-weixin"]',
    ],
    "phone_share_btn": [
        ".btn-contact",
        'div:has-text("换电话")',
        'span:has-text("换电话")',
        '[class*="btn-contact"]',
    ],
    "back_to_list": [
        '[class*="back"]',
        'span:has-text("返回")',
        'button:has-text("返回")',
        'a[href*="/chat"]',
    ],
}


def _merge_selectors():
    """合并 settings 表中的选择器覆盖。"""
    try:
        raw = get_setting("selector_overrides", "")
        if raw:
            overrides = json.loads(raw)
            for k, v in overrides.items():
                if k in SELECTORS and isinstance(v, list) and len(v) > 0:
                    SELECTORS[k] = v
    except Exception:
        pass


_merge_selectors()

# ── 绝对上限 ──
MAX_APPLY_PER_DAY = 30
MAX_AUTO_REPLY_PER_DAY = 200


class BossAutomation(BossScraper):
    """在 BossScraper 基础上增加交互能力"""

    def __init__(self, headless=False):
        super().__init__(headless)
        init_db()

    # ══════════════════════════════════════
    #  底层交互 helpers
    # ══════════════════════════════════════

    async def _find_element(self, selector_list: List[str], timeout_ms: int = 5000) -> Optional[Locator]:
        """逐个尝试选择器，返回第一个可见匹配。"""
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            for sel in selector_list:
                try:
                    loc = self.page.locator(sel).first
                    if await loc.is_visible():
                        return loc
                except Exception:
                    continue
            await asyncio.sleep(0.3)
        return None

    async def _find_all_elements(self, selector_list: List[str]) -> List[Locator]:
        """返回所有匹配的可见元素。"""
        for sel in selector_list:
            try:
                locs = self.page.locator(sel)
                count = await locs.count()
                if count > 0:
                    return [locs.nth(i) for i in range(count)]
            except Exception:
                continue
        return []

    async def _human_type(self, locator: Locator, text: str):
        """逐字输入，模拟真人打字。"""
        try:
            await locator.click()
            await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass
        for ch in text:
            await self.page.keyboard.type(ch, delay=random.randint(50, 150))
        await asyncio.sleep(random.uniform(0.3, 0.8))

    async def _safe_click(self, locator: Locator):
        """带随机延迟的点击。"""
        await asyncio.sleep(random.uniform(0.2, 0.6))
        try:
            await locator.hover()
            await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass
        await locator.click()

    async def _dismiss_popups(self):
        """关闭 BOSS 页面常见的弹窗/遮罩。"""
        dismiss_selectors = [
            '.btn-close', '.close-btn', '[class*="close"]',
            'button:has-text("我知道了")', 'button:has-text("关闭")',
            'button:has-text("暂不")', 'button:has-text("取消")',
            '.dialog-close', '.modal-close',
            'span:has-text("×")', '[class*="icon-close"]',
        ]
        for sel in dismiss_selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    await asyncio.sleep(0.3)
            except Exception:
                pass
        # 按 Escape 关闭可能的弹窗
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
        except Exception:
            pass

    async def _has_text(self, *texts: str) -> bool:
        """检查页面是否包含任意关键词。"""
        try:
            body = await self.page.inner_text("body")
            body_lower = body.lower()
            return any(t.lower() in body_lower for t in texts)
        except Exception:
            return False

    # ══════════════════════════════════════
    #  安全检查
    # ══════════════════════════════════════

    async def check_page_safety(self) -> bool:
        """所有自动化操作前检查页面安全状态。"""
        try:
            body = await self.page.inner_text("body")
            body_lower = body.lower()

            if await self._login_prompt_visible():
                print("  ⚠️ 安全检查: 需要重新登录")
                return False
            if any(kw in body_lower[:500] for kw in ["验证", "滑块", "拼图", "captcha", "verify"]):
                print("  ⚠️ 安全检查: 检测到验证码")
                return False
            # 只在弹窗/对话框中检测账号异常关键词，避免误报
            try:
                dialogs = await self.page.locator('[class*="dialog"], [class*="modal"], [class*="popup"], [class*="tip"]').all_inner_texts()
                dialog_text = " ".join(dialogs).lower()
                if any(kw in dialog_text for kw in ["账号异常", "违规", "限制使用", "冻结"]):
                    print("  ⚠️ 安全检查: 账号异常")
                    return False
                if any(kw in dialog_text for kw in ["操作太频繁", "稍后再试", "休息一下"]):
                    print("  ⚠️ 安全检查: 操作频率限制")
                    return False
            except Exception:
                pass
            return True
        except Exception:
            print("  ⚠️ 安全检查: 页面异常，无法检测")
            return False

    # ══════════════════════════════════════
    #  Session 保活 & 心跳
    # ══════════════════════════════════════

    async def check_logged_in(self) -> bool:
        """快速检查当前是否已登录；未知空白页不直接当作过期。"""
        try:
            return await self.is_logged_in_page()
        except Exception:
            return False

    async def heartbeat(self) -> bool:
        """心跳: 只检查当前页面登录状态，不主动跳转。"""
        try:
            return await self.check_logged_in()
        except Exception:
            return False

    async def keep_alive(self):
        """主动保活: 在聊天页保持 BOSS session 活跃。已登录时用轻量操作代替完整刷新。"""
        try:
            current_url = self.page.url
            need_navigate = "/web/geek/chat" not in current_url
            try:
                if need_navigate:
                    await self.page.goto("https://www.zhipin.com/web/geek/chat", wait_until="load", timeout=30000)
                    await async_pause(2, 4)
                else:
                    # 已在聊天页，轻量滚动模拟用户活动，避免频繁 reload 被检测
                    try:
                        await self.page.mouse.move(random.randint(200, 600), random.randint(300, 500))
                        await asyncio.sleep(random.uniform(0.5, 1.0))
                        await self.page.evaluate("window.scrollBy(0, %d)" % random.randint(-100, 100))
                    except Exception:
                        pass
            except Exception:
                pass
            return await self.check_logged_in()
        except Exception:
            return False

    async def _save_state(self):
        """保存当前浏览器状态到文件。"""
        try:
            state = await self._ctx.storage_state()
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
        except Exception:
            pass

    # ══════════════════════════════════════
    #  自动投递
    # ══════════════════════════════════════

    async def apply_to_job(self, job_url: str, greeting: Optional[str] = None, job_data: dict = None) -> dict:
        """
        对单个岗位执行投递流程:
        1. 打开详情页
        2. 点击"立即沟通"
        3. 发送招呼语
        返回 {success, message, application_id}
        """
        # 缓存 DB 查询，避免同一 URL 多次查询
        _cached_app = None
        def _get_app():
            nonlocal _cached_app
            if _cached_app is None:
                _cached_app = get_application_by_url(job_url)
            return _cached_app

        if not job_url:
            return {"success": False, "message": "缺少岗位链接"}

        # 日限检查
        today_count = get_today_application_count()
        daily_limit = int(get_setting("daily_apply_limit", "15"))
        if today_count >= min(daily_limit, MAX_APPLY_PER_DAY):
            return {"success": False, "message": f"已达今日上限({today_count}条)"}

        # 48小时内已投递过的岗位不再重复投递
        existing_app = _get_app()
        if existing_app:
            try:
                from datetime import datetime, timedelta
                # 优先用 greeting_sent_at，其次用 updated_at（status=applied 时）
                ts = existing_app.get("greeting_sent_at") or ""
                if not ts and existing_app.get("status") == "applied":
                    ts = existing_app.get("updated_at") or ""
                if ts:
                    sent_time = datetime.fromisoformat(ts.replace(" ", "T").split("+")[0].split(".")[0])
                    if datetime.now() - sent_time < timedelta(hours=48):
                        return {"success": False, "message": "48小时内已投递过", "skipped": True}
            except Exception:
                pass

        # 经验匹配和薪资匹配检查
        if job_data:
            is_match, reason = check_job_match(job_data)
            if not is_match:
                print(f"  ⏭️ 跳过: {reason}")
                return {"success": False, "message": reason, "skipped": True}

        print(f"  🚀 投递: {job_url[:60]}...")

        try:
            await self.page.goto(job_url, wait_until="load", timeout=45000)
            await async_pause(1, 2)

            if not await self.check_page_safety():
                return {"success": False, "message": "安全检查未通过"}

            # 检查是否已投递
            if await self._has_text("已沟通", "继续沟通"):
                existing = _get_app()
                if existing and existing["status"] == "pending":
                    update_application_status(existing["id"], "applied")
                return {"success": True, "message": "已投递过", "already_applied": True}

            # 关闭可能的弹窗
            await self._dismiss_popups()

            # 等待页面关键元素加载
            try:
                await self.page.wait_for_selector('button, a.btn, [class*="btn"]', timeout=8000)
            except Exception:
                pass

            # 关闭弹窗
            await self._dismiss_popups()

            # 查找投递按钮
            apply_btn = await self._find_element(SELECTORS["apply_button"], timeout_ms=8000)

            if not apply_btn:
                # 尝试多种文本匹配
                for btn_text in ["立即沟通", "立即投递", "投递简历", "发送简历"]:
                    try:
                        loc = self.page.locator(f'text="{btn_text}"').first
                        if await loc.is_visible(timeout=1000):
                            apply_btn = loc
                            break
                    except Exception:
                        continue

            if not apply_btn:
                # 尝试滚动页面后再找
                for scroll_y in [300, 600, 0]:
                    try:
                        await self.page.evaluate(f"window.scrollTo(0, {scroll_y})")
                        await asyncio.sleep(0.5)
                        await self._dismiss_popups()
                        apply_btn = await self._find_element(SELECTORS["apply_button"], timeout_ms=3000)
                        if apply_btn:
                            break
                    except Exception:
                        continue

            if not apply_btn:
                # 最后用 JavaScript 尝试查找
                try:
                    btn_info = await self.page.evaluate("""() => {
                        const btns = document.querySelectorAll('button, a, [role="button"]');
                        for (const b of btns) {
                            const text = (b.textContent || '').trim();
                            if (text.includes('立即沟通') || text.includes('立即投递') || text.includes('投递简历')) {
                                const rect = b.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    return {found: true, text: text, x: rect.x + rect.width/2, y: rect.y + rect.height/2};
                                }
                            }
                        }
                        return {found: false};
                    }""")
                    if btn_info and btn_info.get("found"):
                        await self.page.mouse.click(btn_info["x"], btn_info["y"])
                        apply_btn = True  # 标记已点击
                        await async_pause(2, 3)
                except Exception:
                    pass

            if not apply_btn:
                return {"success": False, "message": "未找到投递按钮"}

            # 用 force=True 绕过可能的遮罩（如果 apply_btn 是 True，说明已通过 JS 点击）
            if apply_btn is not True:
                try:
                    await apply_btn.click(force=True, timeout=10000)
                except Exception:
                    await self._safe_click(apply_btn)
            await async_pause(2, 3)

            # 检查限制消息
            if await self._has_text("已达上限", "沟通人数已用完", "今日次数已用完", "今日沟通次数已用完"):
                return {"success": False, "message": "BOSS直聘今日沟通次数已用完"}

            # 等待聊天窗口加载
            chat_input = await self._find_element(SELECTORS["chat_input"], timeout_ms=5000)

            # 发送招呼语
            if not greeting:
                # 使用智能打招呼生成
                from .replier import generate_smart_greeting
                resume_summary = get_setting("resume_summary", "")
                greeting_text = generate_smart_greeting(
                    job_title=job_data.get("title", "") if job_data else "",
                    company=job_data.get("company", "") if job_data else "",
                    salary=job_data.get("salary", "") if job_data else "",
                    experience=job_data.get("experience", "") if job_data else "",
                    education=job_data.get("education", "") if job_data else "",
                    resume_summary=resume_summary,
                )
            else:
                greeting_text = greeting
            greeting_sent = False
            if chat_input and greeting_text:
                greeting_sent = await self.send_message(greeting_text)
                if greeting_sent:
                    print(f"  ✅ 招呼语已发送")
                else:
                    print(f"  ⚠️ 招呼语发送失败")

            # 记录到 SQLite
            existing = _get_app()
            if existing:
                if greeting_sent:
                    update_application_status(existing["id"], "applied", greeting_text)
                else:
                    update_application_status(existing["id"], "applied")
                app_id = existing["id"]
            else:
                # 从页面提取岗位标题和公司名
                page_title = ""
                page_company = ""
                try:
                    page_info = await self.page.evaluate("""() => {
                        const body = (document.body || {}).innerText || '';
                        const lines = body.split('\\n').map(l => l.trim()).filter(Boolean);
                        let title = '', company = '';
                        // 标题通常在前几行
                        for (let i = 0; i < Math.min(lines.length, 5); i++) {
                            const l = lines[i];
                            if (l.length > 2 && l.length < 40 && !/^\\d|经验|学历|应届/.test(l)) {
                                if (!title) title = l;
                                else if (!company && l.length < 30) { company = l; break; }
                            }
                        }
                        return {title, company};
                    }""")
                    page_title = (page_info.get("title") or "").strip()
                    page_company = (page_info.get("company") or "").strip()
                except Exception:
                    pass
                app_id = add_application({"title": page_title, "company": page_company, "url": job_url})
                if greeting_sent:
                    update_application_status(app_id, "applied", greeting_text)
                else:
                    update_application_status(app_id, "applied")

            # 从详情页提取 HR 真实姓名和岗位信息
            hr_name = ""
            hr_company = ""
            job_title = ""
            try:
                hr_info = await self.page.evaluate("""() => {
                    const body = (document.body || {}).innerText || '';
                    const lines = body.split('\\n').map(l => l.trim()).filter(Boolean);
                    let hrName = '', hrTitle = '';
                    for (let i = 0; i < lines.length; i++) {
                        const l = lines[i];
                        if (l.includes('HR') || l.includes('招聘者') || l.includes('招聘经理') ||
                            l.includes('人事') || l.includes('HRBP') || l.includes('猎头')) {
                            if (i > 0 && lines[i-1].length <= 6 && !/\\d|省|市|区|路|号|招聘|公司|BOSS/.test(lines[i-1])) {
                                hrName = lines[i-1];
                            }
                            hrTitle = l;
                            break;
                        }
                    }
                    return {hrName, hrTitle};
                }""")
                hr_name = (hr_info.get("hrName") or "").strip()
                if not hr_name:
                    hr_name = ""
            except Exception:
                pass

            app_record = _get_app() or {}
            hr_name = hr_name or app_record.get("hr_name", "")
            hr_company = app_record.get("company", "")
            job_title = app_record.get("job_title", "")

            # 只创建有 HR 名字的会话，避免"未知HR"垃圾数据
            if hr_name and len(hr_name) >= 2:
                get_or_create_conversation(app_id, hr_name, hr_company, job_title)

            increment_daily_stat("applications_sent")
            print(f"  ✅ 投递成功")
            return {"success": True, "message": "投递成功", "application_id": app_id}

        except Exception as e:
            print(f"  ❌ 投递失败: {e}")
            return {"success": False, "message": str(e)}

    async def apply_batch(self, job_urls: List[str], greeting_template: Optional[str] = None) -> List[dict]:
        """批量投递，带间隔延迟。可通过设置 batch_delay_sec 控制间隔。"""
        results = []
        min_delay = int(get_setting("batch_delay_min_sec", "30"))
        max_delay = int(get_setting("batch_delay_max_sec", "90"))
        for i, url in enumerate(job_urls):
            if i > 0:
                delay = random.uniform(min_delay, max_delay)
                print(f"  ⏳ 等待 {delay:.0f}s 后投递下一条...")
                await asyncio.sleep(delay)

            # 获取岗位数据用于匹配检查
            job = get_application_by_url(url)
            job_data = None
            if job:
                job_data = {
                    "title": job.get("job_title", ""),
                    "company": job.get("company", ""),
                    "salary": job.get("salary", ""),
                    "experience": job.get("experience", ""),
                    "education": job.get("education", ""),
                }

            result = await self.apply_to_job(url, greeting_template, job_data)
            results.append(result)

            if not result["success"] and "上限" in result.get("message", ""):
                break
        return results

    # ══════════════════════════════════════
    #  聊天监控
    # ══════════════════════════════════════

    async def navigate_to_chat(self) -> bool:
        """导航到 BOSS 聊天页，切到「未读」标签，只显示有未读消息的会话。"""
        try:
            await self.page.goto("https://www.zhipin.com/web/geek/chat", wait_until="load", timeout=45000)
            await async_pause(2, 3)
            # 点击「未读」标签，只显示有未读的会话
            for sel in ['span.label-name:has-text("未读")', 'li:has-text("未读")', '.label-name:has-text("未读")']:
                try:
                    unread_tab = self.page.locator(sel).first
                    if await unread_tab.is_visible():
                        await unread_tab.click()
                        await async_pause(1, 2)
                        break
                except Exception:
                    pass
            return await self.check_page_safety()
        except Exception:
            return False

    async def poll_conversation_list(self) -> List[dict]:
        """从 BOSS 聊天页 DOM 获取会话列表。DOM 失败用 body text 正则兜底。"""
        conversations = []

        # 方式1: DOM 选择器
        conv_els = await self._find_all_elements(SELECTORS["conversation_items"])
        if conv_els:
            for el in conv_els:
                try:
                    text = (await el.inner_text()).strip()
                    if not text or len(text) < 3:
                        continue
                    # 从 BOSS 真实结构提取 HR 名字: .name-text
                    try:
                        hr_name = (await el.locator(".name-text").first.inner_text()).strip()
                    except Exception:
                        hr_name = ""
                    if not hr_name:
                        # 兜底：从 body_text 行中提取
                        hr_name = (
                            await el.evaluate("""(el) => {
                            const lines = (el.innerText||'').split('\\n').map(l=>l.trim()).filter(Boolean);
                            for (const l of lines) {
                                if (/^\\d{1,2}:\\d{2}$/.test(l)) continue;
                                if (/^\\[.+\\]$/.test(l)) continue;
                                const ch = l.replace(/[^\\u4e00-\\u9fff]/g,'');
                                if (ch.length>=2 && ch.length<=5) return l.split(/[\\s|·]/)[0].trim();
                            }
                            return '';
                        }""")
                            or ""
                        )
                    has_unread = False
                    try:
                        badge = el.locator('.red-dot, [class*="unread"]').first
                        has_unread = await badge.is_visible()
                    except Exception:
                        pass
                    conversations.append(
                        {
                            "text": text,
                            "has_unread": has_unread,
                            "element": el,
                            "hr_name": hr_name,
                        }
                    )
                except Exception:
                    continue

        # 方式2: body text 正则兜底
        if not conversations:
            try:
                body = await self.page.inner_text("body")
                pattern = r"(\d{1,2}:\d{2})\s+([一-鿿\w·]+?)\s+(\[\s*\S+\s*\])\s+(.+?)(?=\s*\d{1,2}:\d{2}\s+|没有更多了|\Z)"
                for m in re.findall(pattern, body):
                    time_str, name_block, status, msg = m
                    hr_name = re.sub(
                        r"[一-鿿]{2,}(?:有限|集团|科技|网络|信息|文化|教育|医疗|能源|贸易|实业|发展|控股|投资).*|经理.*|主管.*|专员.*|总监.*|[\[\]].*",
                        "",
                        name_block,
                    ).strip()
                    if not hr_name or len(hr_name) < 2:
                        m2 = re.match(r"^[一-鿿]{2,4}", name_block)
                        hr_name = m2.group(0) if m2 else name_block[:6]
                    hr_name = hr_name.strip()
                    if not hr_name or len(hr_name) < 2:
                        continue
                    conversations.append(
                        {
                            "text": f"{time_str}\n{name_block}\n{status}\n{msg}".strip(),
                            "has_unread": "未读" in status,
                            "element": None,
                            "hr_name": hr_name,
                        }
                    )
            except Exception:
                pass

        return conversations

    async def read_visible_messages(self) -> List[dict]:
        """读取当前右侧聊天窗口中的可见消息，避免把左侧会话列表误当聊天内容。"""
        try:
            raw = await self.page.evaluate("""() => {
                const result = [];
                const vw = window.innerWidth || 1200;
                const visible = el => {
                    const r = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                };
                const clean = text => (text || '')
                    .replace(/^(已读|未读|送达|发送失败|已发送)\\s*/g, '')
                    .replace(/\\n?(已读|未读|送达|发送失败|已发送)$/g, '')
                    .trim();
                const pickStatus = text => {
                    const m = (text || '').match(/(^|\\n)\\s*(已读|未读|送达|发送失败|已发送)\\s*(\\n|$)/);
                    return m ? m[2] : '';
                };
                const push = (el, contentEl) => {
                    if (!visible(el)) return;
                    const r = el.getBoundingClientRect();
                    if (r.left + r.width / 2 < vw * 0.35) return;
                    const textNode = contentEl || el.querySelector('.text p, .text span:last-child, .text, [class*="bubble"], [class*="content"]');
                    const fullText = el.innerText || '';
                    const content = clean(textNode ? textNode.innerText : el.innerText);
                    if (!content || /^(已读|未读|送达|发送失败|已发送)$/.test(content)) return;
                    if (content.length > 1000) return;
                    const cls = el.className || '';
                    const sender = cls.includes('item-myself') || cls.includes('myself') || cls.includes('self') || r.left > vw * 0.52 ? 'me' : 'hr';
                    const status = sender === 'me' ? pickStatus(fullText) : '';
                    result.push({sender: sender, content: content, status: status});
                };

                document.querySelectorAll('li.message-item, li[class*="message-item"]').forEach(el => push(el));
                if (result.length === 0) {
                    document.querySelectorAll('[class*="message"] [class*="bubble"], [class*="msg"] [class*="bubble"], [class*="chat"] [class*="text"]').forEach(el => push(el, el));
                }
                return result;
            }""")
            return raw or []
        except Exception:
            return []

    async def open_conversation_by_name(self, hr_name: str) -> bool:
        """在聊天页中按 HR 名字定位并打开对应会话。"""
        try:
            current_url = self.page.url
            if "/web/geek/chat" not in current_url:
                await self.page.goto("https://www.zhipin.com/web/geek/chat", wait_until="load", timeout=45000)
                await async_pause(2, 3)

            # 优先用 Playwright 文本选择器点击列表项。
            for sel in [
                f'li[role="listitem"]:has-text("{hr_name}")',
                f'.user-list li:has-text("{hr_name}")',
                f'[class*="friend"]:has-text("{hr_name}")',
                f'text="{hr_name}"',
            ]:
                try:
                    loc = self.page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.click(force=True, timeout=3000)
                        await async_pause(1, 2)
                        return True
                except Exception:
                    pass

            # 兜底：在 DOM 中找包含 HR 名的最小可点击会话容器并触发点击。
            clicked = await self.page.evaluate(
                """(name) => {
                    const visible = el => {
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                    };
                    const candidates = [];
                    const selectors = [
                        '.user-list li', 'li[role="listitem"]', '.friend-content',
                        '[class*="friend"]', '[class*="conversation"]', '[class*="chat-item"]'
                    ];
                    document.querySelectorAll(selectors.join(',')).forEach(el => {
                        const text = (el.innerText || '');
                        if (text.length < 3 || text.length > 200) return;
                        if (!text.includes(name)) return;
                        if (!visible(el)) return;
                        const rect = el.getBoundingClientRect();
                        const nameEl = el.querySelector('.name-text, [class*="name"]');
                        const nameText = (nameEl && nameEl.innerText || '').trim();
                        const exact = nameText === name || text.split('\\n').some(line => line.trim() === name);
                        candidates.push({el: el, exact: exact ? 1 : 0, area: rect.width * rect.height, top: rect.top});
                    });
                    candidates.sort((a,b) => b.exact - a.exact || a.area - b.area || a.top - b.top);
                    for (const c of candidates) {
                        try {
                            c.el.scrollIntoView({block: 'center'});
                            const r = c.el.getBoundingClientRect();
                            const opts = {bubbles: true, cancelable: true, view: window, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2};
                            c.el.dispatchEvent(new MouseEvent('mousedown', opts));
                            c.el.dispatchEvent(new MouseEvent('mouseup', opts));
                            c.el.dispatchEvent(new MouseEvent('click', opts));
                            return true;
                        } catch(e) {}
                    }
                    return false;
                }""",
                hr_name,
            )
            if clicked:
                await async_pause(1, 2)
                return True
            return False
        except Exception as e:
            print(f"  ⚠️ 打开会话失败 ({hr_name}): {e}")
            return False

    async def send_message(self, text: str, fast: bool = True) -> bool:
        """逐字模拟键盘输入 + Enter 发送，确保 BOSS 检测到输入事件。"""
        try:
            # 点击输入框激活
            try:
                await self.page.locator("#chat-input").first.click()
                await asyncio.sleep(0.15)
            except Exception:
                try:
                    await self.page.locator('[contenteditable="true"]').first.click()
                    await asyncio.sleep(0.15)
                except Exception:
                    pass

            # 清除已有内容
            try:
                await self.page.keyboard.press("Control+a")
                await asyncio.sleep(0.05)
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(0.05)
            except Exception:
                pass

            # 逐字键入，模拟真人打字
            delay = 20 if fast else 40
            await self.page.keyboard.type(text, delay=delay)
            await async_pause(0.3, 0.6)

            # 按 Enter 发送
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(random.uniform(0.5, 1))

            # 验证：在右侧聊天消息区域（不是整个页面）查找刚发的消息
            # 使用 read_visible_messages 读取最新消息，检查是否包含刚发送的内容
            messages = await self.read_visible_messages()
            if messages:
                last_msg = messages[-1]
                # 检查最后一条消息是否是我们发的，且内容匹配
                check_text = text[:20] if len(text) >= 20 else text
                if last_msg.get("sender") == "me" and check_text in last_msg.get("content", ""):
                    return True

            # 再试一次 Enter + 二次验证
            try:
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(random.uniform(0.5, 1))
                messages2 = await self.read_visible_messages()
                if messages2:
                    last_msg2 = messages2[-1]
                    check_text = text[:20] if len(text) >= 20 else text
                    if last_msg2.get("sender") == "me" and check_text in last_msg2.get("content", ""):
                        return True
            except Exception:
                pass

            return False
        except Exception as e:
            print(f"  ⚠️ send_message 失败: {e}")
            return False

    async def _get_chat_security_id(self, hr_name: str = "") -> str:
        """从 BOSS API 或页面提取对方 securityId。"""
        for attempt in range(3):  # 重试3次
            try:
                # 方式1: 页面 HTML 正则搜
                html = await self.page.content()
                m = re.search(r'securityId["\']?\s*[:=]\s*["\']([A-Za-z0-9_~+/=-]{30,})["\']', html)
                if m:
                    return m.group(1)

                # 方式2: JS 全局对象
                sid = await self.page.evaluate("""() => {
                    for (const key of Object.keys(window)) {
                        try {
                            const v = window[key];
                            if (!v || typeof v !== 'object') continue;
                            if (v.securityId) return v.securityId;
                        } catch(e) {}
                    }
                    return '';
                }""")
                if sid:
                    return sid

                # 方式3: BOSS API 获取会话列表, 按 HR 名匹配
                encrypt_id = ""
                try:
                    encrypt_id = await self.page.evaluate("""() => {
                        for (const key of Object.keys(window)) {
                            try { if (window[key] && window[key].encryptSystemId) return window[key].encryptSystemId; } catch(e) {}
                        }
                        return '';
                    }""")
                except Exception:
                    pass

                if encrypt_id and hr_name:
                    url = f"https://www.zhipin.com/wapi/zprelation/friend/geekFilterByLabel?labelId=0&encryptSystemId={encrypt_id}"
                    data = await self.page.evaluate(
                        """async (url) => {
                        const r = await fetch(url, {headers:{'Accept':'application/json','x-requested-with':'XMLHttpRequest'}, credentials:'include'});
                        return await r.json();
                    }""",
                        url,
                    )
                    friends = (data or {}).get("zpData", {}).get("friends", [])
                    for f in friends:
                        fn = (f.get("bossName") or f.get("realName") or "").strip()
                        if fn == hr_name:
                            return f.get("securityId", "")

                if attempt < 2:
                    print(f"  [securityId] 第{attempt + 1}次获取失败，重试...")
                    await async_pause(1, 2)

            except Exception as e:
                print(f"  [securityId] 获取异常: {e}")
                if attempt < 2:
                    await async_pause(1, 2)

        print(f"  ⚠️ securityId 获取失败（3次重试），HR: {hr_name}")
        return ""

    async def _exchange_contact(self, hr_name: str, exchange_type: int, selector_key: str, label: str) -> bool:
        """通过 BOSS API 交换联系方式（微信 type=2 / 电话 type=1），等弹窗后点「确定」。"""
        try:
            sid = await self._get_chat_security_id(hr_name)

            if sid:
                await self.page.evaluate(
                    """
                    async (args) => {
                        await fetch('https://www.zhipin.com/wapi/zpchat/exchange/test', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded', 'x-requested-with': 'XMLHttpRequest'},
                            body: 'securityId=' + encodeURIComponent(args.sid) + '&type=' + args.type + '&friendSource=0',
                            credentials: 'include',
                        });
                    }
                    """,
                    {"sid": sid, "type": exchange_type},
                )
                print(f"  [换{label}] API /exchange/test (type={exchange_type}) 已调用")
            else:
                btn = await self._find_element(SELECTORS[selector_key], timeout_ms=5000)
                if not btn:
                    print(f"  ⚠️ send_{label}: 无法获取 securityId 且未找到按钮")
                    return False
                await btn.click()
                print(f"  [换{label}] 已点击换{label}按钮")

            confirm_clicked = await self.page.evaluate("""() => {
                return new Promise((resolve) => {
                    let tries = 0;
                    const check = () => {
                        const btns = document.querySelectorAll('span');
                        for (const b of btns) {
                            if (b.innerText.trim() === '确定' && b.offsetParent !== null) {
                                const parent = b.closest('.secure-exchange, .sentence-popover, .panel-contact, [class*="exchange"], [class*="popover"]');
                                if (parent) {
                                    b.click();
                                    resolve(true);
                                    return;
                                }
                            }
                        }
                        const all = document.querySelectorAll('.btn-sure-v2, span');
                        for (const el of all) {
                            if (el.innerText.trim() === '确定' && el.offsetParent !== null && !el.closest('.btn-outline-v2')) {
                                el.click();
                                resolve(true);
                                return;
                            }
                        }
                        if (++tries < 30) setTimeout(check, 300);
                        else resolve(false);
                    };
                    check();
                });
            }""")
            if confirm_clicked:
                await asyncio.sleep(random.uniform(0.5, 1))
                print(f"  [换{label}] 已点确定按钮")
                return True

            print(f"  [换{label}] 超时: 未找到确定按钮")
            return False

        except Exception as e:
            print(f"  ⚠️ send_{label} 失败: {e}")
            return False

    async def send_wechat(self, hr_name: str = "") -> bool:
        """通过 BOSS API 发起微信交换。"""
        return await self._exchange_contact(hr_name, 2, "wechat_share_btn", "微信")

    async def send_phone(self, hr_name: str = "") -> bool:
        """通过 BOSS API 交换手机号。"""
        return await self._exchange_contact(hr_name, 1, "phone_share_btn", "电话")

    async def send_resume(self) -> bool:
        """点击「发简历」按钮，等弹窗后点「发送」确认。"""
        try:
            btn = await self._find_element(SELECTORS["resume_attach_btn"], timeout_ms=5000)
            if not btn:
                print("  ⚠️ send_resume: 未找到发简历按钮")
                return False
            await btn.click()
            print("  [发简历] 已点击发简历按钮")
            await async_pause(1, 2)

            # 等弹窗出现 → 点「发送」按钮
            confirm = await self._find_element(SELECTORS["resume_confirm_btn"], timeout_ms=5000)
            if confirm:
                await confirm.click()
                await asyncio.sleep(random.uniform(0.5, 1))
                print("  [发简历] 已点发送按钮")
                return True

            # 兜底：无弹窗但已点击
            print("  [发简历] 无弹窗，直接完成")
            return True
        except Exception as e:
            print(f"  ⚠️ send_resume 失败: {e}")
            return False

    # ══════════════════════════════════════
    #  页面扫描 & 一键投递
    # ══════════════════════════════════════

    async def scan_current_page(self) -> List[dict]:
        """扫描当前BOSS搜索结果页，提取所有可见岗位卡片。不跳转，只读当前页。"""
        print(f"  [扫描] 开始扫描当前页面...")
        await self._scroll_all()
        jobs = await self._extract_job_cards()
        if not jobs:
            body_text = await self.page.inner_text("body")
            lines = [l.strip() for l in body_text.split("\n") if l.strip()]
            sal_idx = [i for i, l in enumerate(lines) if re.search(r"\d+[-~]\d+K", decode_salary(l), re.I)]
            for n, si in enumerate(sal_idx):
                if n > 0 and si - sal_idx[n - 1] < 3:
                    continue
                if si == 0:
                    continue
                title = lines[si - 1]
                if not (2 < len(title) < 60):
                    continue
                salary = decode_salary(lines[si])
                company = exp = edu = city = ""
                end = sal_idx[n + 1] if n + 1 < len(sal_idx) else min(si + 10, len(lines))
                for j in range(si + 1, min(end, len(lines))):
                    ln = lines[j]
                    if "经验" in ln or "应届" in ln:
                        exp = ln
                    elif re.search(r"本科|硕士|博士|大专|学历不限", ln):
                        edu = ln
                    elif "·" in ln and len(ln) < 30:
                        city = ln
                    elif (
                        not company
                        and len(ln) > 2
                        and len(ln) < 40
                        and not re.search(r"年|学历|大专|本科|硕士|博士|不限|应届|·", ln)
                    ):
                        company = ln
                jobs.append(
                    {
                        "title": title,
                        "salary": salary,
                        "company": company,
                        "experience": exp,
                        "education": edu,
                        "city": city,
                        "url": "",
                        "description": "",
                        "hr_name": "",
                        "hr_title": "",
                    }
                )
            links = await self._extract_links()
            if links:
                lm = {l["title"][:12]: l["href"] for l in links if l["title"][:12]}
                for j in jobs:
                    if not j["url"] and j["title"][:12] in lm:
                        j["url"] = lm[j["title"][:12]]
        print(f"  [扫描] 从当前页面提取到 {len(jobs)} 个岗位")
        return jobs

    async def scan_and_apply_current_page(self, greeting_template: Optional[str] = None) -> dict:
        """扫描当前页面全部岗位 → 一键批量投递。"""
        jobs = await self.scan_current_page()
        if not jobs:
            return {"success": False, "message": "当前页面未找到任何岗位", "scanned": 0, "applied": 0}
        urls = [j["url"] for j in jobs if j.get("url")]
        if not urls:
            return {"success": False, "message": "扫描到的岗位没有有效URL", "scanned": len(jobs), "applied": 0}
        results = await self.apply_batch(urls, greeting_template)
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": success_count > 0,
            "message": f"扫描 {len(jobs)} 个岗位，投递 {success_count}/{len(urls)}",
            "scanned": len(jobs),
            "applied": success_count,
            "results": results,
        }

    # ══════════════════════════════════════
    #  监控周期（供后台循环调用）
    # ══════════════════════════════════════

    async def run_chat_monitor_cycle(self) -> dict:
        """
        一个完整的监控周期:
        1. 导航到聊天页
        2. 扫描未读会话
        3. 对每个未读会话: 打开→读消息→存库→AI回复
        """
        result = {"checked": 0, "new_messages": 0, "replies_sent": 0}

        # 只在不在聊天页时才导航
        current_url = self.page.url
        need_nav = "/web/geek/chat" not in current_url
        if need_nav:
            if not await self.navigate_to_chat():
                print("  [监控] 导航到聊天页失败")
                return result
            # 导航后点击未读Tab
            for sel in ['span.label-name:has-text("未读")', '.label-name:has-text("未读")']:
                try:
                    tab = self.page.locator(sel).first
                    if await tab.is_visible():
                        await tab.click()
                        await asyncio.sleep(random.uniform(0.5, 1))
                        break
                except Exception:
                    pass
        # 已在聊天页时不再强制切换Tab，避免干扰用户操作

        if not await self.check_page_safety():
            print("  [监控] 安全检查未通过（登录过期/验证码等）")
            return result

        conversations = await self.poll_conversation_list()
        result["checked"] = len(conversations)
        print(f"  [监控] 扫描到 {len(conversations)} 个会话")
        # 始终打印 body 内容用于调试
        try:
            body_text = await self.page.inner_text("body")
            preview = (body_text or "")[:800].replace("\n", " | ")
            print(f"  [监控] Body: {preview}")
        except Exception:
            pass

        known_convs = list_active_conversations()
        print(f"  [监控] 数据库已知活跃会话: {len(known_convs)}")

        # 已在导航时切到「未读」Tab，当前列表都是未读。每轮上限 3 个
        if not conversations:
            print(f"  [监控] 无未读消息，跳过本轮")
            return result
        if len(conversations) > 3:
            print(f"  [监控] 未读会话: {len(conversations)} 个，本轮只处理前3个")
            conversations = conversations[:3]

        for conv_data in conversations:
            text = conv_data.get("text", "")
            has_unread = conv_data.get("has_unread", False)
            element = conv_data.get("element")

            if not text:
                continue

            # 尝试匹配已知会话：用提取的 HR 名字精确匹配
            matched_conv = None
            extracted_name = conv_data.get("hr_name", "")
            for kc in known_convs:
                kc_name = kc.get("hr_name", "")
                if kc_name and extracted_name and kc_name == extracted_name:
                    matched_conv = kc
                    break

            if not matched_conv:
                for kc in known_convs:
                    kc_name = kc.get("hr_name", "")
                    if kc_name and len(kc_name) >= 3 and kc_name in text:
                        matched_conv = kc
                        break

            if not matched_conv:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                hr_name = conv_data.get("hr_name", "") or lines[0] if lines else ""
                hr_name = hr_name[:20] if len(hr_name) > 20 else hr_name

                # 过滤无效名称
                skip_keywords = [
                    "消息", "联系人", "沟通", "设置", "搜索", "我的", "首页",
                    "已沟通", "继续沟通", "新对话", "系统", "通知", "BOSS",
                    "在线", "离线", "刚刚", "分钟", "小时", "昨天", "简历",
                    "附件", "上传", "制作", "更新", "AI",
                ]
                is_valid = (
                    hr_name
                    and len(hr_name) >= 2
                    and not hr_name.isdigit()
                    and not any(kw == hr_name for kw in skip_keywords)
                    and not any(kw in hr_name and len(hr_name) <= len(kw) + 1 for kw in skip_keywords)
                )
                if not is_valid:
                    print(f"  [监控] 跳过无效会话名: '{hr_name}' (原文: {text[:50]})")
                    continue

                conv_id = get_or_create_conversation(
                    None, hr_name, conv_data.get("company", ""), conv_data.get("job_title", "")
                )
                known_convs = list_active_conversations()
                matched_conv = get_conversation(conv_id)
                if not matched_conv:
                    continue
                print(f"  [监控] 新建会话: {hr_name}")
                result.setdefault("new_conversations", []).append(hr_name)
            else:
                conv_id = matched_conv["id"]
                # 提取的名字比 DB 更精确时自动修正（仅当新名字更长/更完整）
                if extracted_name and len(extracted_name) >= 2:
                    old_name = matched_conv.get("hr_name", "")
                    if old_name != extracted_name and old_name in extracted_name:
                        try:
                            get_db().execute("UPDATE conversations SET hr_name=? WHERE id=?", (extracted_name, conv_id))
                            get_db().commit()
                            matched_conv["hr_name"] = extracted_name
                        except Exception:
                            pass

            # 从会话文本里提取公司名
            if not matched_conv.get("hr_company"):
                company_info = text.split("\n")[0] if "\n" in text else text

                hr_name_part = matched_conv.get("hr_name", "")
                if hr_name_part and len(hr_name_part) >= 2:
                    company_info = company_info.replace(hr_name_part, "", 1)
                company_info = re.sub(r"\d{1,2}:\d{2}|\[.*?\]|送达|已读|未读", "", company_info)
                m = re.search(r"[一-龥]{4,12}", company_info)
                if m:
                    company = m.group()
                    try:
                        get_db().execute("UPDATE conversations SET hr_company=? WHERE id=?", (company, conv_id))
                        get_db().commit()
                        matched_conv["hr_company"] = company
                        print(f"  [监控] 提取公司名: {company}")
                    except Exception:
                        pass

            if matched_conv.get("status") != "active":
                continue
            if not matched_conv.get("auto_reply_enabled"):
                continue

            # 读取消息：打开会话从 DOM 提取
            hr_name_to_open = matched_conv["hr_name"]
            opened = await self.open_conversation_by_name(hr_name_to_open)
            if not opened and len(hr_name_to_open) > 4:
                short = re.match(r"^[一-鿿]{2,3}", hr_name_to_open)
                if short:
                    opened = await self.open_conversation_by_name(short.group(0))
            if not opened:
                print(f"  [监控] 无法打开会话: {hr_name_to_open}")
                continue
            await async_pause(1, 2)
            msgs = await self.read_visible_messages()
            print(f"  [监控] 会话 {matched_conv.get('hr_name')}: 读到 {len(msgs)} 条消息")

            new_count = 0
            clean_msgs = []
            for msg in msgs:
                sender = msg.get("sender", "hr")
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                clean_msgs.append({"sender": sender, "content": content, "status": msg.get("status", "")})

            if clean_msgs:
                replace_conversation_messages(conv_id, clean_msgs)
                last_msg = clean_msgs[-1]
                update_conversation_last_message(conv_id, last_msg["content"], last_msg["sender"], 0)

                # 从 HR 消息里提取微信号
                if not matched_conv.get("hr_wechat"):
                    for m in clean_msgs:
                        if m["sender"] == "hr":
                            patterns = [
                                r"(?:wxid|WXID)[_\-]?\s*[:：]?\s*([a-zA-Z0-9_-]{6,30})",
                                r"(?:微信|VX|vx|wechat|WeChat)[号：:]*\s*[:：]?\s*([a-zA-Z0-9_-]{4,30})",
                                r"(?:加我|加V|找V|加个V)\s*[:：]?\s*([a-zA-Z0-9_-]{4,30})",
                                r"微信号\s+([a-zA-Z0-9_-]{4,30})",
                            ]
                            for pat in patterns:
                                match = re.search(pat, m["content"])
                                if match:
                                    wx_id = match.group(1).strip()
                                    if wx_id and len(wx_id) >= 5:
                                        update_conversation_wechat(conv_id, wx_id)
                                        matched_conv["hr_wechat"] = wx_id
                                        result["wechat_exchanged"] = True
                                        print(f"  [监控] 提取HR微信: {wx_id}")
                                        break

            # 检测需要回复的 HR 消息
            def _is_system_notification(content):
                content = content.strip()
                if len(content) > 80:
                    return False
                patterns = (
                    "你与该职位竞争者PK情况", "竞争力分析", "BOSS安全提示",
                    "系统消息", "沟通分析", "今日推荐", "该Boss已查看了你的简历",
                )
                return any(content.startswith(p) for p in patterns)

            unreplied_hr_msg = None
            for i in range(len(clean_msgs) - 1, -1, -1):
                m = clean_msgs[i]
                if m["sender"] == "me":
                    continue
                if _is_system_notification(m["content"]):
                    continue
                has_reply_after = any(clean_msgs[j]["sender"] == "me" for j in range(i + 1, len(clean_msgs)))
                if not has_reply_after:
                    unreplied_hr_msg = m["content"]
                    print(f"  [监控] 待回复HR消息: {m['content'][:60]}...")
                break

            if unreplied_hr_msg:
                result["new_messages"] += 1

            # 自动回复
            auto_reply_enabled = get_setting("auto_reply_enabled", "false") == "true"
            if unreplied_hr_msg and auto_reply_enabled:
                today_replies = get_today_auto_reply_count()
                if today_replies >= MAX_AUTO_REPLY_PER_DAY:
                    continue

                # 48小时内已回复过的会话不再重复回复（防止骚扰）
                # 但如果有新的未读HR消息，仍然回复
                try:
                    from datetime import datetime, timedelta
                    # 检查最近一条HR消息的时间
                    recent_hr = get_db().execute(
                        "SELECT created_at FROM messages WHERE conversation_id=? AND sender='hr' ORDER BY created_at DESC LIMIT 1",
                        (conv_id,)
                    ).fetchone()
                    recent_me = get_db().execute(
                        "SELECT created_at FROM messages WHERE conversation_id=? AND sender='me' ORDER BY created_at DESC LIMIT 1",
                        (conv_id,)
                    ).fetchone()
                    if recent_hr and recent_me and recent_hr["created_at"] and recent_me["created_at"]:
                        hr_time = datetime.fromisoformat(recent_hr["created_at"].replace(" ", "T").split("+")[0].split(".")[0])
                        me_time = datetime.fromisoformat(recent_me["created_at"].replace(" ", "T").split("+")[0].split(".")[0])
                        # 只有当最近的HR消息早于我的回复，且间隔<48小时时才跳过
                        # （即没有新的HR消息，我之前已经回复过了）
                        if hr_time <= me_time and datetime.now() - me_time < timedelta(hours=48):
                            print(f"  [监控] 跳过 {matched_conv.get('hr_name')}: 48小时内已回复过且无新消息")
                            continue
                except Exception:
                    pass

                try:
                    from .replier import generate_reply

                    job_title = matched_conv.get("job_title", "")
                    job_company = matched_conv.get("hr_company", "")
                    job_desc = ""
                    app_id = matched_conv.get("application_id")
                    if app_id:
                        app = get_application(app_id)
                        if app:
                            job_desc = app.get("description") or ""
                            job_title = job_title or app.get("job_title", "")
                            job_company = job_company or app.get("company", "")

                    job_info = {
                        "title": job_title,
                        "company": job_company,
                        "description": job_desc,
                    }
                    style = get_setting("ai_reply_style", "professional")
                    resume = get_setting("resume_summary", "")
                    wechat = get_setting("wechat_id", "")

                    reply, interest, emotion, dialogue_stage = generate_reply(conv_id, unreplied_hr_msg, job_info, style, resume, wechat)
                    if reply:
                        # 先执行发送操作（简历/微信/电话）
                        msg_lower = unreplied_hr_msg.lower()

                        # 发简历 — 精确匹配"发简历""看看简历"等请求，排除"简历很重要"等讨论
                        if re.search(r'(发|看|传|投|给|send).{0,4}(简历|cv|resume)|(简历|cv|resume).{0,4}(发|看|传|投|给|send)', msg_lower, re.IGNORECASE):
                            if not matched_conv.get("resume_sent"):
                                print(f"  [监控] HR要简历，正在发送...")
                                if await self.send_resume():
                                    mark_resume_sent(conv_id)
                                    await async_pause(1, 2)

                        # 换微信 — 精确匹配短语，排除误匹配
                        wechat_patterns = (
                            r'加.{0,2}微信', r'微信.{0,2}聊', r'加.{0,2}vx',
                            r'加.{0,2}v$', r'微信号', r'换.{0,2}微信',
                        )
                        if any(re.search(p, msg_lower) for p in wechat_patterns):
                            if not matched_conv.get("hr_wechat"):
                                print(f"  [监控] HR要微信，正在发送...")
                                await self.send_wechat(hr_name_to_open)
                                await async_pause(1, 2)

                        # 换电话 — 精确匹配"给电话""手机号多少"等请求，排除"电话面试"等
                        if re.search(r'(给|留|交换|告诉|发|send).{0,4}(电话|手机)|(电话|手机).{0,2}(多少|号码|发|给|交换)', msg_lower):
                            if not matched_conv.get("phone_shared"):
                                print(f"  [监控] HR要电话，正在发送...")
                                if await self.send_phone(hr_name_to_open):
                                    mark_phone_shared(conv_id)
                                    await async_pause(1, 2)

                        # 发送AI回复
                        print(f"  [监控] AI回复: {reply[:60]}...")
                        if await self.send_message(reply):
                            add_message(conv_id, "me", reply, ai_generated=True)
                            update_conversation_last_message(conv_id, reply, "me", 0)
                            increment_daily_stat("auto_replies_sent")
                            result["replies_sent"] += 1
                            if interest or emotion or dialogue_stage:
                                update_conversation_interest(conv_id, interest, emotion, dialogue_stage)
                                parts = []
                                if interest:
                                    parts.append(f"兴趣:{interest}")
                                if emotion:
                                    parts.append(f"情感:{emotion}")
                                if dialogue_stage:
                                    parts.append(f"阶段:{dialogue_stage}")
                                print(f"  [监控] HR评估: {', '.join(parts)}")
                            print(f"  [监控] 回复已发送")
                        else:
                            print(f"  [监控] 回复发送失败!")
                        await asyncio.sleep(random.uniform(5, 15))
                except Exception as e:
                    print(f"  ⚠️ AI回复生成失败: {e}")
            elif unreplied_hr_msg and not auto_reply_enabled:
                print(f"  [监控] 自动回复已关闭，跳过")

            # 下一个会话前确保输入框已清空
            try:
                input_el = self.page.locator("#chat-input").first
                text_content = (await input_el.inner_text()).strip()
                if text_content:
                    print(f"  [监控] 输入框残留文字「{text_content[:30]}...」，正在清空")
                    await input_el.click()
                    await self.page.keyboard.press("Control+a")
                    await self.page.keyboard.press("Backspace")
                    await asyncio.sleep(random.uniform(0.3, 0.5))
            except Exception:
                pass
            # 重新切「未读」Tab
            for sel in ['span.label-name:has-text("未读")', '.label-name:has-text("未读")']:
                try:
                    tab = self.page.locator(sel).first
                    if await tab.is_visible():
                        await tab.click()
                        await asyncio.sleep(random.uniform(0.5, 1))
                        break
                except Exception:
                    pass
            await asyncio.sleep(random.uniform(0.5, 1))

        print(f"  [监控] 本轮完成: 消息 {result['new_messages']}, 回复 {result['replies_sent']}")
        return result
