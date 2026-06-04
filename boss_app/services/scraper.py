"""
BOSS直聘 AI Agent 岗位采集工具 — 服务层 (Service Layer)

从 boss_firefox.py 提取的 BossScraper 类及其依赖项。
"""

import argparse
import asyncio
import csv
import io
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from ..core.database import get_db
from ..models.settings import get_setting

# Windows 编码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── 配置 ──
TODAY = date.today().isoformat()
DATE_STR = date.today().strftime("%Y-%m-%d")

KEYWORDS = [
    "AI Agent",
    "AI产品经理",
    "电商",
    "机械",
    "化工",
    "外贸",
]

# BOSS直聘城市代码
CITIES = {
    # 山东省
    "济南": "101120100",
    "青岛": "101120200",
    "淄博": "101120300",
    "德州": "101120400",
    "烟台": "101120500",
    "潍坊": "101120600",
    "济宁": "101120700",
    "泰安": "101120800",
    "临沂": "101120900",
    "菏泽": "101121000",
    "滨州": "101121100",
    "东营": "101121200",
    "威海": "101121300",
    "枣庄": "101121400",
    "日照": "101121500",
    "聊城": "101121700",
    # 一线城市
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    # 新一线城市
    "成都": "101270100",
    "杭州": "101210100",
    "武汉": "101200100",
    "南京": "101190100",
    "重庆": "101040100",
    "西安": "101110100",
    "长沙": "101250100",
    "天津": "101030100",
    "苏州": "101190400",
    "郑州": "101180100",
    "东莞": "101281600",
    "沈阳": "101070100",
    "宁波": "101210400",
    "昆明": "101290100",
    # 其他省会城市
    "合肥": "101220100",
    "福州": "101230100",
    "厦门": "101230200",
    "南昌": "101240100",
    "贵阳": "101260100",
    "南宁": "101300100",
    "太原": "101100100",
    "石家庄": "101090100",
    "哈尔滨": "101050100",
    "长春": "101060100",
    "兰州": "101160100",
    "乌鲁木齐": "101130100",
    "呼和浩特": "101080100",
    "拉萨": "101140100",
    "西宁": "101150100",
    "银川": "101170100",
    "海口": "101310100",
    "三亚": "101310200",
    "全国": "100010000",
}

OUTPUT_DIR = Path.home() / "AI" / "岗位日报"
# 相对于项目根目录（从 boss_app/services/ 向上两级）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = _PROJECT_ROOT / ".boss_profile" / "firefox_state.json"
PROFILE_DIR = _PROJECT_ROOT / ".boss_profile" / "firefox_user_data"

ANTI_DETECT = """
// ── 核心：隐藏 webdriver 标记 ──
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
try { delete Object.getPrototypeOf(navigator).webdriver; } catch(e) {}

// ── 语言 ──
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});

// ── 硬件（桌面端典型值）──
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});

// ── screen 与 viewport 保持一致 ──
const fixScreen = () => {
    const w = window.innerWidth || 1280;
    const h = window.innerHeight || 800;
    Object.defineProperty(screen, 'width',  {get: () => w});
    Object.defineProperty(screen, 'height', {get: () => h});
    Object.defineProperty(screen, 'availWidth',  {get: () => w});
    Object.defineProperty(screen, 'availHeight', {get: () => h});
    Object.defineProperty(screen, 'colorDepth', {get: () => 24});
    Object.defineProperty(screen, 'pixelDepth', {get: () => 24});
};
fixScreen();
window.addEventListener('resize', fixScreen);

// ── 时区 ──
if (Intl && Intl.DateTimeFormat) {
    const origResolved = Intl.DateTimeFormat.prototype.resolvedOptions;
    Intl.DateTimeFormat.prototype.resolvedOptions = function() {
        const r = origResolved.call(this);
        r.timeZone = 'Asia/Shanghai';
        return r;
    };
}

// ── canvas 指纹干扰：轻微噪声扰动 ──
try {
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 10 && this.height > 10) {
            const imgData = ctx.getImageData(0, 0, this.width, this.height);
            for (let i = 0; i < imgData.data.length; i += 4) {
                imgData.data[i] ^= 1;  // R channel ±1 bit
            }
            ctx.putImageData(imgData, 0, 0);
        }
        return origToDataURL.apply(this, arguments);
    };
} catch(e) {}

// ── WebGL 指纹一致性 ──
try {
    const getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        // UNMASKED_VENDOR / UNMASKED_RENDERER
        if (p === 37445) return 'Google Inc. (Intel)';
        if (p === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)';
        return getParam.call(this, p);
    };
} catch(e) {}

// ── 权限通知 ──
if (window.Permissions) {
    const orig = window.Permissions.prototype.query;
    window.Permissions.prototype.query = function(d) {
        if (d.name === 'notifications') return Promise.resolve({state: 'prompt'});
        return orig.call(this, d);
    };
}

// ── navigator.connection ──
try {
    Object.defineProperty(navigator, 'connection', {
        get: () => ({effectiveType: '4g', rtt: 50, downlink: 10, saveData: false})
    });
} catch(e) {}
"""

