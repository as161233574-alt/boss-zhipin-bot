"""Services 层完整测试。"""
import pytest
from unittest.mock import patch

# 模拟无 API key 的配置
_NO_API_KEY_CFG = {"api_key": "", "base_url": "", "model": ""}


# ══════════════════════════════════════
#  scorer.py
# ══════════════════════════════════════

class TestScorer:
    def test_score_hr_activity_just_active(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("刚刚活跃") == 100

    def test_score_hr_activity_today(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("今日活跃") == 80

    def test_score_hr_activity_3days(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("3日内活跃") == 60

    def test_score_hr_activity_week(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("本周活跃") == 40

    def test_score_hr_activity_month(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("本月活跃") == 30

    def test_score_hr_activity_half_year(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("半年前活跃") == 20

    def test_score_hr_activity_unknown(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("活跃") == 10

    def test_score_hr_activity_empty(self):
        from boss_app.services.scorer import score_hr_activity
        assert score_hr_activity("") == 0
        assert score_hr_activity(None) == 0

    def test_compute_composite_score_all(self):
        from boss_app.services.scorer import compute_composite_score
        score = compute_composite_score(80, 70, 60)
        expected = int(round(80 * 0.55 + 70 * 0.25 + 60 * 0.20))
        assert score == expected

    def test_compute_composite_score_partial(self):
        from boss_app.services.scorer import compute_composite_score
        # 只有 CV 分
        score = compute_composite_score(80, None, None)
        assert score == 80

    def test_compute_composite_score_two_dims(self):
        from boss_app.services.scorer import compute_composite_score
        score = compute_composite_score(80, 70, None)
        # 权重重分配: CV 0.55/(0.55+0.25) = 0.6875, Q 0.25/0.8 = 0.3125
        expected = int(round(80 * 0.55 / 0.8 + 70 * 0.25 / 0.8))
        assert score == expected

    def test_compute_composite_score_none(self):
        from boss_app.services.scorer import compute_composite_score
        assert compute_composite_score(None, None, None) == 0

    def test_compute_composite_score_bounds(self):
        from boss_app.services.scorer import compute_composite_score
        assert compute_composite_score(100, 100, 100) == 100
        assert compute_composite_score(0, 0, 0) == 0

    def test_check_legitimacy_clean(self):
        from boss_app.services.scorer import check_legitimacy
        job = {
            "title": "Python开发", "company": "测试公司",
            "description": "这是一段足够长的岗位描述" * 5,
            "salary": "15-25K", "hr_name": "张三",
        }
        result = check_legitimacy(job)
        assert result["level"] == "high"
        assert len(result["signals"]) == 0

    def test_check_legitimacy_short_jd(self):
        from boss_app.services.scorer import check_legitimacy
        job = {"title": "T", "company": "C", "description": "短", "salary": "10K", "hr_name": "H"}
        result = check_legitimacy(job)
        assert any(s["type"] == "short_jd" for s in result["signals"])

    def test_check_legitimacy_no_hr(self):
        from boss_app.services.scorer import check_legitimacy
        job = {"title": "T", "company": "C", "description": "长描述" * 20, "salary": "10K", "hr_name": ""}
        result = check_legitimacy(job)
        assert any(s["type"] == "no_hr" for s in result["signals"])

    def test_check_legitimacy_wide_salary(self):
        from boss_app.services.scorer import check_legitimacy
        job = {"title": "T", "company": "C", "description": "长描述" * 20, "salary": "5-50K", "hr_name": "H"}
        result = check_legitimacy(job)
        assert any(s["type"] == "salary_range_wide" for s in result["signals"])

    def test_check_legitimacy_duplicate(self):
        from boss_app.services.scorer import check_legitimacy
        job = {"title": "T", "company": "C", "description": "长描述" * 20, "salary": "10K", "hr_name": "H"}
        existing = [{"company": "C", "job_title": "T"}, {"company": "C", "job_title": "T"}, {"company": "C", "job_title": "T"}]
        result = check_legitimacy(job, existing)
        assert any(s["type"] == "duplicate_posting" for s in result["signals"])

    def test_check_legitimacy_suspicious(self):
        from boss_app.services.scorer import check_legitimacy
        job = {"title": "T", "company": "C", "description": "短", "salary": "5-50K", "hr_name": ""}
        result = check_legitimacy(job)
        assert result["level"] == "suspicious"

    @patch("boss_app.services.scorer._load_ai_config", return_value=_NO_API_KEY_CFG)
    def test_score_job_no_api_key(self, mock_cfg):
        from boss_app.services.scorer import score_job
        result = score_job("Python开发", "公司", "描述", "15K")
        assert result["score"] is None

    @patch("boss_app.services.scorer._load_ai_config", return_value=_NO_API_KEY_CFG)
    def test_score_job_quality_no_api_key(self, mock_cfg):
        from boss_app.services.scorer import score_job_quality
        result = score_job_quality("Python开发", "公司", "描述", "15K", "张三")
        assert result["quality_score"] is None

    @patch("boss_app.services.scorer._load_ai_config", return_value=_NO_API_KEY_CFG)
    def test_score_job_combined_no_api_key(self, mock_cfg):
        from boss_app.services.scorer import score_job_combined
        result = score_job_combined("Python开发", "公司", "描述", "15K", "张三", "")
        assert result["cv_score"] is None
        assert result["quality_score"] is None


# ══════════════════════════════════════
#  replier.py
# ══════════════════════════════════════

class TestReplier:
    def test_generate_greeting(self, test_db):
        from boss_app.services.replier import generate_greeting
        greeting = generate_greeting("Python开发", "测试公司")
        assert isinstance(greeting, str)
        assert len(greeting) > 0
        assert "Python开发" in greeting

    def test_generate_greeting_with_template(self, test_db):
        from boss_app.services.replier import generate_greeting
        g1 = generate_greeting("Python开发", "测试公司", template="自定义招呼 {job_title}")
        assert g1 == "自定义招呼 Python开发"
        g2 = generate_greeting("Python开发", "测试公司", template="{company}招{job_title}？")
        assert "测试公司" in g2 and "Python开发" in g2

    def test_generate_greeting_fallback_when_template_empty(self, test_db):
        """空模板（含 settings 里有空值）应回退到默认。"""
        from boss_app.models.settings import set_setting
        set_setting("greeting_template", "")
        from boss_app.services.replier import generate_greeting
        g = generate_greeting("AI工程师", "未来公司")
        assert "AI工程师" in g
        assert len(g) > 0


# ══════════════════════════════════════
#  resume_parser.py
# ══════════════════════════════════════

class TestResumeParser:
    def test_extract_text_from_bytes_txt(self):
        from boss_app.services.resume_parser import extract_text_from_bytes
        content = "姓名：张三\nPython开发工程师\n3年经验".encode("utf-8")
        text = extract_text_from_bytes(content, "resume.txt")
        assert "张三" in text
        assert "Python" in text

    def test_extract_text_from_bytes_gbk(self):
        from boss_app.services.resume_parser import extract_text_from_bytes
        content = "姓名：李四\nJava开发".encode("gbk")
        text = extract_text_from_bytes(content, "resume.txt")
        assert "李四" in text

    def test_extract_text_from_bytes_unknown_ext(self):
        from boss_app.services.resume_parser import extract_text_from_bytes
        content = "some text".encode("utf-8")
        text = extract_text_from_bytes(content, "resume.xyz")
        assert "some text" in text

    def test_summarize_resume_empty(self):
        from boss_app.services.resume_parser import summarize_resume
        assert summarize_resume("") == ""
        assert summarize_resume("   ") == ""

    def test_summarize_resume_skills(self):
        from boss_app.services.resume_parser import summarize_resume
        text = "熟练掌握Python、Docker、Kubernetes，有MySQL和Redis使用经验"
        summary = summarize_resume(text)
        assert "Python" in summary
        assert "Docker" in summary
        assert "MySQL" in summary

    def test_summarize_resume_education(self):
        from boss_app.services.resume_parser import summarize_resume
        text = "北京大学计算机科学与技术专业本科毕业，5年工作经验"
        summary = summarize_resume(text)
        assert "北京大学" in summary or "本科" in summary

    def test_summarize_resume_years(self):
        from boss_app.services.resume_parser import summarize_resume
        text = "5年以上工作经验，熟练Python开发"
        summary = summarize_resume(text)
        assert "5年" in summary

    def test_summarize_resume_truncates(self):
        from boss_app.services.resume_parser import summarize_resume
        text = "技能: " + "Python " * 500
        summary = summarize_resume(text, max_chars=100)
        assert len(summary) <= 104  # 100 + "..."

    def test_parse_resume_file_txt(self):
        from boss_app.services.resume_parser import parse_resume_file
        content = "张三\nPython开发\n3年经验\n项目：AI聊天机器人".encode("utf-8")
        result = parse_resume_file(content, "resume.txt")
        assert result["filename"] == "resume.txt"
        assert result["text_length"] > 0
        assert len(result["summary"]) > 0

    def test_parse_resume_file_empty(self):
        from boss_app.services.resume_parser import parse_resume_file
        result = parse_resume_file(b"", "empty.txt")
        assert result["text_length"] == 0
        assert result["summary"] == ""
