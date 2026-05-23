from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
import json
import httpx
import asyncio
import re

load_dotenv()

app = FastAPI(title="星途简历 - AI后端", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("DOUBAO_API_KEY")
MODEL_ID = os.getenv("DOUBAO_MODEL_ID", "doubao-pro-32k-241215")
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# ========== 数据模型 ==========

class ExperienceItem(BaseModel):
    id: int
    type: str
    role: str
    company: str
    date: str
    content: str

class StarResult(BaseModel):
    experienceId: int
    experienceType: str
    role: str
    company: str
    date: str
    focus: str
    S: str
    T: str
    A: str
    R: str

class SuggestionItem(BaseModel):
    type: str
    icon: str
    label: str
    subject: str
    issue: str
    direction: str
    example: str

class SuggestionsResponse(BaseModel):
    title: str
    isExcellent: bool
    suggestions: List[SuggestionItem]

# ========== 新增：完整字段对齐前端 ==========

class OptimizeRequest(BaseModel):
    targetJob: str = ""
    expectedCity: str = ""
    jobType: str = "fulltime"
    name: str = ""
    phone: str = ""
    email: str = ""
    photo: str = ""
    github: str = ""
    blog: str = ""
    portfolio: str = ""
    personalWebsite: str = ""
    school: str = ""
    major: str = ""
    educationLevel: str = "undergraduate"
    graduation: str = ""
    gpa: str = ""
    courses: str = ""
    skills: str = ""
    certificates: str = ""
    selfEvaluation: str = ""
    jd: str = ""
    templateId: str = "template_15"
    experiences: List[ExperienceItem]

class OptimizeResponse(BaseModel):
    results: List[StarResult]

class SuggestionsRequest(BaseModel):
    experience: ExperienceItem
    jd: str = ""
    targetJob: str = ""
    skills: str = ""

class GenerateResumeRequest(BaseModel):
    targetJob: str = ""
    expectedCity: str = ""
    jobType: str = "fulltime"
    name: str = ""
    phone: str = ""
    email: str = ""
    photo: str = ""
    github: str = ""
    blog: str = ""
    portfolio: str = ""
    personalWebsite: str = ""
    school: str = ""
    major: str = ""
    educationLevel: str = "undergraduate"
    graduation: str = ""
    gpa: str = ""
    courses: str = ""
    skills: str = ""
    certificates: str = ""
    selfEvaluation: str = ""
    jd: str = ""
    templateId: str = "template_15"
    experiences: List[ExperienceItem]
    starResults: List[StarResult]
    suggestions: Optional[List[dict]] = None

class GenerateResumeResponse(BaseModel):
    html: str
    success: bool

# ========== 模板风格映射 ==========

TEMPLATE_STYLES = {
    "template_01": {"name": "经典商务单栏", "style_desc": "简约商务风，ATS兼容性100%，适合财务/HR/行政/管培生", "color": "#1a365d", "layout": "单栏", "font": "微软雅黑/Arial"},
    "template_02": {"name": "互联网技术双栏", "style_desc": "互联网风，技术岗专属，技能前置展示，左右分栏(3:7)，适合Java/前端/后端/算法", "color": "#2563eb", "layout": "左右分栏(3:7)", "font": "Inter/思源黑体"},
    "template_03": {"name": "金融投行精英", "style_desc": "简约商务风，极致专业，信息密度极高，单栏紧凑，适合投行/研究员/PE/VC/四大", "color": "#000000", "layout": "单栏紧凑", "font": "Times New Roman/宋体"},
    "template_04": {"name": "产品经理思维", "style_desc": "互联网风，突出产品思维和数据成果，适合产品经理/产品运营/B端产品", "color": "#f97316", "layout": "单栏", "font": "现代无衬线字体"},
    "template_05": {"name": "运营增长数据", "style_desc": "互联网风，数据驱动，增长指标突出，单栏+数据卡片，适合运营/增长/新媒体/营销", "color": "#10b981", "layout": "单栏+数据卡片", "font": "清晰无衬线字体"},
    "template_06": {"name": "国企央企正式", "style_desc": "国企/体制内风，政治面貌前置，稳重正式，表格化单栏，适合公务员/事业单位/国企/央企", "color": "#dc2626", "layout": "表格化单栏", "font": "宋体/仿宋"},
    "template_07": {"name": "创意设计作品", "style_desc": "创意设计风，设计感第一，作品展示充分，左侧信息栏+右侧作品区，适合UI/UX/平面/视觉设计", "color": "#8b5cf6", "layout": "左侧信息栏+右侧作品区", "font": "多种字体组合"},
    "template_08": {"name": "学术科研专业", "style_desc": "学术科研风，LaTeX风格，论文为核心，学术论文式单栏，适合博士申请/高校教师/研究员", "color": "#000000", "layout": "学术论文式单栏", "font": "Times New Roman/Computer Modern"},
    "template_09": {"name": "市场营销品牌", "style_desc": "创意商务风，Campaign案例突出，品牌思维，现代商务单栏，适合品牌经理/市场推广/公关/广告", "color": "#ef4444", "layout": "现代商务单栏", "font": "专业商务字体"},
    "template_10": {"name": "医疗健康专业", "style_desc": "专业严谨风，资质证书前置，临床经验，规整单栏，适合医生/护士/医药代表/医疗行政", "color": "#059669", "layout": "规整单栏", "font": "清晰标准字体"},
    "template_11": {"name": "制造业工程", "style_desc": "专业技术风，技术认证突出，产线经验，结构化单栏，适合工艺/机械工程师/生产管理/质控", "color": "#1e40af", "layout": "结构化单栏", "font": "标准技术文档字体"},
    "template_12": {"name": "教育培训行业", "style_desc": "专业亲和风，教学成果突出，亲和力强，整洁单栏，适合教师/教研/课程设计/培训师", "color": "#3b82f6", "layout": "整洁单栏", "font": "清晰易读字体"},
    "template_13": {"name": "行政人事管理", "style_desc": "稳重商务风，协调能力突出，流程优化，清晰规整单栏，适合行政/HR/办公室主任", "color": "#4b5563", "layout": "清晰规整单栏", "font": "标准商务字体"},
    "template_14": {"name": "咨询管理精英", "style_desc": "高端商务风，麦肯锡风格，极度结构化，高密度单栏，适合管理咨询/战略咨询/IT咨询", "color": "#1e3a8a", "layout": "高密度单栏", "font": "Times New Roman/宋体"},
    "template_15": {"name": "应届生校招全能", "style_desc": "简约商务风，应届生专属，ATS友好，标准单栏，适合应届生校招/通用/无明确方向", "color": "#3b82f6", "layout": "标准单栏", "font": "微软雅黑"},
    "template_16": {"name": "社招3-5年进阶", "style_desc": "专业商务风，职业成长清晰，能力层级明确，经历排序单栏，适合3-5年经验/主管/高级专员", "color": "#0369a1", "layout": "经历排序单栏", "font": "成熟稳重字体"},
    "template_17": {"name": "社招5年+管理", "style_desc": "高端商务风，管理能力清晰，战略高度，大气双栏/单栏，适合5年+经验/经理/总监", "color": "#1e40af", "layout": "大气双栏/单栏", "font": "权威感字体"},
    "template_18": {"name": "转行跨界桥梁", "style_desc": "能力迁移风，可迁移能力前置，衔接新旧职业，能力模块前置单栏，适合跨行业求职/职业转型", "color": "#7c3aed", "layout": "能力模块前置单栏", "font": "专业清晰字体"},
}

# ========== 调用豆包 AI ==========

async def call_doubao_optimize(exp: ExperienceItem, jd: str, school: str, major: str) -> StarResult:
    system_prompt = """你是一位拥有10年经验的资深HR总监和简历优化专家。
你的任务是根据用户提供的原始经历描述，使用 STAR 法则进行专业优化。

【STAR 法则说明】
- S (Situation/情境): 描述当时的背景、环境、面临的挑战
- T (Task/任务): 明确你的具体职责、目标、需要解决的问题
- A (Action/行动): 详细说明你采取的具体措施、方法、使用的技能
- R (Result/结果): 用数据量化最终成果，如提升了XX%、完成了XX、获得了XX

【重要规则】
1. 必须基于用户提供的真实经历，严禁虚构数据或编造成果
2. 每个要素控制在 50-80 字，语言简洁专业
3. 结果部分必须有具体数字
4. 输出必须是严格的 JSON 格式，不要包含 markdown 代码块标记

【输出格式】
{
    "S": "情境描述...",
    "T": "任务描述...",
    "A": "行动描述...",
    "R": "结果描述（必须包含数字）..."
}"""

    user_prompt = f"""【经历类型】{exp.type}
【职位/角色】{exp.role}
【公司/机构】{exp.company}
【时间段】{exp.date}
【原始经历描述】{exp.content}
【学校背景】{school} {major}
【目标岗位JD】{jd if jd else "未提供"}

请按 STAR 法则优化这段经历，只输出 JSON 格式，不要添加任何其他文字。"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            BASE_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL_ID,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 800
            }
        )
        result = response.json()
        ai_content = clean_json_response(result["choices"][0]["message"]["content"])
        star_data = json.loads(ai_content)

        focus_map = {
            "internship": "突出工作成果与业务能力",
            "campus": "突出技术能力与问题解决",
            "club": "突出组织协调与领导力",
            "parttime": "突出责任心与执行力",
            "research": "突出科研能力与学术成果"
        }

        return StarResult(
            experienceId=exp.id,
            experienceType=exp.type,
            role=exp.role,
            company=exp.company,
            date=exp.date,
            focus=focus_map.get(exp.type, "综合优化"),
            S=star_data.get("S", ""),
            T=star_data.get("T", ""),
            A=star_data.get("A", ""),
            R=star_data.get("R", "")
        )

async def call_doubao_suggestions(exp: ExperienceItem, jd: str, target_job: str = "", skills: str = "") -> SuggestionsResponse:
    system_prompt = """你是一位拥有10年经验的资深HR总监和简历优化专家。
你的任务是根据用户提供的原始经历、经历类型和目标岗位JD，生成个性化、可落地的优化建议。

【分析流程】（必须在后台完成，不输出分析过程）
1. STAR法则完整性分析：检查S/T/A/R四要素覆盖情况
2. 岗位需求匹配度分析：从JD提取关键词，标记经历中未提及的技能点
3. 成果量化程度分析：识别"提升效率"、"效果很好"、"参与负责"等模糊表述
4. 经历类型适配性分析：根据类型（实习/校园项目/社团/兼职）检查特性描述
5. 个人贡献清晰度分析：检查"参与"、"协助"等弱化个人贡献的表述

【输出格式要求】
必须输出严格的JSON格式，不要包含任何markdown标记：

{
    "isExcellent": false,
    "suggestions": [
        {
            "type": "critical",
            "icon": "⚠️",
            "label": "核心问题",
            "subject": "建议标题（15字以内）",
            "issue": "【问题定位】具体指出原始经历中的问题，必须引用用户原文中的具体表述",
            "direction": "【具体修改方向】提供可操作的优化方法",
            "example": "【参考示例】基于用户实际经历优化后的表述"
        }
    ]
}

【规则】
1. 所有建议必须直接引用用户原始经历中的具体表述，禁止通用模板
2. 建议总数1-5条，按严重性排序：核心问题 > 岗位适配 > 加分项
3. 如果经历非常优秀（STAR完整、匹配度≥85%、量化≥70%、贡献清晰），isExcellent设为true，只输出2条加分项
4. 参考示例必须基于用户实际经历，不得捏造不存在的内容
5. 禁止使用"建议优化内容结构"、"建议突出核心能力"等通用表述
6. 问题定位必须精确到用户原文中的具体词语或句子"""

    user_prompt = f"""【经历类型】{exp.type}
【职位/角色】{exp.role}
【公司/机构】{exp.company}
【原始经历文本】{exp.content}
【目标岗位】{target_job if target_job else "未提供"}
【目标岗位JD】{jd if jd else "未提供"}
【已掌握技能】{skills if skills else "未提供"}

请生成个性化优化建议，只输出JSON格式。"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            BASE_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL_ID,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1500
            }
        )
        result = response.json()
        ai_content = clean_json_response(result["choices"][0]["message"]["content"])
        data = json.loads(ai_content)
        
        suggestions = []
        for item in data.get("suggestions", []):
            suggestions.append(SuggestionItem(
                type=item.get("type", "bonus"),
                icon=item.get("icon", "💡"),
                label=item.get("label", "加分项"),
                subject=item.get("subject", ""),
                issue=item.get("issue", ""),
                direction=item.get("direction", ""),
                example=item.get("example", "")
            ))
        
        is_excellent = data.get("isExcellent", False)
        count = len(suggestions)
        title = f"🎉 你的经历描述非常优秀！以下是2个可以锦上添花的小建议" if is_excellent else f"📝 你的简历个性化优化建议（共{count}条）"
        
        return SuggestionsResponse(title=title, isExcellent=is_excellent, suggestions=suggestions)