# ── 技能词库（仅分析用）──
SKILL_MAP = {
    "编程语言": {
        "Python",
        "Java",
        "Go",
        "Golang",
        "Rust",
        "C++",
        "C#",
        "C",
        "PHP",
        "Ruby",
        "Swift",
        "Kotlin",
        "Scala",
        "TypeScript",
        "JavaScript",
        "Node.js",
    },
    "前端": {"React", "Vue", "Angular", "Next.js", "HTML", "CSS", "Tailwind"},
    "AI/ML框架": {
        "PyTorch",
        "TensorFlow",
        "Transformers",
        "vLLM",
        "ONNX",
        "HuggingFace",
        "GGUF",
        "Stable Diffusion",
        "Diffusion",
        "Vision",
        "Multimodal",
    },
    "AI框架/工具": {
        "LangChain",
        "LangGraph",
        "LlamaIndex",
        "AutoGen",
        "CrewAI",
        "Dify",
        "Coze",
        "MCP",
    },
    "大模型技术": {
        "RAG",
        "Fine-tuning",
        "Finetune",
        "微调",
        "SFT",
        "RLHF",
        "LoRA",
        "QLoRA",
        "Prompt",
        "Function Calling",
        "Tool Calling",
        "Agent",
        "Multi-Agent",
        "Embedding",
        "LLM",
        "AI Agent",
        "AIGC",
    },
    "数据库/中间件": {
        "MySQL",
        "PostgreSQL",
        "Redis",
        "MongoDB",
        "Elasticsearch",
        "Milvus",
        "FAISS",
        "Chroma",
        "Qdrant",
        "Pinecone",
        "Weaviate",
        "Kafka",
        "RabbitMQ",
    },
    "部署/架构": {
        "Docker",
        "Kubernetes",
        "K8s",
        "FastAPI",
        "Flask",
        "Django",
        "Spring",
        "Nginx",
        "gRPC",
        "GraphQL",
        "WebSocket",
        "REST",
        "RESTful",
        "CI/CD",
        "GitHub Actions",
        "Linux",
        "GPU",
        "CUDA",
    },
    "云平台": {"AWS", "GCP", "Azure", "阿里云", "腾讯云"},
    "其他": {
        "数据结构",
        "算法",
        "系统设计",
        "架构",
        "微服务",
        "高并发",
        "分布式",
        "设计模式",
        "OOP",
        "TDD",
        "单元测试",
        "测试",
    },
}
ALL_SKILLS = {s for v in SKILL_MAP.values() for s in v}
MY_SKILLS = {
    s.lower()
    for v in {
        "编程语言": {"Python", "TypeScript", "JavaScript"},
        "AI框架/工具": {"LangChain", "LangGraph", "AutoGen", "CrewAI", "Dify", "Coze"},
        "大模型技术": {
            "LLM",
            "AI Agent",
            "RAG",
            "微调",
            "MCP",
            "Prompt Engineering",
            "Function Calling",
            "Tool Calling",
            "Embedding",
        },
        "数据库/向量库": {"MySQL", "Milvus", "FAISS", "Chroma", "Qdrant"},
        "部署/运维": {"Docker", "FastAPI", "Kubernetes"},
        "AI平台/模型": {"Claude", "OpenAI", "GPT"},
    }.values()
    for s in v
}


def decode_salary(text):
    """解码BOSS直聘的薪资私有编码（U+E030..U+E039 -> 0..9, U+E03A -> 0）"""
    result = []
    for c in text:
        code = ord(c)
        if 0xE030 <= code <= 0xE039:
            result.append(str(code - 0xE030))
        elif code == 0xE03A:
            result.append('0')  # 边界情况
        else:
            result.append(c)
    return "".join(result)


def salary_ok(text):
    if not text:
        return False
    nums = re.findall(
        r"(\d+)",
        re.sub(r"[^\d-]", "", text.replace("~", "-").replace("K", "").replace("k", "")),
    )
    if len(nums) < 2:
        return False
    l, h = int(nums[0]), int(nums[1])
    if l < 5 and h < 20:
        l *= 10
        h *= 10
    return 15 <= l and h <= 35


async def async_pause(a=1.0, b=3.0):
    await asyncio.sleep(random.uniform(a, b))


def pause(a=1.0, b=3.0):
    """Sync pause kept for scraper.py standalone usage only."""
    time.sleep(random.uniform(a, b))


def parse_skills(text):
    tl = text.lower()
    r = defaultdict(list)
    for cat, skills in SKILL_MAP.items():
        for s in skills:
            if s.lower() in tl:
                r[cat].append(s)
    return dict(r)


# ══════════════════════════════════════
#  浏览器
# ══════════════════════════════════════


