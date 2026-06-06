"""Batch score (or re-score) all jobs that have descriptions.

Uses combined LLM scoring (1 call per job instead of 2) and parallel execution.
"""
import sqlite3
import sys
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add paths (parent directory is project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'interview'))
sys.path.insert(0, _PROJECT_ROOT)

from boss_app.services.scorer import score_job_combined, score_hr_activity, compute_composite_score

DB_PATH = '.boss_profile/boss_state.db'

def get_resume_summary():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='resume_summary'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def _score_one(job_row, resume):
    """Score a single job (runs in thread pool)."""
    aid, title, company, desc, salary, hr_name, hr_activity = job_row
    try:
        result = score_job_combined(
            title or "", company or "", desc or "", salary or "",
            hr_name or "", resume
        )
        cv_score = result.get("cv_score")
        quality_score = result.get("quality_score")
        if cv_score is None:
            cv_score = 30
        if quality_score is None or quality_score == 0:
            quality_score = 40

        hr_score = score_hr_activity(hr_activity or "")
        composite = compute_composite_score(cv_score, quality_score, hr_score)

        return {
            "aid": aid, "cv_score": cv_score, "quality_score": quality_score,
            "hr_score": hr_score, "composite": composite,
            "result": result, "ok": True,
        }
    except Exception as e:
        return {"aid": aid, "ok": False, "error": str(e)}

def batch_score(rescore_all=False, max_workers=3):
    resume = get_resume_summary()
    print(f"Resume: {len(resume)} chars")
    print(f"Parallel workers: {max_workers}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if rescore_all:
        c.execute("""SELECT id, job_title, company, description, salary, hr_name, hr_activity
                     FROM applications
                     WHERE deleted_at IS NULL AND description IS NOT NULL AND description != ''
                     ORDER BY id""")
        jobs = c.fetchall()
        print(f"Found {len(jobs)} jobs to RE-SCORE (all)")
    else:
        c.execute("""SELECT id, job_title, company, description, salary, hr_name, hr_activity
                     FROM applications
                     WHERE score IS NULL AND description IS NOT NULL AND description != ''
                     ORDER BY id""")
        jobs = c.fetchall()
        print(f"Found {len(jobs)} unscored jobs with descriptions")

    scored = 0
    failed = 0

    # Parallel scoring
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_score_one, row, resume): row[0] for row in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                r = future.result()
                aid = r["aid"]
                if r["ok"]:
                    cv_score = r["cv_score"]
                    quality_score = r["quality_score"]
                    hr_score = r["hr_score"]
                    composite = r["composite"]
                    result = r["result"]

                    c.execute("UPDATE applications SET score=?, score_detail=? WHERE id=?",
                              (cv_score, json.dumps(result, ensure_ascii=False), aid))
                    c.execute("UPDATE applications SET composite_score=?, hr_activity_score=? WHERE id=?",
                              (composite, hr_score, aid))
                    scored += 1
                    print(f"[{i}/{len(jobs)}] ID={aid}: CV={cv_score} 质量={quality_score} HR={hr_score} 综合={composite}")
                else:
                    failed += 1
                    print(f"[{i}/{len(jobs)}] ID={aid}: FAILED - {r['error']}")

                # Commit every 5 jobs
                if (scored + failed) % 5 == 0:
                    conn.commit()
            except Exception as e:
                failed += 1
                print(f"  !!! CRITICAL ERROR: {e}")

    conn.commit()
    conn.close()
    print(f"\n=== Done: {scored} scored, {failed} failed ===")

if __name__ == "__main__":
    rescore = "--rescore" in sys.argv
    workers = 3
    for arg in sys.argv:
        if arg.startswith("--workers="):
            workers = int(arg.split("=")[1])
    if rescore:
        print("=== 重新评分模式：将重新评分所有岗位 ===")
    batch_score(rescore_all=rescore, max_workers=workers)
