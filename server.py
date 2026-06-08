import sys
import io
import re
import json
import time
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import pdfplumber
from openai import OpenAI
import config

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
app.secret_key = config.SECRET_KEY
client = None


def print_error(msg):
    print("\n" + "!" * 60)
    print("❌ 配置错误")
    print("!" * 60)
    print(msg)
    print("!" * 60 + "\n")


def check_config():
    if not getattr(config, "API_KEY", "") or config.API_KEY == "PASTE_KEY_HERE":
        print_error("请先设置环境变量 OPENROUTER_API_KEY。不要把 API Key 写死在代码里或粘贴到聊天窗口。")
        sys.exit(1)
    if not config.API_KEY.startswith("sk-or-v1-"):
        print_error("API Key 格式不对。OpenRouter Key 应该以 sk-or-v1- 开头。")
        sys.exit(1)
    if getattr(config, "API_BASE", "") != "https://openrouter.ai/api/v1":
        print_error("API_BASE 应为 https://openrouter.ai/api/v1")
        sys.exit(1)


def read_file(path):
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def current_date():
    return datetime.now().strftime("%Y-%m-%d")


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not config.APP_PASSWORD or session.get("authenticated"):
            return func(*args, **kwargs)
        if request.path.startswith("/api/"):
            return jsonify({"error": "请先登录后再使用。"}), 401
        return redirect(url_for("login"))
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if not config.APP_PASSWORD:
        return redirect(url_for("index"))
    error = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == config.APP_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        error = "密码不正确"
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>登录 · CEO 面试副驾驶</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: linear-gradient(135deg, #f5f7fb 0%, #eef4fb 100%); color: #2c3e50; padding: 24px; }}
    .login-card {{ width: 100%; max-width: 420px; background: #fff; border-radius: 18px; padding: 32px; box-shadow: 0 12px 40px rgba(44,62,80,0.12); border: 1px solid #edf1f5; }}
    h1 {{ font-size: 24px; margin-bottom: 8px; }}
    p {{ color: #718096; font-size: 14px; margin-bottom: 22px; line-height: 1.7; }}
    label {{ display: block; font-size: 13px; margin-bottom: 8px; color: #4a5568; font-weight: 600; }}
    input {{ width: 100%; border: 1px solid #d9e2ec; border-radius: 10px; padding: 12px 14px; font-size: 15px; outline: none; }}
    input:focus {{ border-color: #3498db; box-shadow: 0 0 0 3px rgba(52,152,219,0.12); }}
    button {{ width: 100%; margin-top: 16px; border: none; background: #3498db; color: #fff; border-radius: 10px; padding: 12px; font-size: 15px; font-weight: 700; cursor: pointer; }}
    button:hover {{ background: #2980b9; }}
    .error {{ margin-top: 14px; color: #c0392b; font-size: 13px; }}
  </style>
</head>
<body>
  <form class="login-card" method="post">
    <h1>🎯 CEO 面试副驾驶</h1>
    <p>该系统包含候选人隐私和公司面试标准，请输入访问密码。</p>
    <label>访问密码</label>
    <input type="password" name="password" autofocus>
    <button type="submit">进入系统</button>
    <div class="error">{error}</div>
  </form>
</body>
</html>
"""


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def extract_candidate_name(markdown):
    patterns = [
        r"^#\s*([^\n#：:|]+)",
        r"姓名[：:]\s*([^\n，,；;\s]+)",
        r"候选人姓名[：:]\s*([^\n，,；;\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, markdown or "", re.MULTILINE)
        if match:
            name = match.group(1).strip()
            if name and name not in {"候选人", "未提供", "（未提供）"}:
                return name
    return "候选人"


def generate_formal_jd(raw_description):
    prompt = f"""
你是一位资深招聘负责人。请把用户输入的岗位描述整理成一份正式、清晰、可用于候选人适配度评估的 JD。

## 当前日期
{current_date()}

## 用户输入的岗位描述
{raw_description}

## 输出要求
1. 不要编造公司未提供的硬性条件；如果信息缺失，写“待补充”。
2. 重点服务于后续人才评估，明确职责、能力要求、加分项、风险点和一票否决。
3. 用 Markdown 输出。

## 输出格式
# 正式岗位描述

## 岗位定位

## 核心职责

## 必备能力

## 加分项

## 关键业务场景

## 本岗位特殊权重与一票否决建议

## 用于面试验证的重点
"""
    return call_llm(prompt)


def log_usage(usage):
    if not usage:
        return
    prompt_tokens = getattr(usage, "prompt_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", 0)
    total_tokens = getattr(usage, "total_tokens", 0)
    # Claude Sonnet 4.x 参考价: Input $3/MTok, Output $15/MTok
    cost = prompt_tokens * 0.000003 + completion_tokens * 0.000015
    print(f"\n[Token Usage] 输入: {prompt_tokens} | 输出: {completion_tokens} | 总计: {total_tokens} | 预估费用: ${cost:.4f}\n")


def get_client():
    global client
    if client is None:
        if not getattr(config, "API_KEY", ""):
            raise RuntimeError("请先设置环境变量 OPENROUTER_API_KEY。")
        client = OpenAI(api_key=config.API_KEY, base_url=config.API_BASE)
    return client


def call_llm(prompt):
    last_error = None
    for attempt in range(2):
        try:
            print(f"[LLM] attempt={attempt + 1} prompt_chars={len(prompt)} model={config.MODEL}")
            response = get_client().chat.completions.create(
                model=config.MODEL,
                max_tokens=config.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                extra_headers={
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "CEO Interview Copilot",
                },
            )
            log_usage(response.usage)
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"[LLM ERROR] attempt={attempt + 1} type={type(e).__name__} error={str(e)}")
            error_msg = str(e).lower()
            if isinstance(e, json.JSONDecodeError) or "expecting value" in error_msg:
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise RuntimeError("OpenRouter 返回了异常或不完整响应，请稍后重试。如果反复出现，可能是输入内容过长或上游服务临时异常。")
            if "401" in error_msg or "authentication" in error_msg or "api key" in error_msg:
                raise RuntimeError("OpenRouter API Key 无效，请检查 config.py 中的 API_KEY。")
            if "quota" in error_msg or "credit" in error_msg or "billing" in error_msg or "insufficient" in error_msg:
                raise RuntimeError("OpenRouter 账户额度不足或计费异常，请检查 OpenRouter 余额。")
            if "rate" in error_msg or "429" in error_msg:
                raise RuntimeError("调用频率过高，请稍后重试。")
            if "timeout" in error_msg or "connection" in error_msg or "network" in error_msg:
                raise RuntimeError("连接 OpenRouter 失败，请检查网络。")
            break
    raise RuntimeError(f"LLM 调用失败：{str(last_error)}")


def parse_pdf(file_stream):
    text_blocks = []
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_blocks.append(text)
    return "\n\n".join(text_blocks)


def parse_docx(file_stream):
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("缺少 Word 解析依赖，请运行：pip3 install -r requirements.txt") from exc
    document = Document(file_stream)
    parts = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def parse_image(file_stream):
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("缺少图片 OCR 依赖，请运行：pip3 install -r requirements.txt，并确保本机已安装 tesseract。") from exc
    image = Image.open(file_stream)
    return pytesseract.image_to_string(image, lang="chi_sim+eng")


def parse_interview_file(file_storage):
    filename = file_storage.filename or "未命名文件"
    suffix = Path(filename).suffix.lower()
    data = file_storage.read()
    stream = io.BytesIO(data)
    if suffix == ".pdf":
        text = parse_pdf(stream)
    elif suffix == ".docx":
        text = parse_docx(stream)
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}:
        text = parse_image(stream)
    elif suffix in {".txt", ".md"}:
        text = data.decode("utf-8", errors="ignore")
    elif suffix == ".doc":
        raise RuntimeError(f"{filename} 是旧版 .doc 格式，暂不支持。请另存为 .docx 后上传。")
    else:
        raise RuntimeError(f"{filename} 的格式暂不支持，请上传 PDF、Word(.docx)、图片、TXT 或 Markdown。")
    if not text.strip():
        raise RuntimeError(f"{filename} 未解析出文字，可能是扫描件或图片 OCR 失败。")
    return f"## 文件：{filename}\n\n{text.strip()}"


def collect_interview_notes():
    manual_notes = ""
    file_notes = []
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        manual_notes = request.form.get("interview_notes", "")
        for file_storage in request.files.getlist("interview_files"):
            if file_storage and file_storage.filename:
                file_notes.append(parse_interview_file(file_storage))
    else:
        data = request.get_json(silent=True) or {}
        manual_notes = data.get("interview_notes", "")
    parts = []
    if manual_notes.strip():
        parts.append("## 手动输入\n\n" + manual_notes.strip())
    parts.extend(file_notes)
    return "\n\n---\n\n".join(parts)


def render(template_name, variables):
    template = read_file(Path("prompts") / template_name)
    if not template:
        raise RuntimeError(f"找不到 Prompt 模板：prompts/{template_name}")
    for key, value in variables.items():
        template = template.replace("{" + key + "}", value or "（暂无）")
    return template


def save_output(candidate_name, filename, content):
    safe_name = "".join(c for c in candidate_name if c not in r'\\/:*?"<>|').strip() or "候选人"
    date = current_date()
    folder = Path("outputs") / f"{date}_{safe_name}"
    folder.mkdir(parents=True, exist_ok=True)
    output_path = folder / filename
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)


@app.route("/")
@login_required
def index():
    return send_from_directory(".", "index.html")


@app.route("/assets/<path:filename>")
@login_required
def assets(filename):
    return send_from_directory("assets", filename)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "model": config.MODEL, "current_date": current_date()})


@app.route("/api/generate_jd", methods=["POST"])
@login_required
def api_generate_jd():
    data = request.get_json(silent=True) or {}
    raw_description = data.get("raw_description", "")
    if not raw_description.strip():
        return jsonify({"error": "岗位描述不能为空"}), 400
    try:
        return jsonify({"markdown": generate_formal_jd(raw_description)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/parse_resume", methods=["POST"])
@login_required
def api_parse_resume():
    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    file = request.files["file"]
    candidate_name = request.form.get("candidate_name", "候选人")
    try:
        raw_text = parse_pdf(file.stream)
        if not raw_text.strip():
            return jsonify({"error": "PDF 解析为空，可能是扫描件或图片型 PDF。"}), 400
        prompt = render("00_resume_parse.md", {
            "RAW_TEXT": raw_text,
            "候选人姓名": candidate_name,
            "CURRENT_DATE": current_date(),
        })
        result = call_llm(prompt)
        extracted_name = extract_candidate_name(result)
        save_output(extracted_name, "01_简历.md", result)
        return jsonify({"markdown": result, "candidate_name": extracted_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pre_interview", methods=["POST"])
@login_required
def api_pre_interview():
    data = request.get_json(silent=True) or {}
    candidate_name = data.get("candidate_name", "候选人")
    resume_md = data.get("resume_md", "")
    jd = data.get("jd", "")
    weights = data.get("weights", "")
    department_style = data.get("department_style", "")
    if not resume_md or not jd:
        return jsonify({"error": "简历或 JD 不能为空"}), 400
    try:
        prompt = render("01_pre_interview.md", {
            "JD": jd,
            "RESUME": resume_md,
            "AMIRO_STANDARD": read_file("standards/AMIRO_talent_standard.md"),
            "POSITION_WEIGHTS": weights,
            "DEPARTMENT_STYLE": department_style,
            "候选人姓名": candidate_name,
            "CURRENT_DATE": current_date(),
        })
        result = call_llm(prompt)
        save_output(candidate_name, "02_面试前作战图.md", result)
        return jsonify({"markdown": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview_plan", methods=["POST"])
@login_required
def api_interview_plan():
    data = request.get_json(silent=True) or {}
    candidate_name = data.get("candidate_name", "候选人")
    resume_md = data.get("resume_md", "")
    jd = data.get("jd", "")
    weights = data.get("weights", "")
    department_style = data.get("department_style", "")
    pre_report = data.get("pre_report", "")
    if not resume_md or not pre_report:
        return jsonify({"error": "简历或作战图不能为空"}), 400
    try:
        prompt = render("02_interview_plan.md", {
            "JD": jd,
            "RESUME": resume_md,
            "AMIRO_STANDARD": read_file("standards/AMIRO_talent_standard.md"),
            "POSITION_WEIGHTS": weights,
            "DEPARTMENT_STYLE": department_style,
            "PRE_INTERVIEW_REPORT": pre_report,
            "候选人姓名": candidate_name,
            "CURRENT_DATE": current_date(),
        })
        result = call_llm(prompt)
        save_output(candidate_name, "03_面试追问卡.md", result)
        return jsonify({"markdown": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/post_interview_eval", methods=["POST"])
@login_required
def api_post_interview_eval():
    data = request.form if request.content_type and request.content_type.startswith("multipart/form-data") else (request.get_json(silent=True) or {})
    candidate_name = data.get("candidate_name", "候选人")
    resume_md = data.get("resume_md", "")
    jd = data.get("jd", "")
    weights = data.get("weights", "")
    department_style = data.get("department_style", "")
    pre_report = data.get("pre_report", "")
    interview_plan = data.get("interview_plan", "")
    try:
        interview_notes = collect_interview_notes()
        if not resume_md or not pre_report or not interview_plan or not interview_notes:
            return jsonify({"error": "简历、作战图、追问卡或面试记录不能为空"}), 400
        prompt = render("03_post_interview_eval.md", {
            "JD": jd,
            "RESUME": resume_md,
            "AMIRO_STANDARD": read_file("standards/AMIRO_talent_standard.md"),
            "POSITION_WEIGHTS": weights,
            "DEPARTMENT_STYLE": department_style,
            "PRE_INTERVIEW_REPORT": pre_report,
            "INTERVIEW_PLAN": interview_plan,
            "INTERVIEW_NOTES": interview_notes,
            "候选人姓名": candidate_name,
            "CURRENT_DATE": current_date(),
        })
        result = call_llm(prompt)
        save_output(candidate_name, "04_面试后评判.md", result)
        return jsonify({"markdown": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import threading
    import time
    import webbrowser

    port = getattr(config, "PORT", 5000)
    if not getattr(config, "API_KEY", ""):
        print_error("当前没有设置 OPENROUTER_API_KEY，页面可以打开，但 AI 生成功能会提示缺少 Key。")

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()
    print("\n" + "=" * 60)
    print("  🎯 CEO 面试副驾驶 - 本地版已启动")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  使用模型: {config.MODEL}")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=port, debug=False)
