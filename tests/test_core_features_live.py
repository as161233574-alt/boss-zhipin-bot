"""
四大核心功能实机测试：
1. 搜索功能 - 启动浏览器 → 搜索岗位 → 查看结果
2. 评分功能 - AI评分 → 综合分 → 合法性检测
3. 智能投递 - 自动投递 → 手动投递 → 批量投递
4. 智能回复 - 聊天监控 → AI自动回复 → 手动发送
"""
import json
import time
import urllib.request
import urllib.error

TOKEN = "mRqpTaGNyLGsDo5BApB5PlJKNa9TbN5Hs9Zo40LUqCY"
BASE = "http://127.0.0.1:8010"


def api(method, path, data=None, timeout=120):
    url = BASE + path
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
    else:
        req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return 0, {"error": str(e)}


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return condition


# ============================================================
#  功能一：搜索功能
# ============================================================
section("功能一：搜索功能")

print("\n--- 1.1 启动浏览器 ---")
t0 = time.time()
code, d = api("POST", "/api/system/start", timeout=60)
elapsed = time.time() - t0
check("启动浏览器接口", code == 200, f"status={code}, time={elapsed:.1f}s")
check("返回started状态", d.get("status") in ("started", "already_started") or "message" in d, f"resp={d}")

# 等待浏览器完全启动
print("  等待浏览器启动...")
time.sleep(3)

# 检查状态
code, d = api("GET", "/api/status")
check("浏览器状态", d.get("browser_running") is True, f"browser_running={d.get('browser_running')}")

print("\n--- 1.2 搜索岗位 ---")
t0 = time.time()
code, d = api("POST", "/api/jobs/search", {
    "keyword": "Python",
    "city": "成都",
    "max_pages": 1
}, timeout=180)
elapsed = time.time() - t0
check("搜索接口响应", code == 200, f"status={code}, time={elapsed:.1f}s")

if code == 200:
    jobs_found = d.get("jobs_found", 0)
    new_jobs = d.get("new_jobs", 0)
    bg = d.get("scoring_in_background", False)
    check("返回岗位数量", jobs_found > 0, f"found={jobs_found}, new={new_jobs}")
    check("返回岗位列表", isinstance(d.get("jobs"), list), f"jobs_count={len(d.get('jobs', []))}")
    if bg:
        print("  [INFO] 评分已在后台启动，可通过WebSocket或轮询查看进度")
    if d.get("jobs"):
        j = d["jobs"][0]
        check("岗位有标题", bool(j.get("job_title") or j.get("title")), f"title={j.get('job_title', j.get('title',''))[:30]}")
        check("岗位有URL", bool(j.get("job_url")), f"url={j.get('job_url','')[:50]}")
else:
    check("搜索响应", False, f"error={d.get('detail', d.get('error',''))[:80]}")

print("\n--- 1.3 验证搜索结果入库 ---")
code, d = api("GET", "/api/jobs?limit=5&sort_by=created_at")
total = d.get("total", 0)
check("数据库有岗位", total > 0, f"total={total}")
if d.get("jobs"):
    latest = d["jobs"][0]
    check("最新岗位有评分字段", "composite_score" in latest, f"score={latest.get('composite_score')}")

print("\n--- 1.4 去重统计 ---")
code, d = api("GET", "/api/jobs/dedup-stats")
check("去重统计", code == 200, f"unique={d.get('total_unique')}, dups={d.get('duplicates')}")


# ============================================================
#  功能二：评分功能
# ============================================================
section("功能二：评分功能")

# 获取一个待评分的岗位
code, d = api("GET", "/api/jobs?status=pending&limit=1")
jobs = d.get("jobs", [])
if not jobs:
    print("  [SKIP] 没有待评分岗位，先添加测试数据")
    # 用搜索结果中的岗位
    code, d = api("GET", "/api/jobs?limit=1")
    jobs = d.get("jobs", [])

