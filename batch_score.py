"""Batch score (or re-score) all jobs that have descriptions."""
import sqlite3
import sys
import os
import json

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'interview'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'boss_app'))

from boss_app.services.scorer import score_job, score_job_quality, score_hr_activity, compute_composite_score

DB_PATH = '.boss_profile/boss_state.db'

def get_resume_summary():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='resume_summary'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def batch_score(rescore_all=False):
    resume = get_resume_summary()
    print(f"Resume: {len(resume)} chars")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if rescore_all:
        # Re-score ALL jobs with descriptions (ignore existing scores)
        c.execute("""SELECT id, job_title, company, description, salary, hr_name, hr_activity
                     FROM applications
                     WHERE deleted_at IS NULL AND description IS NOT NULL AND description != ''
                     ORDER BY id""")
        jobs = c.fetchall()
        print(f"Found {len(jobs)} jobs to RE-SCORE (all)")
    else:
        # Only score jobs without scores
        c.execute("""SELECT id, job_title, company, description, salary, hr_name, hr_activity
                     FROM applications
                     WHERE score IS NULL AND description IS NOT NULL AND description != ''
                     ORDER BY id""")
        jobs = c.fetchall()
        print(f"Found {len(jobs)} unscored jobs with descriptions")

    scored = 0
    failed = 0

    for i, (aid, title, company, desc, salary, hr_name, hr_activity) in enumerate(jobs):
        print(f"\n[{i+1}/{len(jobs)}] ID={aid}: {title} @ {company}")

        try:
            # 1. CV match score
            try:
                result = score_job(title or "", company or "", desc or "", salary or "", resume)
                cv_score = result.get("score")
                if cv_score is None:
                    cv_score = 30
                    result["summary"] = "LLM评分失败，使用保守默认分"
                print(f"  CV score: {cv_score}")
            except Exception as e:
                print(f"  CV scoring error: {e}")
                cv_score = 30
                result = {"score": 30, "key_skills": [], "gap": "", "advice": "", "summary": f"评分异常: {str(e)[:50]}", "has_resume": bool(resume)}

            # Update cv score
            c.execute("UPDATE applications SET score=?, score_detail=? WHERE id=?",
                      (cv_score, json.dumps(result, ensure_ascii=False), aid))

            # 2. Quality score
            try:
                quality_result = score_job_quality(title or "", company or "", desc or "", salary or "", hr_name or "")
                quality_score = quality_result.get("quality_score")
                if quality_score is None:
                    quality_score = 40
                print(f"  Quality score: {quality_score}")
            except Exception as e:
                print(f"  Quality scoring error: {e}")
                quality_score = 40

            # 3. HR activity score
            try:
                hr_score = score_hr_activity(hr_activity or "")
                print(f"  HR activity: {hr_activity} -> {hr_score}")
            except Exception as e:
                print(f"  HR activity scoring error: {e}")
                hr_score = 0

            # 4. Composite score
            try:
                composite = compute_composite_score(cv_score, quality_score, hr_score)
                print(f"  Composite: {composite}")
            except Exception as e:
                print(f"  Composite scoring error: {e}")
                composite = max(0, min(100, int((cv_score + quality_score + hr_score) / 3)))

            # Update composite
            c.execute("UPDATE applications SET composite_score=?, hr_activity_score=? WHERE id=?",
                      (composite, hr_score, aid))

            scored += 1

            # Commit every 5 jobs
            if scored % 5 == 0:
                conn.commit()
                print(f"  (committed {scored} jobs)")

        except Exception as e:
            # 顶层异常处理：确保单个岗位评分失败不影响其他岗位
            print(f"  !!! CRITICAL ERROR for job {aid}: {e}")
            failed += 1
            # 继续处理下一个岗位
            continue

    conn.commit()
    conn.close()
    print(f"\n=== Done: {scored} scored, {failed} failed ===")

if __name__ == "__main__":
    rescore = "--rescore" in sys.argv
    if rescore:
        print("=== 重新评分模式：将重新评分所有岗位 ===")
    batch_score(rescore_all=rescore)
