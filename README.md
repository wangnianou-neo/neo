# CEO 面试副驾驶

用于上传候选人简历、生成正式 JD、输出简历分析、面试前作战图、面试追问卡和面试后评判报告。

## 功能

- **简历解析**：上传简历 PDF，自动整理候选人信息并提取姓名。
- **正式 JD 生成**：输入岗位简述后，由 AI 生成正式 JD，可继续手动编辑。
- **面试前作战图**：结合 JD、人才标准、岗位权重、部门风格生成风险和验证重点。
- **面试追问卡**：生成结构化面试问题。
- **面试后评判**：支持粘贴面试记录，也支持上传多份 PDF、Word、图片、TXT、Markdown 附件。
- **导出 PDF**：支持导出当前报告或全部报告。

## 技术栈

- **后端**：Python + Flask
- **线上启动**：Gunicorn
- **前端**：HTML + JavaScript
- **LLM**：OpenRouter
- **文档解析**：pdfplumber、python-docx、Pillow、pytesseract

## 本地运行

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置环境变量：

```bash
export OPENROUTER_API_KEY="sk-or-v1-your-key-here"
```

也可以复制 `.env.example` 后手动加载环境变量。

3. 启动服务：

```bash
python server.py
```

4. 访问：

```text
http://localhost:5000
```

## 线上部署到 Render

1. 把项目上传到 GitHub 私有仓库。
2. 登录 Render。
3. New → Blueprint，选择该仓库。
4. Render 会读取 `render.yaml`。
5. 在环境变量里填写：

```text
OPENROUTER_API_KEY=你的 OpenRouter Key
APP_PASSWORD=同事访问网站时使用的密码
```

6. 部署完成后，Render 会提供一个 HTTPS 地址，可直接发给同事使用。

## 绑定域名

内测阶段可以直接使用 Render 提供的域名。

正式使用时，可以绑定公司子域名，例如：

```text
interview.your-company.com
```

在 Render 服务设置中添加 Custom Domain，然后到域名服务商处配置 DNS。

## 安全注意事项

- **不要把 OpenRouter API Key 写死在代码里。**
- **不要把 API Key 提交到公开仓库。**
- 建议使用 GitHub 私有仓库部署。
- 线上部署时建议设置 `APP_PASSWORD`，系统会要求访问者先登录。
- 上传文件可能包含候选人隐私信息，应限制访问人员。

## 环境变量

| 变量 | 说明 |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API Key，必填 |
| `OPENROUTER_API_BASE` | 默认 `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | 默认 `anthropic/claude-sonnet-4.5` |
| `MAX_TOKENS` | 默认 `8000` |
| `PORT` | 本地端口，默认 `5000` |
| `APP_PASSWORD` | 外网访问密码，建议线上必填 |
| `SECRET_KEY` | Flask Session 密钥，线上必须使用随机值 |

## API 路由

- `GET /`
- `GET /api/health`
- `POST /api/generate_jd`
- `POST /api/parse_resume`
- `POST /api/pre_interview`
- `POST /api/interview_plan`
- `POST /api/post_interview_eval`

## 输出目录

报告会自动保存到：

```text
outputs/日期_候选人姓名/
```
