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


def summarize_resume(text: str, max_chars: int = 2000) -> str:
    """把简历文本压缩为 LLM 评分用的摘要。

    保留关键信息：求职目标、技能、教育、项目经验（完整描述+职责）。
    """
    if not text:
        return ""

    # 不压缩空格，保留原始结构用于提取
    lines = text.split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # 关键模式 — 技能关键词
    skill_keywords = [
        "Python", "Java", "Go", "Rust", "C++", "JavaScript", "TypeScript",
        "Docker", "K8s", "Kubernetes", "Linux", "CentOS", "Ubuntu", "Debian",
        "MySQL", "PostgreSQL", "Redis", "MongoDB", "SQLite", "Nginx", "Apache",
        "AWS", "阿里云", "GCP", "Azure", "Jenkins", "GitLab", "GitHub Actions",
        "React", "Vue", "FastAPI", "Flask", "Django", "Spring", "Node", "Express",
        "LangChain", "LLM", "RAG", "Agent", "Prompt", "FAISS", "OCR",
        "DevOps", "CI/CD", "Git", "SVN", "Ansible", "Terraform",
        "机器学习", "深度学习", "NLP", "推荐系统", "数据分析", "大模型",
        "PaddleOCR", "Selenium", "Playwright", "Scrapy",
        "Pydantic", "SSE", "WebSocket", "RESTful", "gRPC",
    ]
    _skill_pattern = re.compile("|".join(re.escape(kw) for kw in skill_keywords), re.IGNORECASE)
    skills_found = {m.group() for m in _skill_pattern.finditer(text)}

    # 提取求职目标（通常在简历开头）
    job_target = ""
    for line in lines[:15]:
        # 匹配 "求职岗位：XXX" 格式
        m = re.search(r"(?:求职意向|求职目标|求职岗位|目标岗位|应聘岗位|意向岗位)[：:]\s*(.+)", line)
        if m:
            job_target = m.group(1).strip()
            break
        # 匹配独立的岗位名称行
        if re.match(r"^[一-鿿]{2,10}(?:工程师|开发|运维|测试|架构师|实习生|设计师)$", line.strip()):
            job_target = line.strip()
            break

    # 提取教育信息
    education = ""
    for i, line in enumerate(lines):
        if any(kw in line for kw in ["教育背景", "教育经历", "学历", "Education"]):
            # 取后续几行
            edu_lines = [line]
            for j in range(i+1, min(i+4, len(lines))):
                if lines[j] and not any(kw in lines[j] for kw in ["项目", "工作", "技能", "实习"]):
                    edu_lines.append(lines[j])
                else:
                    break
            education = " ".join(edu_lines)
            break
        # 直接匹配学校名
        if re.search(r"[一-鿿]{2,15}(?:大学|学院|学校)", line):
            education = line
            # 检查下一行是否有学位信息
            if i+1 < len(lines) and re.search(r"(?:本科|硕士|博士|大专|学士)", lines[i+1]):
                education += " " + lines[i+1]
            break

    # 提取工作年限
    years_match = re.search(r"(\d+)\s*年(?:以上)?(?:经验|工作|开发)", text)
    years = years_match.group(0) if years_match else ""

    # 提取项目经验（完整提取每个项目）
    projects = []
    in_project = False
    current_project = []
    project_keywords = ["项目经验", "项目经历", "项目名称", "Project", "工作经历", "工作经验"]

    for i, line in enumerate(lines):
        is_project_header = False
        # 检查是否是项目标题行
        if any(kw in line for kw in project_keywords):
            in_project = True
            is_project_header = True
            if current_project:
                projects.append("\n".join(current_project))
                current_project = []
            current_project.append(line)
            continue

        if in_project:
            # 检查是否是新段落（技能、教育等）
            if any(kw in line for kw in ["技能", "专业技能", "技术栈", "教育背景", "自我评价", "证书", "荣誉"]):
                if current_project:
                    projects.append("\n".join(current_project))
                    current_project = []
                in_project = False
                continue

            # 项目标题特征：包含"项目"或技术栈
            if re.match(r"^[\d.]*\s*项目", line) or (len(line) < 50 and "项目" in line):
                if current_project and len("\n".join(current_project)) > 50:
                    projects.append("\n".join(current_project))
                    current_project = []
                current_project.append(line)
                continue

            current_project.append(line)

            # 限制每个项目的长度
            if len("\n".join(current_project)) > 500:
                projects.append("\n".join(current_project))
                current_project = []
                in_project = False

    if current_project:
        projects.append("\n".join(current_project))

    # 组装摘要
    parts = []
    if job_target:
        parts.append("求职目标: " + job_target)
    if skills_found:
        parts.append("技能: " + ", ".join(sorted(skills_found)))
    if education:
        parts.append("教育: " + education)
    if years:
        parts.append("经验: " + years)

    # 添加项目经验（最多3个，保留完整描述）
    if projects:
        parts.append("\n项目经验:")
        for p in projects[:3]:
            # 清理项目文本
            p_clean = re.sub(r"\s+", " ", p).strip()
            if len(p_clean) > 300:
                p_clean = p_clean[:300] + "..."
            parts.append(p_clean)

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
