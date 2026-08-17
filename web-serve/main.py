import logging
import sys
from flask import Flask, request, render_template, Response, stream_with_context
import requests
import json
import os
import re
import subprocess
import time
from transformers import AutoTokenizer

# ---------- 配置彩色日志 ----------
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[41m',
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        levelname = record.levelname
        color = self.COLORS.get(levelname, '')
        record.levelname = f"{color}{self.BOLD}{levelname}{self.RESET}"
        record.asctime = self.formatTime(record, self.datefmt)
        return super().format(record)

logger = logging.getLogger('CogniPulse')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = ColoredFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)

# ---------- Flask 初始化 ----------
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# ---------- 配置 ----------
PORT_CogniPluse_Work = 8081
PORT_CogniPluse_Chat = 8080
CogniPluse_Work_URL = f"http://localhost:{PORT_CogniPluse_Work}/completion"
CogniPluse_Chat_URL = f"http://localhost:{PORT_CogniPluse_Chat}/completion"

TOKENIZER_PATH = "./base_model"
if not os.path.exists(TOKENIZER_PATH):
    logger.warning(f"Tokenizer 目录 '{TOKENIZER_PATH}' 不存在，闲聊将使用简单拼接")
    tokenizer = None
else:
    try:
        tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
        logger.info(f"成功加载 tokenizer：{TOKENIZER_PATH}")
    except Exception as e:
        logger.error(f"加载 tokenizer 失败：{e}")
        tokenizer = None

SKILLS_FILE = "skills.json"
WHITELIST_FILE = "whitelist.json"
SKILLS_DIR = "skills"
MAX_ITERATIONS = 5

if not os.path.exists(SKILLS_DIR):
    os.makedirs(SKILLS_DIR)
    logger.info(f"创建技能目录：{SKILLS_DIR}")

def load_json(filename, default=None):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default if default is not None else {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

skills = load_json(SKILLS_FILE, {})
whitelist = load_json(WHITELIST_FILE, [])
logger.info(f"已加载 {len(skills)} 个技能，白名单：{whitelist}")

# ---------- 辅助函数 ----------
def get_completion(prompt, port, temperature=0.65, top_k=5, n_predict=512):
    """非流式调用 llama-server，并截断过长的 prompt"""
    # ---------- 截断过长的 prompt ----------
    max_prompt_len = 1800  # 约 450 tokens（保守）
    if len(prompt) > max_prompt_len:
        # 保留开头 200 字符（包含系统提示）和结尾 1600 字符
        head = prompt[:200]
        tail = prompt[-max_prompt_len+200:]
        prompt = head + "\n...(中间截断)...\n" + tail
        logger.warning(f"prompt 过长，已截断至 {len(prompt)} 字符")

    url = f"http://localhost:{port}/completion"
    payload = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "top_k": top_k,
        "repeat_penalty": 1.1,
        "repeat_last_n": 256,
        "stream": False
    }
    logger.debug(f"调用端口 {port}，prompt 长度：{len(prompt)}")
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data.get('content', '')
        logger.debug(f"端口 {port} 响应长度：{len(content)}")
        return content
    except Exception as e:
        logger.error(f"调用端口 {port} 失败：{e}")
        return None

def judge_intent(user_message):
    """
    判断用户意图，返回 'c'（闲聊）、'w'（工作）、'f'（询问开发者）
    """
    logger.info(f"判断意图：用户消息 = {user_message[:50]}...")
    prompt = (
        f"你是一个意图分类器。用户说：\"{user_message}\"\n"
        "请判断用户是想闲聊（chat）、需要你执行任务（work），还是在询问关于你的开发者信息（developer）。\n"
        "判断标准：\n"
        "- 如果用户只是问候、表达情感、随意聊天，没有具体信息需求，请输出 'c'。\n"
        "- 如果用户要求你完成某个具体任务（如查询信息、计算、操作、搜索新闻、创建文件等），请输出 'w'。\n"
        "- 如果用户在询问关于你的开发者、创建者、公司背景等，请输出 'f'。\n"
        "只输出一个字母，不要输出其他任何内容。"
    )
    result = get_completion(prompt, PORT_CogniPluse_Work, temperature=0.0, n_predict=1)
    if result:
        result = result.strip().lower()
        if result in ('c', 'w', 'f'):
            logger.info(f"意图判断结果：{'闲聊' if result == 'c' else '工作' if result == 'w' else '开发者询问'}")
            return result
    logger.warning(f"意图判断异常，默认工作模式。原始返回：{result}")
    return 'w'

