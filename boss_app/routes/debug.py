"""调试 / 页面分析相关 API 路由。

BOSS 改版时用于诊断 CSS 选择器是否仍然有效。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import state

router = APIRouter()


# ══════════════════════════════════════
#  Pydantic Models
# ══════════════════════════════════════


class SelectorTest(BaseModel):
    selector: str


# ══════════════════════════════════════
#  调试接口
# ══════════════════════════════════════


@router.post("/api/debug/selector-test")
async def test_selector(req: SelectorTest):
    """测试任意 CSS 选择器，返回匹配元素数和文本。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    result = await state.automation.page.evaluate(
        """(sel) => {
        try {
            const els = document.querySelectorAll(sel);
            const items = [];
            for (let i = 0; i < Math.min(els.length, 10); i++) {
                items.push((els[i].innerText || '').trim().substring(0, 200));
            }
            return {count: els.length, samples: items};
        } catch(e) {
            return {error: e.message};
        }
    }""",
        req.selector,
    )
    return result


@router.get("/api/debug/page-stats")
async def page_stats():
    """返回当前页面 DOM 统计，帮助诊断选择器失效。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    result = await state.automation.page.evaluate("""() => {
    const stats = {};
    stats.url = window.location.href;
    stats.title = document.title;
    stats.bodyLength = (document.body?.innerText || '').length;
    // 关键元素计数
    stats.liCount = document.querySelectorAll('li').length;
    stats.inputCount = document.querySelectorAll('input, textarea, [contenteditable]').length;
    stats.buttonCount = document.querySelectorAll('button').length;
    stats.messageItems = document.querySelectorAll('li.message-item, [class*="message-item"]').length;
    stats.listItems = document.querySelectorAll('li[role="listitem"]').length;
    stats.chatInput = document.querySelector('#chat-input') ? 1 : 0;
    stats.sendButton = document.querySelector('button[type="send"]') ? 1 : 0;
    // body 前 500 字符
    stats.bodyPreview = (document.body?.innerText || '').substring(0, 500);
    return stats;
}""")
    return result


@router.get("/api/debug/selectors-status")
async def selectors_status():
    """检查所有关键选择器的有效性。"""
    if not state.automation or state.automation.page is None:
        raise HTTPException(status_code=503, detail="浏览器未启动")
    from ..services.automation import SELECTORS

    result = await state.automation.page.evaluate(
        """(groups) => {
        const res = {};
        for (const [key, sels] of Object.entries(groups)) {
            for (const sel of sels) {
                try {
                    const count = document.querySelectorAll(sel).length;
                    if (count > 0) {
                        res[key] = {selector: sel, count: count, ok: true};
                        break;
                    }
                } catch(e) {}
            }
            if (!res[key]) res[key] = {selector: sels[sels.length-1], count: 0, ok: false};
        }
        return res;
    }""",
        SELECTORS,
    )
    return result