class BossScraper:
    def __init__(self, headless=False):
        self.headless = headless
        self._pw = self._br = self._ctx = None
        self.page = None

    async def start(self):
        self._pw = await async_playwright().start()
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        kw = {
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 800},
            "locale": "zh-CN",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        }
        self._ctx = await self._pw.firefox.launch_persistent_context(str(PROFILE_DIR), **kw)
        self._br = None

        # 持久化 profile 自动管理 cookies，不额外 add_cookies 避免冲突
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                cookies = state.get("cookies") or []
                if cookies:
                    for c in cookies:
                        try:
                            await self._ctx.add_cookies([c])
                        except Exception:
                            pass
            except Exception:
                pass

        await self._ctx.add_init_script(ANTI_DETECT)
        self.page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        self.page.set_default_timeout(15000)
        self.page.set_default_navigation_timeout(15000)

    async def close(self):
        if self._ctx:
            try:
                await self._ctx.close()
            except Exception:
                pass
        elif self._br:
            try:
                await self._br.close()
            except Exception:
                pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass

    async def _body_text(self, limit=1500):
        try:
            text = await self.page.inner_text("body")
            return text[:limit]
        except Exception:
            return ""

    async def _login_prompt_visible(self):
        """判断当前页面是否真的落在登录/扫码态，避免误判普通详情页。"""
        try:
            url = (self.page.url or "").lower()
        except Exception:
            url = ""

        explicit_login_paths = (
            "/web/user/",
            "/login/",
            "ka=header-login",
            "login?redirect=",
        )
        if any(path in url for path in explicit_login_paths):
            return True

        body = await self._body_text(4000)

        # 详情页/聊天页的已登录特征，优先级高于任意"登录"字样。
        authenticated_indicators = (
            "职位描述",
            "岗位职责",
            "任职要求",
            "公司介绍",
            "竞争力分析",
            "立即沟通",
            "立即聊",
            "已沟通",
            "继续沟通",
            "聊天",
            "消息",
            "沟通中",
            "发简历",
        )
        if any(text in body for text in authenticated_indicators):
            return False

        strong_prompts = (
            "请登录",
            "扫码登录",
            "密码登录",
            "验证码登录",
            "微信扫码",
            "登录BOSS直聘",
        )
        if not any(text in body for text in strong_prompts):
            return False

        try:
            return await self.page.evaluate("""() => {
                const visible = el => {
                    if (!el) return false;
                    const style = getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const ariaHidden = el.getAttribute('aria-hidden');
                    return style
                        && style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && style.opacity !== '0'
                        && ariaHidden !== 'true'
                        && rect.width > 0
                        && rect.height > 0;
                };

                const selectors = [
                    'input[placeholder*="手机号"]',
                    'input[placeholder*="验证码"]',
                    'input[type="password"]',
                    '.qrcode-img',
                    'img[class*="qrcode"]',
                    '[class*="login-panel"]',
                    '[class*="login-modal"]',
                    '[class*="sign-form"]',
                    '[class*="user-sign"]',
                ];

                return selectors.some(sel =>
                    Array.from(document.querySelectorAll(sel)).some(visible)
                );
            }""")
        except Exception:
            return False

    async def is_logged_in_page(self):
        """当前页面是否能作为已登录态使用。"""
        try:
            url = self.page.url
        except Exception:
            return False
        # about:blank 视为未登录（需要先访问BOSS直聘页面）
        if url == "about:blank":
            return False
        # 检查页面标题是否包含登录相关关键词
        try:
            title = await self.page.title()
            if any(kw in title for kw in ["登录", "注册", "login", "sign"]):
                return False
        except Exception:
            pass
        # 检查body是否为空（页面未加载）
        try:
            body = await self._body_text(1000)
            if not body or len(body) < 50:
                return False
        except Exception:
            pass
        return not await self._login_prompt_visible()

    async def login(self):
        await self.page.goto("https://www.zhipin.com/web/user/?ka=header-login")
        await async_pause(2, 4)
        await self.page.bring_to_front()
        print("\n🔓 浏览器已打开，请扫码登录")
        last = self.page.url
        logged_in = False
        for i in range(600):
            await asyncio.sleep(1)
            try:
                url = await self.page.evaluate("window.location.href")
            except Exception:
                continue
            if (
                any(p in url for p in ["/web/geek", "/web/geek/chat", "/job_detail"])
                and not await self._login_prompt_visible()
            ):
                print("✅ 登录成功")
                logged_in = True
                break
            last = url
            if i > 0 and i % 30 == 0:
                print("  ⏳ %ds" % i)
        if not logged_in:
            raise TimeoutError("扫码登录超时或未确认进入已登录页面")
        state = await self._ctx.storage_state()
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        print("✅ 登录状态已保存")

        # 预热：导航到聊天页验证 session 稳定性，确保 token 生效
        try:
            await self.page.goto("https://www.zhipin.com/web/geek/chat", wait_until="load", timeout=30000)
            await async_pause(3, 5)
            if not await self._login_prompt_visible():
                print("✅ 会话预热成功")
            else:
                print("⚠️ 预热时仍检测到登录提示，可能需要手动刷新页面")
        except Exception as e:
            print(f"⚠️ 会话预热失败: {e}")

    # ── 搜索列表页 ──

    async def _extract_current_page_jobs(self):
        """从当前页面提取岗位列表（单页，不翻页）。"""
        # 检查页面是否需要登录
        try:
            login_check = await self.page.evaluate("""() => {
                const body = document.body.innerText || '';
                return {
                    hasLogin: body.includes('登录') || body.includes('请先登录'),
                    hasJobList: document.querySelectorAll('a[href*="/job_detail/"]').length,
                    pageTitle: document.title,
                    bodyLength: body.length,
                    firstLines: body.split('\\n').slice(0, 10).join(' | ')
                };
            }""")
            print(f"  [检查] 页面状态: {login_check}")
            if login_check.get('hasLogin') and login_check.get('hasJobList', 0) == 0:
                print(f"  [警告] 页面需要登录，请先在浏览器中登录BOSS直聘")
                return []
        except Exception as e:
            print(f"  [检查] 页面检查失败: {e}")

        # 直接从链接提取岗位
        links = await self._extract_links()
        print(f"  [提取] 找到 {len(links or [])} 个链接")
        if not links:
            return []

        jobs = []
        for link in links:
            url = link.get("href", "")
            title = (link.get("title") or "").strip()
            if not url or not title or len(title) < 2 or len(title) > 60:
                continue
            # 排除非岗位标题
            if re.search(r'公司|工商|安全|竞争力|评论|相似|推荐|首页|消息|简历|APP|海外|校招', title):
                continue
            jobs.append({
                "title": title,
                "salary": "",
                "company": "",
                "experience": "",
                "education": "",
                "city": "",
                "url": url,
                "description": "",
                "hr_name": "",
                "hr_title": "",
            })
        print(f"  [提取] 过滤后 {len(jobs)} 个岗位")
        return jobs

    async def search(self, keyword, city_code="100010000", max_pages=3):
        """搜索关键词，支持无限滚动分页加载。

        Args:
            keyword: 搜索关键词
            city_code: 城市代码
            max_pages: 最大加载页数（默认3页，避免翻到死岗位）

        Returns:
            去重后的岗位列表
        """
        url = "https://www.zhipin.com/web/geek/job?query=%s&city=%s" % (
            quote_plus(keyword),
            city_code,
        )
        for attempt in range(3):
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await async_pause(3, 5)

                all_jobs = []
                seen_urls = set()
                no_new_count = 0
                low_quality_count = 0  # 连续低质量页计数

                for page in range(max_pages):
                    # 提取当前页面岗位
                    if page == 0:
                        await self._scroll_all()
                    else:
                        # 滚动到底部触发加载
                        old_job_count = await self.page.evaluate("""
                            () => document.querySelectorAll('a[href*="/job_detail/"]').length
                        """)
                        scrolled = await self._scroll_to_bottom()
                        if scrolled <= 0:
                            print(f"  [分页] 第{page+1}页: 无法继续滚动，停止")
                            break
                        # 等待新内容加载
                        loaded = await self._wait_for_new_jobs(old_job_count)
                        if not loaded:
                            print(f"  [分页] 第{page+1}页: 无新内容加载，停止")
                            no_new_count += 1
                            if no_new_count >= 2:
                                break
                            continue
                        # 滚动加载后重新扫描全部内容
                        await self._scroll_all()

                    jobs = await self._extract_current_page_jobs()

                    # 去重：只保留新岗位
                    new_jobs = []
                    for j in jobs:
                        if j["url"] and j["url"] not in seen_urls:
                            seen_urls.add(j["url"])
                            new_jobs.append(j)
                        elif not j["url"]:
                            key = j["title"] + "|" + j["salary"] + "|" + j.get("company", "")
                            if key not in seen_urls:
                                seen_urls.add(key)
                                new_jobs.append(j)

                    if new_jobs:
                        all_jobs.extend(new_jobs)
                        no_new_count = 0
                        # 检查新岗位质量：如果新增太少，可能是到了死岗位区域
                        if len(new_jobs) <= 3:
                            low_quality_count += 1
                        else:
                            low_quality_count = 0
                        print(f"  [分页] 第{page+1}页: 新增 {len(new_jobs)} 条（累计 {len(all_jobs)} 条）")
                    else:
                        no_new_count += 1
                        low_quality_count += 1
                        print(f"  [分页] 第{page+1}页: 无新岗位")
                        if no_new_count >= 2:
                            break

                    # 智能停止：连续50页低质量（<=3条新岗位），停止翻页
                    if low_quality_count >= 50:
                        print(f"  [分页] 连续低质量页，停止翻页")
                        break

                    # 已获取足够岗位（30+），停止
                    if len(all_jobs) >= 30:
                        print(f"  [分页] 已获取 {len(all_jobs)} 条，足够使用")
                        break

                    # 页间延迟
                    if page < max_pages - 1:
                        await async_pause(2, 3)

                print(f"  [搜索] {keyword}@{city_code}: 共获取 {len(all_jobs)} 条（{min(page+1, max_pages)} 页）")
                return all_jobs

            except Exception as e:
                if attempt < 2:
                    print(f"  ⚠️ 搜索重试 ({attempt+1}/3): {e}")
                    await async_pause(2, 4)
                else:
                    print(f"  ❌ 搜索失败: {keyword}@{city_code}: {e}")
                    return []

    def _filter_by_welfare(self, jobs, welfare_keywords):
        """福利筛选：AND逻辑，所有关键词都必须匹配。纯 Python，无需 async。"""
        if not welfare_keywords:
            return jobs
        filtered = []
        for j in jobs:
            tags = " ".join(j.get("welfareList", []) or [])
            if not tags:
                tags = j.get("description", "") or ""
            if all(kw in tags for kw in welfare_keywords):
                filtered.append(j)
        return filtered

    async def _extract_job_cards(self):
        """优先从岗位卡片 DOM 提取，避免正文行号变化导致链接和岗位错配。"""
        try:
            # 先等待岗位列表加载
            try:
                await self.page.wait_for_selector('a[href*="/job_detail/"]', timeout=5000)
            except Exception:
                pass

            rows = await self.page.evaluate("""() => {
                const cards = [];
                const seen = new Set();
                // 遍历所有岗位链接
                const allLinks = document.querySelectorAll('a[href*="/job_detail/"]');
                const debugInfo = {totalLinks: allLinks.length, hrefs: []};
                allLinks.forEach(a => {
                    const rawHref = a.getAttribute('href') || '';
                    debugInfo.hrefs.push(rawHref);
                    if (!rawHref || seen.has(rawHref)) return;
                    seen.add(rawHref);
                    const href = a.href || rawHref;

                    // 向上找最近的卡片容器（最多8层）
                    let card = a;
                    for (let i = 0; i < 8; i++) {
                        card = card.parentElement;
                        if (!card) break;
                        const cls = card.className || '';
                        if (cls.includes('job-card') || cls.includes('job-primary') ||
                            cls.includes('search-job') || cls.includes('job-list') ||
                            card.tagName === 'LI') break;
                    }
                    if (!card) card = a;

                    const text = (card.innerText || '').trim();
                    const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);

                    // 薪资：匹配 XX-XXK 格式
                    let salary = '';
                    for (const l of lines) {
                        if (/\\d+[-~]\\d+[Kk元]/.test(l) && l.length < 30) {
                            salary = l;
                            break;
                        }
                    }
                    if (!salary) return; // 没有薪资的跳过

                    // 岗位名称：薪资前一行，或链接文字第一行
                    let title = '';
                    const salIdx = lines.indexOf(salary);
                    if (salIdx > 0) {
                        title = lines[salIdx - 1];
                    }
                    if (!title) {
                        title = (a.innerText || '').trim().split('\\n')[0];
                    }
                    if (!title || title.length < 2 || title.length > 60) return;
                    if (/公司|工商|安全|竞争力|评论|相似|推荐/.test(title)) return;

                    // 公司名称：薪资后找不含数字/经验/学历的行
                    let company = '';
                    const skipPat = /\\d+[-~]|经验|应届|在校|本科|硕士|博士|大专|中专|学历|不限|K\\/|元\\/|天\\/周|薪|·|五险|社保|福利/i;
                    for (let i = (salIdx >= 0 ? salIdx + 1 : 1); i < Math.min(lines.length, (salIdx >= 0 ? salIdx + 8 : 8)); i++) {
                        const l = lines[i];
                        if (l.length >= 2 && l.length <= 40 && !skipPat.test(l) && !/^\\d/.test(l)) {
                            company = l;
                            break;
                        }
                    }

                    // 城市
                    let city = '';
                    for (const l of lines) {
                        if (l.includes('·') && l.length < 30) {
                            city = l.split('·')[0].trim();
                            break;
                        }
                    }

                    // 经验 & 学历
                    let experience = lines.find(x => /^\\d+[-~]\\d+年|^\\d+年|^经验不限$|^应届$|^在校$/.test(x) && x.length < 20) || '';
                    let education = lines.find(x => /^(本科|硕士|博士|大专|中专|中技|高中|学历不限|不限)$/.test(x)) || '';

                    cards.push({title, salary, company, city, experience, education, url: href, _debug: lines.slice(0, 3).join(' | ')});
                });
                return {cards, debug: debugInfo};
            }""")
        except Exception:
            return []

        if not rows or not rows.get("cards"):
            # 调试：打印页面上的链接信息
            try:
                debug = await self.page.evaluate("""() => {
                    const links = document.querySelectorAll('a[href*="/job_detail/"]');
                    return {
                        count: links.length,
                        hrefs: Array.from(links).slice(0, 5).map(a => a.getAttribute('href')),
                        classes: Array.from(document.querySelectorAll('[class*="job"]')).slice(0, 10).map(e => e.className)
                    };
                }""")
                print(f"  [调试] 页面链接数: {debug.get('count', 0)}, hrefs: {debug.get('hrefs', [])}, classes: {debug.get('classes', [])[:5]}")
            except Exception:
                pass
            return []

        debug_info = rows.get("debug", {})
        print(f"  [调试] 找到 {len(rows['cards'])} 个岗位卡片, 总链接数: {debug_info.get('totalLinks', 0)}, 去重后href数: {len(debug_info.get('hrefs', []))}")

        result = []
        seen = set()
        for row in rows["cards"]:
            url = (row.get("url") or "").strip()
            title = (row.get("title") or "").strip()
            if not url or not title or url in seen:
                continue
            seen.add(url)
            salary = decode_salary((row.get("salary") or "").strip())
            company = (row.get("company") or "").strip()
            city = (row.get("city") or "").strip()
            experience = (row.get("experience") or "").strip()
            education = (row.get("education") or "").strip()

            if not re.search(r'\d+[Kk元]', salary):
                continue

            result.append({
                "title": title,
                "salary": salary,
                "company": company,
                "experience": experience,
                "education": education,
                "city": city,
                "url": url,
                "description": "",
                "hr_name": "",
                "hr_title": "",
            })
        return result

    async def _scroll_all(self):
        """滚动加载所有岗位（单页内）。"""
        try:
            h = await self.page.evaluate("document.body.scrollHeight")
            for p in range(0, int(h) + 400, 400):
                await self.page.evaluate("window.scrollTo(0,%d)" % p)
                await asyncio.sleep(random.uniform(0.3, 0.6))
        except Exception:
            pass

    async def _scroll_to_bottom(self):
        """滚动到页面底部，触发无限加载。返回新增内容高度。"""
        try:
            old_height = await self.page.evaluate("document.body.scrollHeight")
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(1.5, 2.5))
            new_height = await self.page.evaluate("document.body.scrollHeight")
            return new_height - old_height
        except Exception:
            return 0

    async def _wait_for_new_jobs(self, old_count, timeout=8):
        """等待新岗位加载完成。"""
        start = time.time()
        while time.time() - start < timeout:
            current = await self.page.evaluate("""
                () => document.querySelectorAll('a[href*="/job_detail/"]').length
            """)
            if current > old_count:
                return True
            await asyncio.sleep(0.5)
        return False

    @staticmethod
    def is_hr_inactive(activity_text: str) -> bool:
        """判断 HR 是否不活跃（超过7天未活跃）。

        活跃度映射：
        - 刚刚活跃/今日活跃/日内活跃/本周活跃 → 活跃（7天内）
        - 本月活跃/半年前活跃/近半年活跃 → 不活跃（超过7天）
        - 空值 → 视为不活跃（无法确认）
        """
        if not activity_text:
            return True  # 无活跃信息，视为不活跃
        # 7天内活跃的关键词（与 score_hr_activity 保持一致）
        active_patterns = ['刚刚活跃', '今日活跃', '日内活跃', '本周活跃']
        for pat in active_patterns:
            if pat in activity_text:
                return False
        # 本月及更早视为不活跃
        return True

    async def _extract_links(self):
        try:
            result = await self.page.evaluate("""()=>{
                const r=[];const s=new Set();
                const all = document.querySelectorAll('a[href*="/job_detail/"]');
                const debugHrefs = [];
                all.forEach(a=>{
                    const raw = a.getAttribute('href') || '';
                    const full = a.href || raw;
                    const t=(a.innerText||'').trim();
                    debugHrefs.push({raw: raw.substring(0, 80), full: full.substring(0, 80), title: t.substring(0, 30)});
                    // 用 raw href 去重（相对路径），但存储 full href
                    if(raw && t && !s.has(raw) && t.length<60){s.add(raw);r.push({href:full,title:t.substring(0,60)});}
                });
                return {links: r, total: all.length, url: location.href, sample: debugHrefs.slice(0, 5)};
            }""")
            print(f"  [链接] 页面URL: {result.get('url','?')}")
            print(f"  [链接] 总链接: {result.get('total',0)}, 有效: {len(result.get('links',[]))}")
            print(f"  [链接] 样本: {result.get('sample',[])}")
            return result.get("links", [])
        except Exception as e:
            print(f"  [链接] 提取失败: {e}")
            return []

    # ── 详情页 ──

    async def fetch_detail(self, url):
        """访问详情页，提取岗位描述 + HR/招聘者信息 + HR活跃度（含重试）"""
        result = {"description": "", "hr_name": "", "hr_title": "", "hr_activity": ""}
        print(f"  [详情] 开始抓取: {url}")
        try:
            # 外层超时调整为 70s，确保内层重试能完整执行（20s × 3 次 + 缓冲时间）
            return await asyncio.wait_for(self._fetch_detail_inner(url, result), timeout=70)
        except asyncio.TimeoutError:
            print(f"  ❌ 详情抓取全局超时(70s): {url}")
            return result

    async def _fetch_detail_inner(self, url, result):
        """fetch_detail 的内部实现。"""
        for attempt in range(3):
            try:
                # 先关闭可能的弹窗/对话框
                try:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass
                # 用 asyncio.wait_for 包裹导航，确保超时生效
                try:
                    await asyncio.wait_for(
                        self.page.goto(url, wait_until="commit", timeout=15000),
                        timeout=20
                    )
                except asyncio.TimeoutError:
                    print(f"  ⚠️ 页面导航超时(20s) ({attempt+1}/3): {url}")
                    if attempt < 2:
                        try:
                            await self.page.goto("about:blank", timeout=3000)
                        except Exception:
                            pass
                        await asyncio.sleep(1)
                        continue
                    return result
                # 等待页面内容加载
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
                # 验证是否真正跳转到了目标页面
                current = self.page.url
                if "job_detail" not in current and "job/" not in current:
                    print(f"  ⚠️ 页面未跳转到详情页，当前URL: {current}")
                    if attempt < 2:
                        # 尝试刷新页面恢复
                        try:
                            await self.page.reload(wait_until="domcontentloaded", timeout=5000)
                        except Exception:
                            pass
                        await async_pause(1, 2)
                        continue
                    return result
                print(f"  [详情] 页面加载完成: {current}")
                break
            except Exception as e:
                print(f"  ⚠️ 详情页异常 ({attempt+1}/3): {e}")
                if attempt < 2:
                    # 尝试导航到空白页重置浏览器状态
                    try:
                        await self.page.goto("about:blank", timeout=3000)
                    except Exception:
                        pass
                    await async_pause(1, 2)
                else:
                    print(f"  ❌ 详情页失败: {url}")
                    return result
        try:
            await async_pause(0.5, 1)
            print(f"  [详情] 开始提取数据")

            # 先关闭可能的弹窗
            try:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
            except Exception:
                pass

            # ── 提取招聘者信息（带超时）──
            try:
                hr_info = await asyncio.wait_for(self.page.evaluate("""() => {
                    const body = document.body.innerText || '';
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
                    const bossSelectors = [
                        '.boss-info-attr', '.boss-info', '.recruiter-info',
                        '.boss-name', '.recruiter-name', '[class*="boss"]',
                    ];
                    for (const sel of bossSelectors) {
                        const el = document.querySelector(sel);
                        if (el && el.innerText.trim()) {
                            const t = el.innerText.trim();
                            if (t.length <= 15) {
                                if (!hrName) hrName = t;
                                break;
                            }
                        }
                    }
                    // HR活跃度提取
                    const activityPatterns = ['刚刚活跃', '今日活跃', '日内活跃', '本周活跃', '本月活跃', '半年前活跃', '近半年活跃'];
                    let activity = '';
                    for (const line of lines) {
                        for (const pat of activityPatterns) {
                            if (line.includes(pat)) { activity = pat; break; }
                        }
                        if (activity) break;
                    }
                    if (!activity) {
                        const actEls = document.querySelectorAll('[class*="active-time"], [class*="activity"], .boss-info-time');
                        for (const el of actEls) {
                            const t = (el.innerText || '').trim();
                            for (const pat of activityPatterns) {
                                if (t.includes(pat)) { activity = pat; break; }
                            }
                            if (activity) break;
                        }
                    }
                    return {hrName, hrTitle, activity};
                }"""), timeout=10)
                result["hr_name"] = (hr_info.get("hrName") or "").strip()
                result["hr_title"] = (hr_info.get("hrTitle") or "").strip()
                result["hr_activity"] = (hr_info.get("activity") or "").strip()
                print(f"  [详情] HR信息提取完成: {result['hr_name']} | {result['hr_activity']}")
            except asyncio.TimeoutError:
                print(f"  ⚠️ HR信息提取超时(10s)")
            except Exception as e:
                print(f"  ⚠️ HR信息提取异常: {e}")

            # ── 提取岗位描述（带超时）──
            desc_text = ""
            try:
                desc_selectors = [
                    '.job-detail-section .job-sec-text',
                    '.job-sec-text',
                    '.job-detail',
                    '[class*="job-detail"]',
                    '.text-job',
                ]
                for sel in desc_selectors:
                    try:
                        el = await asyncio.wait_for(self.page.query_selector(sel), timeout=5)
                    except asyncio.TimeoutError:
                        print(f"  ⚠️ 选择器 {sel} 超时")
                        continue
                    if el:
                        try:
                            desc_text = (await asyncio.wait_for(el.inner_text(), timeout=5)).strip()
                        except asyncio.TimeoutError:
                            print(f"  ⚠️ 元素文本提取超时")
                            continue
                        if desc_text and len(desc_text) > 20:
                            print(f"  [详情] CSS描述提取成功: {len(desc_text)}字 (选择器: {sel})")
                            break
                        desc_text = ""
            except Exception as e:
                print(f"  ⚠️ CSS描述提取异常: {e}")

            print(f"  [详情] 开始提取页面文本...")
            # 再次关闭弹窗
            try:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.2)
            except Exception:
                pass
            body = None
            # 使用 JavaScript 直接提取，比 inner_text 更可靠
            try:
                body = await asyncio.wait_for(
                    self.page.evaluate("() => document.body ? document.body.innerText : ''"),
                    timeout=8
                )
            except asyncio.TimeoutError:
                print(f"  ⚠️ JavaScript文本提取超时(8s)")
            except Exception as e:
                print(f"  ⚠️ JavaScript文本提取异常: {e}")
            if not body:
                # 最后尝试 inner_text
                try:
                    body = await asyncio.wait_for(self.page.inner_text("body"), timeout=5)
                except Exception:
                    pass
            if not body:
                print(f"  ⚠️ 页面文本提取失败，跳过")
                return result
            lines = [l.strip() for l in body.split("\n") if l.strip()]

            skill_lines = []
            capture = False
            for l in lines:
                if "职位描述" in l or "岗位职责" in l:
                    capture = True
                    continue
                if capture:
                    # 停止词：遇到这些标记说明描述部分结束
                    if any(
                        stop in l
                        for stop in [
                            "公司介绍",
                            "工商信息",
                            "BOSS 安全提示",
                            "竞争力分析",
                            "相似职位",
                            "推荐公司",
                            "该公司的其他职位",
                        ]
                    ):
                        break
                    # 跳过HR信息行（名字、活跃状态、公司名后缀）
                    if re.match(r'^(刚刚活跃|今日活跃|\d+日内活跃|日内活跃|本周活跃|本月活跃|半年前活跃|近半年活跃)$', l):
                        continue
                    if l in ("招聘者", "招聘经理", "HR", "HRBP", "人事", "猎头"):
                        continue
                    # 跳过公司名后的装饰行
                    if l in ("·", "招聘者", "BOSS"):
                        continue
                    skill_lines.append(l)
            # 清理尾部可能混入的HR信息
            while skill_lines and skill_lines[-1] in ("·", "招聘者", "招聘经理", "HR", "HRBP", "人事", "猎头", "BOSS"):
                skill_lines.pop()
            # 移除尾部的活跃状态和公司信息
            cleaned = []
            for l in skill_lines:
                if re.match(r'^(刚刚活跃|今日活跃|\d+日内活跃|日内活跃|本周活跃|本月活跃|半年前活跃|近半年活跃)$', l):
                    continue
                cleaned.append(l)

            # 清理CSS选择器提取的描述中的HR信息和无关内容
            if desc_text:
                desc_lines = [l.strip() for l in desc_text.split("\n") if l.strip()]
                filtered_desc = []
                for dl in desc_lines:
                    # 跳过HR活跃状态
                    if re.match(r'^(刚刚活跃|今日活跃|\d+日内活跃|日内活跃|本周活跃|本月活跃|半年前活跃|近半年活跃)$', dl):
                        continue
                    # 跳过HR相关标记
                    if dl in ("·", "招聘者", "招聘经理", "HR", "HRBP", "人事", "猎头", "BOSS"):
                        continue
                    # 跳过停止词后的内容
                    if any(stop in dl for stop in ["公司介绍", "工商信息", "BOSS 安全提示", "竞争力分析",
                                                    "相似职位", "推荐公司", "该公司的其他职位", "看过该职位的人还看了"]):
                        break
                    filtered_desc.append(dl)
                desc_text = "\n".join(filtered_desc)

            # 优先使用CSS选择器提取的描述，如果更完整的话
            text_desc = "\n".join(cleaned) if cleaned else ""
            if desc_text and len(desc_text) > len(text_desc):
                result["description"] = desc_text
            else:
                result["description"] = text_desc

            # 如果 JS 没抓到招聘者信息，从文本中尝试解析
            if not result["hr_name"]:
                for i, l in enumerate(lines):
                    if l in ("HR", "招聘者", "招聘经理", "HRBP", "人事", "猎头"):
                        if i > 0 and len(lines[i - 1]) <= 6:
                            result["hr_name"] = lines[i - 1]
                            result["hr_title"] = l
                            break

            print(f"  [详情] 提取完成: desc={len(result['description'])}字 HR={result['hr_name']} 活跃={result['hr_activity']}")

        except Exception as e:
            print(f"  ⚠️ 数据提取异常: {e}")
        return result