def execute_skill(skill_id, argv):
    """执行技能脚本，从 skills.json 读取超时配置"""
    logger.info(f"执行技能：{skill_id}，参数：{json.dumps(argv, ensure_ascii=False)}")
    if skill_id not in skills:
        err = f"未找到技能 '{skill_id}'"
        logger.error(err)
        return err
    skill_info = skills[skill_id]
    script_path = os.path.join(SKILLS_DIR, skill_info.get('script', ''))
    if not os.path.exists(script_path):
        err = f"技能脚本 '{script_path}' 不存在"
        logger.error(err)
        return err

    # 读取超时配置：默认 30 秒，若 timeout 为 0 则无限制（None）
    timeout = skill_info.get('timeout', 30)
    if timeout == 0:
        timeout = None

    try:
        result = subprocess.run(
            ['python', script_path, json.dumps(argv)],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode != 0:
            err = f"技能执行失败：{result.stderr.strip()}"
            logger.error(err)
            return err
        output = result.stdout.strip()
        logger.info(f"技能 {skill_id} 执行成功，输出：{output[:100]}...")
        return output
    except subprocess.TimeoutExpired:
        err = "技能执行超时"
        logger.error(err)
        return err
    except Exception as e:
        err = f"技能执行异常：{str(e)}"
        logger.error(err)
        return err

# ---------- 会话状态 ----------
agent_states = {}

def get_state(session_id):
    if session_id not in agent_states:
        agent_states[session_id] = {
            'prompt': '',
            'iterations': 0,
            'history': [],
            'user_message': '',
            'allowed_once': set(),
            'pending_skill': None,
            'max_iterations': MAX_ITERATIONS,
            'finished': False,
            'final_answer': None,
            'has_executed_skill': False,
            'extracted_url': None,
        }
        logger.debug(f"创建新会话状态：{session_id}")
    return agent_states[session_id]

def cleanup_state(session_id):
    if session_id in agent_states:
        del agent_states[session_id]
        logger.debug(f"清理会话状态：{session_id}")

# ---------- 流式生成器 ----------
def generate_stream(session_id, message, history, continue_flag):
    state = get_state(session_id)
    logger.info(f"===== 新请求开始，session: {session_id}, continue: {continue_flag} =====")

    if not continue_flag:
        logger.info(f"用户消息：{message[:50]}...，历史消息数：{len(history)}")
        intent = judge_intent(message)

        # ---------- 处理开发者询问 ----------
        if intent == 'f':
            fixed_reply = "如果你想了解我的开发者的话，可以点击左侧边栏的‘开发者介绍’链接查看喵~"
            logger.info("返回开发者固定回复")
            yield f"data: {json.dumps({'content': fixed_reply})}\n\n"
            yield "data: [DONE]\n\n"
            cleanup_state(session_id)
            return

        if intent == 'c':
            logger.info("进入闲聊分支，调用 CogniPulse_Chat")
            if tokenizer is None:
                chat_history = ""
                for msg in history:
                    role = "用户" if msg['role'] == 'user' else "助手"
                    chat_history += f"{role}：{msg['content']}\n"
                chat_history += f"用户：{message}\n助手："
                prompt = chat_history
                logger.warning("未使用 tokenizer，采用简单拼接 prompt")
            else:
                messages = history + [{"role": "user", "content": message}]
                try:
                    prompt = tokenizer.apply_chat_template(
                        messages,
                        tokenize=False,
                        add_generation_prompt=True
                    )
                    logger.info("使用 tokenizer 应用 chat template 生成 prompt")
                except Exception as e:
                    logger.error(f"应用 chat template 失败：{e}，降级为简单拼接")
                    chat_history = ""
                    for msg in history:
                        role = "用户" if msg['role'] == 'user' else "助手"
                        chat_history += f"{role}：{msg['content']}\n"
                    chat_history += f"用户：{message}\n助手："
                    prompt = chat_history

            url = f"http://localhost:{PORT_CogniPluse_Chat}/completion"
            payload = {
                "prompt": prompt,
                "n_predict": 512,
                "temperature": 0.65,
                "top_k": 5,
                "repeat_penalty": 1.1,
                "repeat_last_n": 256,
                "stream": True
            }
            try:
                resp = requests.post(url, json=payload, stream=True, timeout=120)
                resp.raise_for_status()
                logger.info("开始流式接收 CogniPulse_Chat 响应")
                chunk_count = 0
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            logger.info(f"闲聊响应结束，共 {chunk_count} 个片段")
                            break
                        try:
                            obj = json.loads(data)
                            content = obj.get('content', '')
                            if content:
                                chunk_count += 1
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        except json.JSONDecodeError:
                            pass
                yield "data: [DONE]\n\n"
                logger.info("闲聊分支完成")
            except Exception as e:
                logger.error(f"闲聊流式请求异常：{e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            cleanup_state(session_id)
            return

        # 工作模式（intent == 'w'）
        logger.info("进入工作模式，初始化 Agent 状态")
        yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': '开始处理任务'})}\n\n"

        # ---------- 提取 URL ----------
        url_pattern = r'https?://[^\s]+'
        match = re.search(url_pattern, message)
        state['extracted_url'] = match.group(0) if match else None
        if state['extracted_url']:
            logger.info(f"检测到 URL：{state['extracted_url']}")

        skill_descs = "\n".join([f"- {sid}: {info['description']}" for sid, info in skills.items()])
        dynamic_work_system = (
            "你是一个任务执行助手。当用户要求你完成某项任务时，你需要逐步思考并调用可用技能。\n"
            "可用的技能列表如下：\n" + skill_descs + "\n"
            "请按以下格式输出你的操作：\n"
            "<skillcall skill=\"技能ID\" argv=参数JSON对象>思考过程</skillcall>\n"
            "其中参数JSON对象必须是一个合法的JSON对象，例如：{\"query\": \"今日新闻\"}\n"
            "注意：\n"
            "1. 每次只能调用一个技能，调用后我会把执行结果告诉你，你再决定下一步。\n"
            "2. 当输出END时，argv必须为空字符串\"\"，结论放在标签内容中。\n"
            "3. 你绝对不能在调用任何技能之前就输出END，必须通过技能获取真实数据，不能编造答案。\n"
            "4. 对于浏览搜索（BROWSE_SEARCH），argv必须包含query字段，例如：{\"query\": \"搜索关键词\"}\n"
            "5. 如果用户明确提供 URL（以 http:// 或 https:// 开头）并要求阅读或分析，你必须使用 BROWSE_READ 技能，将完整 URL 作为参数传入。例如：{\"url\": \"https://example.com\"}\n"
            "6. 如果用户询问当前时间，你必须使用 get_current_time 技能（无需参数）。\n"
            "7. 参数JSON对象中的字符串必须使用双引号，不要使用单引号。\n"
            "示例：<skillcall skill=\"BROWSE_SEARCH\" argv={\"query\": \"今日新闻\"}>正在搜索今日新闻...</skillcall>"
        )
        chat_history = f"用户：{message}\n"
        state['prompt'] = dynamic_work_system + "\n\n" + chat_history + "助手："
        state['iterations'] = 0
        state['history'] = history
        state['user_message'] = message
        state['allowed_once'] = set()
        state['pending_skill'] = None
        state['finished'] = False
        state['final_answer'] = None
        state['has_executed_skill'] = False
        logger.debug(f"工作模式初始 prompt 长度：{len(state['prompt'])}")

        # ---------- 自动匹配入口：URL 或文件路径或时间关键词 ----------
        auto_skill = None
        auto_argv = {}

        # 1. 检测 URL
        if state['extracted_url']:
            auto_skill = 'BROWSE_READ'
            auto_argv = {'url': state['extracted_url']}
        else:
            # 2. 检测文件路径
            path_pattern = r'(?:[a-zA-Z]:)?[\\/](?:[^\s"\'<>]+[\\/])*[^\s"\'<>]+'
            path_match = re.search(path_pattern, message)
            if path_match:
                potential_path = path_match.group(0)
                if not re.match(r'https?://', potential_path):
                    auto_skill = 'FILE_READ'
                    auto_argv = {'path': potential_path}

            # 3. 检测时间关键词
            if not auto_skill:
                time_keywords = ['现在几点', '当前时间', '什么时间', '几点了', '现在时间', '当前时刻', '时间']
                if any(kw in message for kw in time_keywords):
                    auto_skill = 'get_current_time'
                    auto_argv = {}

        if auto_skill and auto_skill in skills:
            logger.info(f"自动匹配到技能：{auto_skill}，参数：{auto_argv}")
            yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'自动调用 {auto_skill}...'})}\n\n"
            result = execute_skill(auto_skill, auto_argv)
            state['prompt'] += f"技能执行结果（自动获取）：{result}\n助手（下一步）："
            state['has_executed_skill'] = True

    # 工作模式主循环
    while state['iterations'] < state['max_iterations'] and not state['finished']:
        # 限制 prompt 长度，防止无限增长
        if len(state['prompt']) > 3000:
            # 保留开头 300 字符和结尾 2500 字符
            head = state['prompt'][:300]
            tail = state['prompt'][-2500:]
            state['prompt'] = head + "\n...(中间截断)...\n" + tail
            logger.warning(f"state['prompt'] 过长，已截断至 {len(state['prompt'])} 字符")

        # 兜底机制：连续 3 次未执行技能且有 URL
        if state['iterations'] >= 3 and not state['has_executed_skill'] and state.get('extracted_url'):
            logger.info(f"模型连续 {state['iterations']} 次未调用技能，自动执行 BROWSE_READ：{state['extracted_url']}")
            result = execute_skill('BROWSE_READ', {'url': state['extracted_url']})
            yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'自动执行 BROWSE_READ 获取网页内容...'})}\n\n"
            state['prompt'] += f"技能执行结果（自动获取）：{result}\n助手（下一步）："
            state['has_executed_skill'] = True
            state['iterations'] += 1
            continue

        if state['pending_skill'] and state['pending_skill'].get('confirmed', False):
            skill_id = state['pending_skill']['skill_id']
            argv = state['pending_skill']['argv']
            logger.info(f"执行已确认的技能：{skill_id}")
            yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'执行技能: {skill_id}'})}\n\n"
            result = execute_skill(skill_id, argv)
            yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'技能执行完成，结果: {result[:50]}...'})}\n\n"
            state['prompt'] += f"技能执行结果：{result}\n助手（下一步）："
            state['pending_skill'] = None
            state['iterations'] += 1
            state['has_executed_skill'] = True
            logger.debug(f"迭代 {state['iterations']} 后 prompt 长度：{len(state['prompt'])}")
            continue

        logger.info(f"工作模式第 {state['iterations']+1} 次调用 CogniPluse_Work")
        yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'第 {state["iterations"]+1} 次思考中...'})}\n\n"
        response = get_completion(state['prompt'], PORT_CogniPluse_Work, temperature=0.65, n_predict=256)
        if response is None:
            logger.error("CogniPluse_Work 响应为空，结束任务")
            yield f"data: {json.dumps({'error': '模型响应失败'})}\n\n"
            cleanup_state(session_id)
            return
        logger.debug(f"CogniPluse_Work 响应长度：{len(response)}")

        # ---------- 改进的 skillcall 解析 ----------
        skillcall_pattern = r'<skillcall\s+(.*?)>(.*?)</skillcall>'
        match = re.search(skillcall_pattern, response, re.DOTALL)

        if not match:
            logger.info("未检测到 skillcall 标签，将响应作为最终结论")
            state['final_answer'] = response
            state['finished'] = True
            break

        attrs = match.group(1).strip()
        thought = match.group(2).strip()

        skill_match = re.search(r'skill\s*=\s*["\']?([^"\' >]+)["\']?', attrs)
        if not skill_match:
            logger.warning("无法提取 skill，将响应作为最终结论")
            state['final_answer'] = response
            state['finished'] = True
            break
        skill_id = skill_match.group(1).strip()

        argv_str = ""
        argv_match = re.search(r'argv\s*=\s*["\']?(\{.*?\})["\']?', attrs, re.DOTALL)
        if argv_match:
            argv_str = argv_match.group(1).strip()
        else:
            logger.warning(f"未找到有效的 argv，将使用空字典")
            argv_str = "{}"

        try:
            argv = json.loads(argv_str)
        except json.JSONDecodeError:
            try:
                import ast
                fixed = argv_str.replace("'", '"')
                argv = json.loads(fixed)
            except:
                logger.warning(f"无法解析 argv：{argv_str}，使用空字典")
                argv = {}

        # 如果 BROWSE_SEARCH 缺少 query，自动提取
        if not argv and skill_id == 'BROWSE_SEARCH':
            keyword_match = re.search(r'搜索\s*(.+?)(?:[，。！？\s]|$)', message)
            if keyword_match:
                keyword = keyword_match.group(1).strip()
                if keyword:
                    argv = {"query": keyword}
                    logger.info(f"自动从用户消息中提取关键词：{keyword}")
            else:
                keyword = message
                for prefix in ['搜索', '查询', '找', '查', '看看', '阅读']:
                    if keyword.startswith(prefix):
                        keyword = keyword[len(prefix):].strip()
                        break
                if keyword:
                    argv = {"query": keyword}
                    logger.info(f"从用户消息中提取关键词：{keyword}")

        logger.info(f"解析到 skillcall：skill={skill_id}, argv={argv}, thought={thought[:30]}...")

        if skill_id.upper() == "END":
            if not state['has_executed_skill']:
                logger.warning("模型直接输出 END 但未执行任何技能（自动匹配可能未触发）")
            state['final_answer'] = thought if thought else "任务已完成。"
            state['finished'] = True
            break

        # 权限检查
        allowed = False
        if skill_id in whitelist:
            allowed = True
            logger.debug(f"技能 {skill_id} 在白名单中")
        elif skill_id in state['allowed_once']:
            allowed = True
            logger.debug(f"技能 {skill_id} 被本次会话允许")
        else:
            logger.info(f"技能 {skill_id} 不在白名单，需用户确认")

        if allowed:
            yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'调用技能: {skill_id}'})}\n\n"
            result = execute_skill(skill_id, argv)
            yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'技能执行完成，结果: {result[:50]}...'})}\n\n"
            state['prompt'] += f"{response}\n技能执行结果：{result}\n助手（下一步）："
            state['iterations'] += 1
            state['has_executed_skill'] = True
            logger.debug(f"迭代 {state['iterations']} 后 prompt 长度：{len(state['prompt'])}")
        else:
            state['pending_skill'] = {
                'skill_id': skill_id,
                'argv': argv,
                'thought': thought,
                'confirmed': False
            }
            ask_event = {
                'type': 'ask_user',
                'confirm_id': session_id,
                'skill_id': skill_id,
                'argv': argv,
                'thought': thought,
                'skill_desc': skills.get(skill_id, {}).get('description', '无描述')
            }
            logger.info(f"向用户发送确认请求：技能 {skill_id}")
            yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': f'请求用户确认技能: {skill_id}'})}\n\n"
            yield f"data: {json.dumps(ask_event)}\n\n"
            return

    # 结束处理
    if state['finished']:
        final = state['final_answer'] or "任务已完成。"
        logger.info(f"工作模式完成，最终结论：{final[:100]}...")
        yield f"data: {json.dumps({'type': 'step', 'icon': '·', 'desc': '任务完成'})}\n\n"
        yield f"data: {json.dumps({'content': final})}\n\n"
        yield "data: [DONE]\n\n"
        cleanup_state(session_id)
    else:
        logger.warning("达到最大迭代次数，任务可能未完成")
        yield f"data: {json.dumps({'content': '达到最大循环次数，任务可能未完成。'})}\n\n"
        yield "data: [DONE]\n\n"
        cleanup_state(session_id)

