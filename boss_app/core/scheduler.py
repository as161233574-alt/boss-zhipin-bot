"""定时自动搜索投递调度器。

在后台按配置的时间点自动执行搜索 + 评分 + 投递。
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from ..models.settings import get_setting
from . import state


class AutoScheduler:
    """定时自动搜索投递调度器。"""

    def __init__(self):
        self.task: Optional[asyncio.Task] = None
        self.last_run: Optional[str] = None
        self.last_result: Optional[dict] = None
        self.next_run: Optional[str] = None
        self._last_exec_key: str = ""

    def start(self, automation, ws_manager) -> None:
        """启动定时任务后台循环。"""
        if self.task is not None and not self.task.done():
            return
        self.task = asyncio.create_task(self._loop(automation, ws_manager))

    def stop(self) -> None:
        """停止定时任务。"""
        if self.task is not None and not self.task.done():
            self.task.cancel()
            self.task = None
        self.next_run = None

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def _parse_cron_times(self, cron_str: str) -> list:
        """解析逗号分隔的时间点，返回 [(hour, minute), ...]。"""
        times = []
        for part in cron_str.split(","):
            part = part.strip()
            if ":" in part:
                try:
                    h, m = part.split(":")
                    times.append((int(h), int(m)))
                except ValueError:
                    pass
        return times

    def _should_run_now(self, cron_times: list) -> bool:
        """检查当前时间是否匹配任何配置的时间点（1分钟窗口），且本分钟未执行过。"""
        now = datetime.now()
        now_key = f"{now.hour}:{now.minute}"
        if now_key == self._last_exec_key:
            return False
        for h, m in cron_times:
            if now.hour == h and now.minute == m:
                self._last_exec_key = now_key
                return True
        return False

    def _compute_next_run(self, cron_times: list) -> Optional[str]:
        """计算下一个执行时间。"""
        now = datetime.now()
        today_times = []
        tomorrow_times = []
        for h, m in cron_times:
            t = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if t > now:
                today_times.append(t)
            else:
                tomorrow_times.append(t + timedelta(days=1))
        candidates = sorted(today_times + tomorrow_times)
        return candidates[0].strftime("%Y-%m-%d %H:%M") if candidates else None

    async def _loop(self, automation, ws_manager) -> None:
        """主循环：每分钟检查一次是否到达执行时间。"""
        # 启动后等待 30 秒，让浏览器稳定
        await asyncio.sleep(30)

        while True:
            try:
                enabled = get_setting("auto_schedule_enabled", "false") == "true"
                if not enabled:
                    await asyncio.sleep(60)
                    continue

                cron_str = get_setting("auto_schedule_cron", "09:00,14:00")
                cron_times = self._parse_cron_times(cron_str)
                if not cron_times:
                    await asyncio.sleep(60)
                    continue

                self.next_run = self._compute_next_run(cron_times)

                if self._should_run_now(cron_times):
                    result = await self._execute(automation, ws_manager)
                    self.last_run = datetime.now().strftime("%Y-%m-%d %H:%M")
                    self.last_result = result
                    # 执行完后等 61 秒，避免同一分钟重复触发
                    await asyncio.sleep(61)
                else:
                    await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[定时调度] 循环异常: {e}")
                await asyncio.sleep(60)

    async def _execute(self, automation, ws_manager) -> dict:
        """执行一次自动搜索 + 评分 + 投递。"""
        from ..routes.jobs import CITY_MAP, _fetch_details_and_score, _save_job_with_dedup
        from ..models.application import get_today_application_count, get_all_active_jobs_for_legitimacy

        result = {"searched": 0, "scored": 0, "applied": 0, "skipped": 0, "errors": []}

        try:
            # 检查投递上限
            try:
                daily_limit = int(get_setting("daily_apply_limit", "15"))
            except (ValueError, TypeError):
                daily_limit = 15
            current_count = get_today_application_count()
            if current_count >= daily_limit:
                result["errors"].append("已达到今日投递上限")
                await ws_manager.broadcast({"type": "scheduler_skipped", "reason": "daily_limit"})
                return result

            # 搜索所有关键词
            keywords = get_setting("search_keywords", "AI Agent")
            city = get_setting("default_city", "全国")
            city_code = CITY_MAP.get(city, "100010000")

            if not automation or automation.page is None:
                result["errors"].append("浏览器未启动")
                return result

            all_jobs = []
            for kw in [k.strip() for k in keywords.split(",") if k.strip()]:
                async with state.browser_sync_lock:
                    jobs = await automation.search(kw, city_code, max_pages=1)
                all_jobs.extend(jobs)
            jobs = all_jobs
            result["searched"] = len(jobs)

            if not jobs:
                await ws_manager.broadcast({"type": "scheduler_search_done", "found": 0})
                return result

            # 保存新岗位
            new_ids = []
            for j in jobs:
                aid, is_new, _ = _save_job_with_dedup(j)
                if is_new and aid:
                    new_ids.append(aid)

            if new_ids:
                all_jobs = get_all_active_jobs_for_legitimacy()
                scored, applied = await _fetch_details_and_score(new_ids, all_jobs)
                result["scored"] = scored
                result["applied"] = applied

            await ws_manager.broadcast({
                "type": "scheduler_complete",
                "searched": result["searched"],
                "scored": result["scored"],
                "applied": result["applied"],
                "skipped": result["skipped"],
            })

        except Exception as e:
            import traceback
            print(f"[定时调度] 执行异常: {e}")
            traceback.print_exc()
            result["errors"].append(f"调度执行异常: {str(e)[:200]}")

        return result


# 全局单例
auto_scheduler = AutoScheduler()
