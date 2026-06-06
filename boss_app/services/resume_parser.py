"""简历解析服务：从 PDF/Word 文本提取关键信息并生成摘要。

支持的输入：
- PDF: pdfplumber（首选，提取更准确）
- Word: 暂不实现，可后续扩展
- 纯文本: 直接返回

提取流程：
1. 解析文件为纯文本
2. 拼接所有页
3. 智能截断（避免超出 LLM 上下文）
"""
import re
from io import BytesIO
from pathlib import Path


def extract_text_from_pdf(source: str | Path | BytesIO) -> str:
    """从 PDF 文件或字节流提取纯文本。"""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


def extract_text_from_bytes(content: bytes, filename: str = "") -> str:
    """从字节流提取文本（按扩展名分发）。"""
    suffix = Path(filename).suffix.lower() if filename else ""

    if suffix == ".pdf":
        return extract_text_from_pdf(BytesIO(content))

    # 纯文本 / 未知格式：尝试解码
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def summarize_resume(text: str, max_chars: int = 1500) -> str:
    """把简历文本压缩为 LLM 评分用的摘要。

    保留关键信息：技能关键词、项目经验、学历、工作年限。
    """
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()

    # 关键模式 — 合并为单次 regex 匹配
    skill_keywords = [
        "Python", "Java", "Go", "Rust", "C++", "JavaScript", "TypeScript",
        "Docker", "K8s", "Kubernetes", "Linux", "MySQL", "PostgreSQL", "Redis",
        "MongoDB", "AWS", "阿里云", "GCP", "Azure",
        "React", "Vue", "FastAPI", "Flask", "Django", "Spring", "Node",
        "LangChain", "LLM", "RAG", "Agent", "Prompt",
        "DevOps", "CI/CD", "Git", "Jenkins", "GitLab", "GitHub Actions",
        "机器学习", "深度学习", "NLP", "推荐系统", "数据分析",
    ]
    _skill_pattern = re.compile("|".join(re.escape(kw) for kw in skill_keywords), re.IGNORECASE)
    skills_found = {m.group() for m in _skill_pattern.finditer(text)}

    # 提取教育（粗略匹配"大学/学院" + 学位）
    edu_match = re.search(
        r"([一-鿿]{2,15}(?:大学|学院|研究所))[^。]{0,30}?(本科|硕士|博士|大专|MBA|PhD|Master|Bachelor)",
        text,
    )
    education = edu_match.group(0) if edu_match else ""

    # 提取工作年限
    years_match = re.search(r"(\d+)\s*年(?:以上)?(?:经验|工作)", text)
    years = years_match.group(0) if years_match else ""

    # 提取项目经验（找"项目"/"Project" 关键词附近的句子）
    project_snippets = []
    for kw in ["项目经验", "项目经历", "Project", "工作经历", "工作经验"]:
        idx = text.find(kw)
        if idx > 0:
            snippet = text[idx:idx + 200]
            project_snippets.append(snippet)
            if len(project_snippets) >= 2:
                break

    parts = []
    if skills_found:
        parts.append("技能: " + ", ".join(sorted(skills_found)))
    if education:
        parts.append("教育: " + education)
    if years:
        parts.append("经验: " + years)
    parts.extend(project_snippets)

    summary = "\n".join(parts)

    if len(summary) > max_chars:
        summary = summary[:max_chars] + "..."

    return summary


def clean_resume_text(text: str) -> str:
    """清洗简历文本：去除多余空白，保留段落结构。"""
    if not text:
        return ""
    # 合并连续空行为单行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去除行首尾多余空格
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def parse_resume_file(content: bytes, filename: str = "") -> dict:
    """解析简历文件，返回原文 + 摘要。"""
    text = extract_text_from_bytes(content, filename)
    cleaned = clean_resume_text(text)
    summary = summarize_resume(text)
    return {
        "filename": filename,
        "text_length": len(text),
        "full_text": cleaned,
        "text_preview": cleaned[:200] if cleaned else "",
        "summary": summary,
    }