# ---------- Flask 路由 ----------
@app.route('/')
def index():
    logger.info("访问首页")
    return render_template('index.html')

@app.route('/about')
def about():
    """开发者信息页面"""
    logger.info("访问关于页面")
    return render_template('about.html')

@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    data = request.get_json()
    if not data:
        logger.warning("收到空请求")
        return {"error": "Invalid request"}, 400

    session_id = data.get('session_id')
    message = data.get('message', '').strip()
    history = data.get('history', [])
    continue_flag = data.get('continue', False)

    if not session_id:
        logger.warning("缺少 session_id")
        return {"error": "Missing session_id"}, 400

    if not continue_flag and not message:
        logger.warning("消息为空且非继续请求")
        return {"error": "Message is empty"}, 400

    logger.info(f"收到流式请求，session={session_id}, continue={continue_flag}, message={message[:30] if message else ''}...")
    return Response(
        stream_with_context(generate_stream(session_id, message, history, continue_flag)),
        mimetype='text/event-stream'
    )

@app.route('/confirm', methods=['POST'])
def confirm():
    data = request.get_json()
    if not data:
        logger.warning("确认请求数据为空")
        return {"error": "Invalid request"}, 400

    confirm_id = data.get('confirm_id')
    decision = data.get('decision')
    logger.info(f"收到确认请求：confirm_id={confirm_id}, decision={decision}")

    if not confirm_id or decision not in ('accept', 'once', 'reject'):
        logger.warning(f"无效确认参数：confirm_id={confirm_id}, decision={decision}")
        return {"error": "Invalid parameters"}, 400

    session_id = confirm_id
    state = get_state(session_id)

    if state.get('pending_skill') is None:
        logger.warning(f"会话 {session_id} 没有待确认的技能")
        return {"error": "No pending skill"}, 400

    skill_id = state['pending_skill']['skill_id']

    if decision == 'reject':
        logger.info(f"用户拒绝技能 {skill_id}")
        state['finished'] = True
        state['final_answer'] = f"技能 '{skill_id}' 被用户拒绝，任务终止。"
        state['pending_skill'] = None
        return {"status": "rejected"}

    if decision == 'once':
        logger.info(f"用户允许技能 {skill_id} 本次执行")
        state['allowed_once'].add(skill_id)
        state['pending_skill']['confirmed'] = True
        return {"status": "allowed_once"}

    if decision == 'accept':
        logger.info(f"用户将技能 {skill_id} 加入白名单")
        if skill_id not in whitelist:
            whitelist.append(skill_id)
            save_json(WHITELIST_FILE, whitelist)
            logger.debug(f"白名单已更新：{whitelist}")
        state['allowed_once'].add(skill_id)
        state['pending_skill']['confirmed'] = True
        return {"status": "accepted"}

    return {"error": "Unknown decision"}, 400

if __name__ == '__main__':
    logger.info("启动 Flask 应用，监听 0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)