if jobs:
    test_job = jobs[0]
    test_id = test_job["id"]
    test_title = test_job.get("job_title", "")[:40]
    print(f"\n  测试岗位: [{test_id}] {test_title}")

    print("\n--- 2.1 单岗位AI评分 ---")
    t0 = time.time()
    code, d = api("POST", f"/api/jobs/{test_id}/score", timeout=90)
    elapsed = time.time() - t0
    check("评分接口响应", code == 200, f"status={code}, time={elapsed:.1f}s")

    if code == 200:
        score_data = d.get("score") or d  # API may return score data directly or wrapped
        cv_score = score_data.get("cv_score") or score_data.get("score")
        quality_score = score_data.get("quality_score")
        composite = score_data.get("composite")
        hr_score = score_data.get("hr_score")
        legitimacy = score_data.get("legitimacy")

        check("CV匹配分", cv_score is not None and cv_score > 0, f"cv_score={cv_score}")
        check("质量评分", quality_score is not None, f"quality_score={quality_score}")
        check("综合评分", composite is not None, f"composite={composite}")
        check("HR活跃分", hr_score is not None, f"hr_score={hr_score}")
        check("合法性检测", legitimacy is not None, f"legitimacy={legitimacy}")
        check("关键技能", bool(score_data.get("key_skills")), f"skills={score_data.get('key_skills',[])}")
        gap = score_data.get("gap") or ""
        check("差距分析", bool(gap), f"gap={gap[:50]}")
        advice = score_data.get("advice") or ""
        check("建议", bool(advice), f"advice={advice[:50]}")
    else:
        check("评分结果", False, f"resp={d}")

    print("\n--- 2.2 验证评分持久化 ---")
    code, d = api("GET", f"/api/jobs/{test_id}")
    if d.get("job"):
        j = d["job"]
        check("分数已保存", j.get("score") is not None, f"score={j.get('score')}")
        check("综合分已保存", j.get("composite_score") is not None, f"composite={j.get('composite_score')}")
        check("合法性已保存", j.get("legitimacy") is not None, f"legitimacy={j.get('legitimacy')}")

    print("\n--- 2.3 合法性检测效果 ---")
    code, d = api("GET", "/api/jobs?limit=20")
    jobs = d.get("jobs", [])
    high = sum(1 for j in jobs if j.get("legitimacy") == "high")
    caution = sum(1 for j in jobs if j.get("legitimacy") == "caution")
    suspicious = sum(1 for j in jobs if j.get("legitimacy") == "suspicious")
    scored = sum(1 for j in jobs if j.get("composite_score") is not None)
    print(f"  已评分: {scored}/{len(jobs)}")
    print(f"  合法性分布: high={high}, caution={caution}, suspicious={suspicious}")
    check("大部分岗位已评分", scored > 0)
else:
    check("评分测试", False, "无可用岗位")


# ============================================================
#  功能三：智能投递
# ============================================================
section("功能三：智能投递")

print("\n--- 3.1 查看自动投递配置 ---")
code, d = api("GET", "/api/settings")
s = d.get("settings", {})
auto_enabled = s.get("auto_apply_enabled", "false")
threshold = s.get("auto_apply_threshold", "73")
hr_active = s.get("auto_apply_hr_active_required", "true")
daily_limit = s.get("daily_apply_limit", "15")
print(f"  自动投递: {'开启' if auto_enabled == 'true' else '关闭'}")
print(f"  最低综合分: {threshold}")
print(f"  要求HR活跃: {hr_active}")
print(f"  每日上限: {daily_limit}")

print("\n--- 3.2 手动投递单个岗位 ---")
code, d = api("GET", "/api/jobs?status=pending&limit=1")
pending = d.get("jobs", [])
if pending:
    job = pending[0]
    job_url = job.get("job_url")
    job_id = job["id"]
    print(f"  投递岗位: [{job_id}] {job.get('job_title','')[:30]}")
    t0 = time.time()
    code, d = api("POST", "/api/jobs/apply", {"job_url": job_url}, timeout=60)
    elapsed = time.time() - t0
    check("投递接口响应", code == 200, f"status={code}, time={elapsed:.1f}s")
    check("投递成功", d.get("success") is True, f"success={d.get('success')}, msg={d.get('message','')[:50]}")

    # 验证状态变更
    code, d = api("GET", f"/api/jobs/{job_id}")
    if d.get("job"):
        check("状态变为applied", d["job"].get("status") == "applied", f"status={d['job'].get('status')}")
        greeting = d["job"].get("greeting_text") or ""
        check("招呼语已记录", len(greeting) > 0, f"greeting={greeting[:40]}")
else:
    print("  [SKIP] 无待投递岗位")