async def call_doubao_generate_resume(req: GenerateResumeRequest) -> str:
    tmpl = TEMPLATE_STYLES.get(req.templateId, TEMPLATE_STYLES["template_15"])
    
    star_text = ""
    for r in req.starResults:
        star_text += f"\n【{r.role} | {r.company} | {r.date}】\nS: {r.S}\nT: {r.T}\nA: {r.A}\nR: {r.R}\n"

    exp_text = ""
    for e in req.experiences:
        exp_text += f"\n【{e.role} | {e.company}】\n{e.content}\n"

    suggestion_text = ""
    if req.suggestions:
        for idx, group in enumerate(req.suggestions, 1):
            suggestion_text += f"\n--- 建议组{idx} ---\n"
            for s in group.get("suggestions", []):
                suggestion_text += f"- [{s.get('label','')}] {s.get('subject','')}: {s.get('direction','')}\n"

    system_prompt = f"""你是一位拥有15年经验的顶级HR总监、简历优化专家和前端设计师。
你的任务是根据用户提供的所有信息，生成一份完整、专业、可直接投递使用的简历HTML。

【当前选中的简历模板风格】
模板名称：{tmpl['name']}
风格描述：{tmpl['style_desc']}
主色调：{tmpl['color']}
布局：{tmpl['layout']}
推荐字体：{tmpl['font']}

【设计规范】
- 必须严格遵循上述模板风格，配色、布局、字体气质要与模板描述一致
- 如果是技术岗模板（如互联网双栏），技能板块要前置，使用左右分栏布局
- 如果是金融/咨询模板，信息密度要高，使用Times New Roman类字体，排版紧凑
- 如果是创意/设计模板，可以增加设计感元素，但不要过度花哨
- 如果是国企/体制内模板，风格稳重正式，使用宋体/仿宋
- 通用要求：适配A4打印，内容宽度最大210mm，内边距15mm，确保可打印在1-2页A4纸内

【内容规范】
1. 个人信息：姓名用超大字号(24px+)突出，联系方式横排，GitHub/Blog/Portfolio/个人网站做成可点击链接（如有）
2. 求职意向：目标岗位、期望城市、工作类型要清晰展示
3. 教育背景：学校、专业、时间、学历、GPA（如有）、主修课程（精简为1行）
4. 技能特长：必须展示用户填写的技能和证书，分点列出，使用熟练度描述（熟悉/掌握/了解）
5. 经历部分：必须使用优化后的STAR内容，突出数据量化成果，每条经历整合成连贯的3-4句话，不要分S/T/A/R小标题
6. 自我评价：3-4句话，针对目标岗位JD定制，如用户未填写则根据经历自动生成
7. 所有内容必须真实，基于用户提供的信息，严禁虚构任何经历或数据

【HTML规范】
1. 输出完整HTML文档片段（从<body>内的内容开始即可，不需要html/head标签，因为会嵌入到现有页面）
2. CSS使用内联style属性，确保样式不丢失
3. 使用中文，排版整齐，行高1.6，段间距合理
4. 不要包含任何JavaScript
5. 只输出HTML代码，不要任何解释、不要markdown代码块标记
6. 确保所有颜色对比度足够，打印清晰"""

    user_prompt = f"""请生成完整简历HTML内容。

【基本信息】
姓名：{req.name}
电话：{req.phone}
邮箱：{req.email}
照片：{req.photo or '未提供'}
GitHub：{req.github or '未提供'}
博客：{req.blog or '未提供'}
作品集：{req.portfolio or '未提供'}
个人网站：{req.personalWebsite or '未提供'}

【求职意向】
目标岗位：{req.targetJob or '未提供'}
期望城市：{req.expectedCity or '未提供'}
工作类型：{req.jobType or '未提供'}

【教育背景】
学校：{req.school}
专业：{req.major}
学历：{req.educationLevel}
毕业时间：{req.graduation}
GPA：{req.gpa or '未提供'}
主修课程：{req.courses or '未提供'}

【技能特长】
专业技能：{req.skills or '未提供'}
证书/奖项：{req.certificates or '未提供'}

【自我评价】
{req.selfEvaluation or '未提供，请根据经历自动生成'}

【目标岗位JD】
{req.jd or '未提供'}

【优化后的经历（STAR法则）】
{star_text}

【原始经历】
{exp_text}

【优化建议】（请确保这些建议已被采纳到简历中）
{suggestion_text}

请直接输出简历的HTML body内容（不需要<html><head>，只需要<div class="resume">...</div>这样的内容块）。"""

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            BASE_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL_ID,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.6,
                "max_tokens": 3000
            }
        )
        result = response.json()
        ai_content = result["choices"][0]["message"]["content"]
        html = clean_json_response(ai_content)
        if "<body>" in html:
            match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
            if match:
                html = match.group(1)
        return html.strip()