# ══════════════════════════════════════
#  分析
# ══════════════════════════════════════


def skill_gap(jobs):
    c = Counter()
    for j in jobs:
        text = (j.get("description") or "") + " " + (j.get("title") or "")
        seen = set()
        for cat, skills in parse_skills(text).items():
            for s in skills:
                if s.lower() not in seen:
                    seen.add(s.lower())
                    c[s] += 1
    have, miss = [], []
    for s, n in c.most_common():
        (have if s.lower() in MY_SKILLS else miss).append({"skill": s, "count": n})
    return {"have": have, "missing": miss, "total": len(jobs)}


# ══════════════════════════════════════
#  输出
# ══════════════════════════════════════


def output_report(jobs):
    lines = ["# 招聘日报 · %s\n" % DATE_STR]
    lines.append("> 来源：**BOSS直聘** · 无薪资限制 · 共 %d 条\n---\n" % len(jobs))

    for i, j in enumerate(jobs, 1):
        lines.append("### %d. %s %s" % (i, j["title"], j["salary"]))
        lines.append("- 公司: %s" % (j.get("company") or "未显示"))
        if j.get("city"):
            lines.append("- 城市: %s" % j["city"])
        if j.get("experience"):
            lines.append("- 经验: %s" % j["experience"])
        if j.get("education"):
            lines.append("- 学历: %s" % j["education"])
        if j.get("hr_name"):
            lines.append("- 👤 招聘者: %s (%s)" % (j["hr_name"], j.get("hr_title") or ""))
        if j.get("url"):
            lines.append("- 链接: %s" % j["url"])
        desc = j.get("description", "")
        if desc:
            lines.append("- 岗位技能：%s" % desc[:600])
        lines.append("---\n")
    lines.append("\n*数据采集于 %s，BOSS直聘*\n" % DATE_STR)
    return "\n".join(lines)