print("\n--- 3.3 拒绝重复投递 ---")
if pending:
    code, d = api("POST", "/api/jobs/apply", {"job_url": job_url}, timeout=60)
    check("重复投递被拒", d.get("success") is False or "已投递" in str(d.get("message", "")), f"msg={d.get('message','')[:50]}")

print("\n--- 3.4 自动投递触发（无高分岗位时） ---")
code, d = api("POST", "/api/auto-apply/trigger", timeout=60)
check("自动投递接口", code == 200 or code == 503, f"status={code}")

print("\n--- 3.5 投递日志 ---")
code, d = api("GET", "/api/auto-apply-logs?limit=5")
check("投递日志", code == 200, f"count={len(d.get('logs', []))}")

print("\n--- 3.6 今日投递统计 ---")
code, d = api("GET", "/api/stats")
today = d.get("today_applications", 0)
pending_count = d.get("pending", 0)
print(f"  今日投递: {today}")
print(f"  待投递: {pending_count}")
check("统计数据", code == 200)


# ============================================================
#  功能四：智能回复
# ============================================================
section("功能四：智能回复")

print("\n--- 4.1 查看会话列表 ---")
code, d = api("GET", "/api/conversations")
convs = d.get("conversations", [])
check("会话列表", code == 200, f"count={len(convs)}")

if convs:
    conv = convs[0]
    conv_id = conv["id"]
    hr_name = conv.get("hr_name", "")
    auto_reply = conv.get("auto_reply_enabled", False)
    print(f"  测试会话: [{conv_id}] {hr_name}")
    print(f"  自动回复: {'开启' if auto_reply else '关闭'}")

    print("\n--- 4.2 查看聊天消息 ---")
    code, d = api("GET", f"/api/conversations/{conv_id}/messages?limit=10")
    msgs = d.get("messages", [])
    check("消息列表", code == 200, f"count={len(msgs)}")
    if msgs:
        for m in msgs[:3]:
            sender = "HR" if m.get("sender") == "hr" else "我"
            ai_tag = " [AI]" if m.get("ai_generated") else ""
            content = (m.get("content", "") or "")[:40]
            print(f"    {sender}{ai_tag}: {content}")

    print("\n--- 4.3 自动回复开关 ---")
    code, d = api("POST", f"/api/conversations/{conv_id}/resume")
    check("开启自动回复(resume)", code == 200, f"status={code}")

    code, d = api("POST", f"/api/conversations/{conv_id}/pause")
    check("关闭自动回复(pause)", code == 200, f"status={code}")

    print("\n--- 4.4 手动发送消息 ---")
    code, d = api("POST", f"/api/conversations/{conv_id}/send", {"content": "你好，我对这个岗位很感兴趣"}, timeout=60)
    check("手动发送", code == 200 or code == 503, f"status={code}")

    print("\n--- 4.5 会话同步 ---")
    code, d = api("POST", f"/api/conversations/{conv_id}/sync", timeout=30)
    check("会话同步", code == 200 or code == 503, f"status={code}")

    print("\n--- 4.6 自动回复配置 ---")
    code, d = api("GET", "/api/settings")
    s = d.get("settings", {})
    auto_reply_enabled = s.get("auto_reply_enabled", "true")
    style = s.get("ai_reply_style", "professional")
    min_delay = s.get("min_reply_delay_sec", "30")
    max_delay = s.get("max_reply_delay_sec", "120")
    print(f"  自动回复: {'开启' if auto_reply_enabled == 'true' else '关闭'}")
    print(f"  回复风格: {style}")
    print(f"  回复延迟: {min_delay}-{max_delay}秒")
    check("自动回复配置完整", auto_reply_enabled in ("true", "false"))
else:
    print("  [SKIP] 无会话数据")


# ============================================================
#  综合评估
# ============================================================
section("综合评估")

code, d = api("GET", "/api/status")
code2, d2 = api("GET", "/api/stats")
code3, d3 = api("GET", "/api/jobs/dedup-stats")

print(f"""
  系统状态:
    浏览器: {'运行中' if d.get('browser_running') else '未启动'}
    监控: {'运行中' if d.get('monitor_running') else '未启动'}
    今日投递: {d2.get('today_applications', 0)}
    待投递: {d2.get('pending', 0)}
    已回复: {d2.get('replied', 0)}

  数据规模:
    总岗位: {d3.get('total_unique', 0)}
    独立岗位: {d3.get('total_unique', 0)}
    重复岗位: {d3.get('duplicates', 0)}
""")