def clean_json_response(content: str) -> str:
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```html"):
        content = content[8:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()

# ========== API 路由 ==========

@app.post("/api/optimize", response_model=OptimizeResponse)
async def optimize_resume(req: OptimizeRequest):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API Key 未配置")
    if not req.experiences:
        raise HTTPException(status_code=400, detail="经历列表不能为空")

    tasks = [call_doubao_optimize(exp, req.jd, req.school, req.major) for exp in req.experiences]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            exp = req.experiences[i]
            valid_results.append(StarResult(
                experienceId=exp.id,
                experienceType=exp.type,
                role=exp.role,
                company=exp.company,
                date=exp.date,
                focus="综合优化（AI处理异常）",
                S=f"在{exp.company or '相关单位'}开展实践。",
                T=f"担任{exp.role}，负责核心工作任务。",
                A="运用专业技能完成各项工作。",
                R="工作顺利完成，获得认可。"
            ))
        else:
            valid_results.append(result)

    return OptimizeResponse(results=valid_results)

@app.post("/api/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(req: SuggestionsRequest):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API Key 未配置")
    if not req.experience.content or req.experience.content.strip() == "":
        raise HTTPException(status_code=400, detail="经历内容不能为空")
    return await call_doubao_suggestions(req.experience, req.jd, req.targetJob, req.skills)

@app.post("/api/generate-resume", response_model=GenerateResumeResponse)
async def generate_full_resume(req: GenerateResumeRequest):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API Key 未配置")
    if not req.name or not req.experiences:
        raise HTTPException(status_code=400, detail="姓名和经历不能为空")
    try:
        html = await call_doubao_generate_resume(req)
        return GenerateResumeResponse(html=html, success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"简历生成失败: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "model": MODEL_ID, "key_ok": bool(API_KEY)}

# 挂载前端页面（确保index.html在同一目录）
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)