def skill_report(gap):
    lines = ["# AI Agent 技能差距分析报告 · %s\n" % DATE_STR]
    lines.append("> 基于 BOSS 直聘 %d 个岗位\n---\n" % gap["total"])
    lines.append("## 一、✅ 你已拥有的技能\n")
    for item in gap["have"]:
        lines.append("- **%s**: %d个岗位" % (item["skill"], item["count"]))
    lines.append("\n## 二、🔍 需要查漏补缺\n")
    for item in gap["missing"][:30]:
        p = "🔴" if item["count"] >= 10 else "🟡" if item["count"] >= 5 else "🟢"
        lines.append("- %s **%s**: %d个岗位" % (p, item["skill"], item["count"]))
    return "\n".join(lines)


# ══════════════════════════════════════
#  主流程（独立运行时使用）
# ══════════════════════════════════════


async def _async_main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--headless", action="store_true", default=False)
    ap.add_argument("--keywords")
    ap.add_argument("--output", default=str(OUTPUT_DIR))
    ap.add_argument("--max-jobs", type=int, default=64)
    args = ap.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else KEYWORDS

    if not STATE_FILE.exists() and not args.login:
        print("⚠️ 请先运行: python3 boss_firefox.py --login")
        sys.exit(1)

    sc = BossScraper(headless=args.headless)
    await sc.start()
    try:
        if args.login:
            await sc.login()
            return

        # Phase 1: 搜索列表（关键词 × 城市）
        all_jobs = []
        seen = set()
        for city_name, city_code in CITIES.items():
            for kw in keywords:
                if len(all_jobs) >= args.max_jobs:
                    break
                print("\n📌 搜索: 「%s」@ %s" % (kw, city_name))
                try:
                    jobs = await sc.search(kw, city_code)
                except Exception as e:
                    print("  ⚠️ 失败: %s" % e)
                    continue
                ok = []
                for j in jobs:
                    key = j["title"] + j["salary"] + j.get("company", "")
                    if key not in seen:
                        seen.add(key)
                        j["city"] = city_name
                        ok.append(j)
                print("  %d条, 去重后%d条(累计%d)" % (len(jobs), len(ok), len(all_jobs)))
                all_jobs.extend(ok)
                if len(all_jobs) >= args.max_jobs:
                    print("  📊 已达上限%d条" % args.max_jobs)
                    break
                await async_pause(2, 4)
            if len(all_jobs) >= args.max_jobs:
                break

        print("\n📊 共%d条" % len(all_jobs))
        if not all_jobs:
            return

        # Phase 2: 逐个访问详情页
        print("\n🔍 开始采集岗位详情（共%d条）..." % len(all_jobs))
        success = 0
        for i, j in enumerate(all_jobs):
            if not j.get("url"):
                continue
            print(
                "  [%d/%d] %s" % (i + 1, len(all_jobs), j["title"][:25]),
                end=" ",
                flush=True,
            )
            detail = await sc.fetch_detail(j["url"])
            if detail["description"]:
                j["description"] = detail["description"]
                success += 1
            j["hr_name"] = detail.get("hr_name", "")
            j["hr_title"] = detail.get("hr_title", "")
            if detail["description"]:
                print("✅ %d字 | HR: %s" % (len(detail["description"]), j["hr_name"] or "未识别"))
            else:
                print("⚠️ 无描述 | HR: %s" % (j["hr_name"] or "未识别"))
            await asyncio.sleep(random.uniform(1.5, 3.0))

        print("📊 详情采集: %d/%d条成功" % (success, len(all_jobs)))

        gap = skill_gap(all_jobs)
        print("\n" + "=" * 60)
        print("📊 技能差距分析")
        print("=" * 60)
        for item in gap["have"][:10]:
            print("  ✅ %s: %d个岗位" % (item["skill"], item["count"]))
        for item in gap["missing"][:15]:
            p = "🔴" if item["count"] >= 10 else "🟡" if item["count"] >= 5 else "🟢"
            print("  %s %s: %d个岗位" % (p, item["skill"], item["count"]))

        with open(out_dir / ("招聘日报_%s.md" % DATE_STR), "w", encoding="utf-8") as f:
            f.write(output_report(all_jobs))
        print("📄 日报: %s/招聘日报_%s.md" % (out_dir, DATE_STR))

        csv_path = out_dir / ("招聘数据_%s.csv" % DATE_STR)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "title",
                    "company",
                    "salary",
                    "city",
                    "experience",
                    "education",
                    "hr_name",
                    "hr_title",
                    "url",
                    "description",
                ],
            )
            writer.writeheader()
            for j in all_jobs:
                writer.writerow({k: j.get(k, "") for k in writer.fieldnames})
        print("📊 数据: %s/招聘数据_%s.csv" % (out_dir, DATE_STR))
        print("\n✅ 完成！")

    finally:
        await sc.close()


def main():
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
