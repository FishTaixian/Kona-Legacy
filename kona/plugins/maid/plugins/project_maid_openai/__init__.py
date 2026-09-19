from pathlib import Path

import nonebot,asyncio,aiofiles,aiohttp,json,re,ast,os,jmcomic
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message,MessageSegment,MessageEvent,PrivateMessageEvent,GroupMessageEvent,NoticeEvent,PokeNotifyEvent,Event,Bot
from nonebot.params import Arg,ArgPlainText
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot import on_command,on_keyword,on_notice,on_message,logger

from openai import AsyncOpenAI,APITimeoutError
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from datetime import datetime
from io import BytesIO
from PIL import Image
from jmcomic.jm_exception import PartialDownloadFailedException
from dotenv import load_dotenv

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="Project-Maid-OpenAI",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

#加载dotenv
load_dotenv()
#加载环境变量
# PROJECT_MAID_OPENAI_PROMPT = os.getenv("PROMPT","None")
PROJECT_MAID_OPENAI_KEI = os.getenv("APIKEY","None")

# if PROJECT_MAID_OPENAI_PROMPT == "None":
#     pass # raise Exception("Non-PromptError")
if PROJECT_MAID_OPENAI_KEI == "None":
    raise Exception("Non-APIKeyError")

#定义常量字段
PROJECT_MAID_OPENAI = Path(__file__).parent
PROJECT_MAID_OPENAI_MFACE_DATA_PATH = PROJECT_MAID_OPENAI/"dat"/"mfaces"
PROJECT_MAID_OPENAI_TIMEMACHINE_DATA_PATH = PROJECT_MAID_OPENAI/"dat"/"timemachine.json"
PROJECT_MAID_OPENAI_TIMEMACHINE_MAIDFRAME_PATH = PROJECT_MAID_OPENAI/"dat"/"timemachine_maid_frame.json"
PROJECT_MAID_OPENAI_TIMEMACHINE_PROFILEFRAME_PATH = PROJECT_MAID_OPENAI/"dat"/"timemachine_profile_frame.json"
PROJECT_MAID_OPENAI_PROMPT_DATA_PATH = PROJECT_MAID_OPENAI/"dat"/"prompt.txt"
JM_CACHE_PATH = PROJECT_MAID_OPENAI/"dat"/"jmcomic"
JM_OPTION_PATH = PROJECT_MAID_OPENAI/"dat"/"jmcomic"/"option.yml"

'''dat文件夹内文件释义
prompt.txt 提示词文件
timemachine.json 记忆文件
timemachine_maid_frame.json 记忆主线结构文件
timemachine_profile_frame.json 记忆印象结构文件
timemachine.json.sample 记忆文件示例
option.yml jmcomci配置文件
'''

#初始化jmoption
with open(str(JM_OPTION_PATH.resolve()),"w") as opt:
    opt.write("dir_rule:\n base_dir: "+str(JM_CACHE_PATH.resolve())+"\n rule: Bd / {Aid}")

'''Maid环境变量'''

class _TimeMachine:
    def __init__(self):
        '''**创建一个时间机器 可以附属为其他平行类的子类**
        Functions:
            record
        '''
        try:
            with open(PROJECT_MAID_OPENAI_TIMEMACHINE_DATA_PATH,"r",encoding="utf-8") as f:
                content = f.read()
                self.memory:dict[str,dict] = json.loads(content)
                f.close()
            logger.debug("检测到已有时间机器")
        except:
            logger.debug("未检测到已有时间机器 新建时间机器")
            self.memory:dict[str,dict] = {"Maid":{"TimeMachine":{}}}
            logger.debug("时间机器创建完成")
            with open(PROJECT_MAID_OPENAI_TIMEMACHINE_DATA_PATH,"w",encoding="utf-8") as f:
                f.write(json.dumps(self.memory, indent=4))
                f.close()
            logger.debug("时间机器保存完成")

    async def record_event(self, obj:str, time:dict[str,str], happened:str, tags:list[dict[str,str]]) -> str:
        '''**Maid记住了这件事情**
        Args:
            object: 将事情记录在的对象上
            time: 事情发生的时间
            happened: 发生了什么
            tags: Maid的感受
        Returns:
            我记住了这件事: happened
        '''
        #检查记忆内是否有用户
        await self.check_user(obj)

        #补充TimeMachine时间戳 / 初始化
        self.memory[obj]["TimeMachine"].setdefault(time["Year"],{})
        self.memory[obj]["TimeMachine"][time["Year"]].setdefault(time["Month"],{})
        self.memory[obj]["TimeMachine"][time["Year"]][time["Month"]].setdefault(time["Day"],{})
        self.memory[obj]["TimeMachine"][time["Year"]][time["Month"]][time["Day"]].setdefault(time["Hour"],{})
        self.memory[obj]["TimeMachine"][time["Year"]][time["Month"]][time["Day"]][time["Hour"]].setdefault(time["Minute"],{})
        #保存事件
        self.memory[obj]["TimeMachine"][time["Year"]][time["Month"]][time["Day"]][time["Hour"]][time["Minute"]]["Happend"] = happened
        #保存Tags
        self.memory[obj]["TimeMachine"][time["Year"]][time["Month"]][time["Day"]][time["Hour"]][time["Minute"]]["Tags"] = tags
        await self.update()
        return f"我记住了这件事:{happened}"
    
    async def record_profile(self, obj:str, key:str, value:str) -> str:
        '''**Maid记下了这个印象**
        Args:
            object: 记忆的对象
            key: 记忆的属性
            value: 记忆属性的值
        Returns:
            我记下了这个印象: value
        '''
        #检查记忆内是否有用户
        await self.check_user(obj)

        keys_accepted = ("Name", "Age", "Relationship", "Gender", "SocialGender", "Alias", "Pleasure", "H", "Interested", "Board", "Tags", "MyThought")
        if not obj == "Maid" and key in keys_accepted:
            self.memory[obj]["Profile"][key] = value
            await self.update()
            return f"我记下了这个印象:{key}={value}"
        else:
            logger.warning(f"RecordProfile方法接收到了不合法的参数:{key}={value}")
            return ""
    
    async def remove_profile(self, obj:str, key:str, value:str) -> str:
        '''**Maid忘记了这个印象**
        Args:
            object: 删改的对象
            key: 删改的属性
            value: 删改属性的值
        Returns:
            我忘记了这个印象: value
        '''
        #检查记忆内是否有用户
        await self.check_user(obj)

        keys_accepted = ("Name", "Age", "Relationship", "Gender", "SocialGender", "Alias", "Pleasure", "H", "Interested", "Board", "Tags", "MyThought")
        if not obj == "Maid" and key in keys_accepted:
            self.memory[obj]["Profile"][key] = value
            await self.update()
            return f"我记下了这个印象:{key}={value}"
        else:
            logger.warning(f"RecordProfile方法接收到了不合法的参数:{key}={value}")
            return ""

    async def recall(self, obj:str, value:str="TimeMachine") -> str:
        '''**Maid正回忆着往事**
        Args:
            object: 回忆的对象
            value: 回忆的属性
        Returns:
            TimeMachine{}
        '''
        #检查记忆内是否有用户
        await self.check_user(obj)

        return str(self.memory[obj][value])
    
    async def update(self) -> None:
        '''**同步运行时记忆到外部记忆**'''
        async with aiofiles.open(PROJECT_MAID_OPENAI_TIMEMACHINE_DATA_PATH,"w",encoding="utf-8") as f:
            await f.write(json.dumps(self.memory, indent=4, ensure_ascii=False))
            await f.close()
        logger.debug("时间机器更新完成")
        return None
    
    async def check_user(self, user_id:str) -> None:
        if not user_id in self.memory:
            async with aiofiles.open(PROJECT_MAID_OPENAI_TIMEMACHINE_PROFILEFRAME_PATH,"r") as f:
                pframe = json.loads(await f.read())
            self.memory.setdefault(user_id,{})
            self.memory[user_id].setdefault("Profile",pframe["Profile"])
            self.memory[user_id].setdefault("TimeMachine",{})
        return None

class _ChatClient:
    def __init__(self):
        pass

    async def send_msg(self, matcher:Matcher, messages:tuple[str]) -> str:
        for message in messages:
            await asyncio.sleep(len(message)*0.18)
            match list(message)[0]:
                case "@":
                    await matcher.send(Message(MessageSegment.at("".join(list(message)[1:]))))
                case "!":
                    await matcher.send(Message(MessageSegment.image(PROJECT_MAID_OPENAI_MFACE_DATA_PATH.joinpath(f"{"".join(list(message)[1:])}.png"))))
                case _:
                    await matcher.send(Message(MessageSegment.text(message)))
            await asyncio.sleep(0.5)
        return f"发送了一段消息: {messages}"

class _Mind:
    '''## 此类为Maid心智类'''
    def __init__(self, Kei:str, prompt:str, length:int, model:str="deepseek-v4-flash", temperature:float=0.6, max_tokens:int=1024):
        '''**Maid心智类，决定Maid情绪 思考 内心活动**
        Args:
            Kei: Maid的API Key
            prompt: Maid的人格
            length: Maid可以同时注意到的最大上下文轮数 长度越大 短时记忆越长 同时token消耗量越高 此轮数包括请求轮和回复轮与工具轮 请使用偶数
        '''
        #初始化起始参数
        self.mind = AsyncOpenAI(api_key=Kei, base_url="https://api.deepseek.com")
        self.context:dict[str,list[ChatCompletionMessageParam]] = {}
        self.prompt = prompt
        self.length = length
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info("Maid心智类基础初始化完成")
        #载入Time_Machine
        self.time_machine:_TimeMachine = _TimeMachine()
        logger.info("Maid心智类时间机器初始化成功")

    async def context_update(self, user_id:str, messages:list[dict[str,str]], group_id:str="") -> None:
        '''**接收单条或连续消息 更新上下文**
        Args:
            user_id: 会话用户的用户ID
            messages: 传入单条或连续消息 接收list[dict["user","user_id","time","content"]参数
        Returns:
            list[str]
        '''
        #检查会话是否为群聊 简单适配
        if group_id:
            if not group_id in self.context.keys():
                self.context[group_id] = [{"role":"system","content":self.prompt}]
            content = ""
            if len(self.context[group_id])-1 > self.length:
                tmp:list[ChatCompletionMessageParam] = [self.context[group_id][0]]
                tmp.extend(self.context[group_id][len(self.context)-self.length:])
                self.context[group_id] = tmp  
            for seg in messages:
                content = content + f"<群聊消息:{group_id}>{seg['user']}({seg['user_id']})[{seg['time']}]:{seg['content']}\n"
            self.context[group_id].append({"role":"user","content":content})
            return None

        #检查会话是否存在 不存在则新建
        if not user_id in self.context.keys():
            self.context[user_id] = [{"role":"system","content":self.prompt}]

        #创建一个拼接字符串
        content = ""

        #检查上下文长度和清理
        if len(self.context[user_id])-1 > self.length:
            tmp:list[ChatCompletionMessageParam] = [self.context[user_id][0]]
            tmp.extend(self.context[user_id][len(self.context)-self.length:])
            self.context[user_id] = tmp   

        #拼接上下文
        for seg in messages:
            content = content + f"<私聊消息>{seg['user']}({seg['user_id']})[{seg['time']}]:{seg['content']}\n"
        self.context[user_id].append({"role":"user","content":content})
        return None
    
    async def toolcall_update(self, user_id:str, tool_result:str) -> None:
        '''**接收工具返回结果 更新上下文**
        Args:
            user_id: 会话用户的用户ID
            tool_result: 工具返回结果
        '''
        #检查上下文长度和清理
        if len(self.context[user_id])-1 > self.length:
            tmp:list[ChatCompletionMessageParam] = [self.context[user_id][0]]
            tmp.extend(self.context[user_id][len(self.context)-self.length:])
            self.context[user_id] = tmp  

        #拼接上下文
        self.context[user_id].append({"role":"user","content":tool_result})
    
    async def thought(self, user_id:str) -> str|None:
        '''**通过上下文 Maid回复你单条或连续消息**
        Args:
            messages: 传入单条或连续消息 接收list[dict["user","user_id","time","content"]参数
        Returns:
            list[str]
        '''
        #请求回复
        while True:
            try:
                response = await self.mind.chat.completions.create(
                    model=self.model,
                    messages=self.context[user_id],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=False
                )
                break
            except APITimeoutError:
                pass
            except Exception as e:
                raise e

        #拼接上下文
        self.context[user_id].append({"role":"assistant","content":response.choices[0].message.content})
        #返回消息
        return response.choices[0].message.content

class _Action:
    '''**Maid行动类，决定Maid能力与行动**'''
    def __init__(self):
        #载入ChatClient
        self.chat_client:_ChatClient = _ChatClient()
        logger.info("Maid行动类基础初始化完成")
    
    async def send_sexpic(self, matcher:Matcher, r18_switch:str) -> None:
        #载入aiohttp.ClientSession
        http_session:aiohttp.ClientSession = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(30))
        url = "https://moe.jitsu.top/img?sort=r18" if r18_switch == "enable" else "https://moe.jitsu.top/img" if r18_switch == "disable" else ""
        if not url:
            logger.warning(f"调用send_sexpic时r18_switch出现了意料之外的参数{r18_switch}")
            return None
        while True:
            try:
                pic = await http_session.get(url)
            except TimeoutError:
                continue
            except Exception as e:
                raise e
            if not pic.ok:
                continue
            async with pic:
                pic_name = str(pic.url).split("/")[-1]
                pic_data = BytesIO(await pic.content.read())
                await matcher.send(Message(MessageSegment.image(pic_data)))
            break
        await http_session.close()
        return None
    
    async def send_18comic(self, matcher:Matcher, bot:Bot, event:GroupMessageEvent, jmcode:str) -> None:
        filepath = JM_CACHE_PATH / f"{jmcode}.pdf"
        while True:
            try:
                await jmcomic.download_album_async(jmcode, jmcomic.create_option_by_file(str(JM_OPTION_PATH.resolve())), extra=jmcomic.Feature.export_pdf(filename_rule="Aid"))
                break
            except PartialDownloadFailedException:
                pass
            except Exception as e:
                raise e
        await bot.call_api("upload_group_file", group_id=str(event.group_id), file=str(filepath), name=f"{jmcode}.pdf")
        return None

        
'''私有抽象类/抽象方法'''

class Maid:
    '''## Maid类
    此类耦合了Maid心智类和Maid行动类 返回一个MaidAI对象
    Attributes:
        self.mind: Maid心智类, 负责Maid思考 情绪 记忆
        self.action: Maid行动类, 负责Maid能力 行动
        self.private_messages_cache: Maid私聊会话状态, 以dict["用户ID",list[dict]]的方式存储各对话消息
        self.group_messages_cache: Maid群聊会话状态, 以dict["群聊ID",list[dict]]的方式存储各对话消息
    '''
    def __init__(self, length:int) -> None:
        '''## Maid类初始化函数
        Args:
            length: 最大上下文轮数 长度越大 短时记忆越长 同时token消耗量越高 此轮数包括请求轮和回复轮与工具轮 请使用偶数
        此方法耦合了Maid心智类和Maid行动类 返回一个MaidAI对象\n
        <del>(实际上Maid类就一个Agent的作用 我改进了ReAct范式而已)</del>
        '''
        logger.info("Maid类开始载入")
        #从dat载入提示词
        try:
            with open(PROJECT_MAID_OPENAI_PROMPT_DATA_PATH,"r",encoding="utf-8") as f:
                prompt = f.read()
                f.close()
            logger.debug("人设提示词已载入")
        except:
            logger.error("没有人设提示词 ProjectMaid将不可用")
            raise Exception("Non-PromptError")
        #从env载入kei
        kei = PROJECT_MAID_OPENAI_KEI
        #初始化和封装私有类
        self.locks:dict[str,asyncio.Lock] = {}
        self.timeouts:dict[str,int] = {}
        self.replying_lock = asyncio.Lock()
        self.mind:_Mind = _Mind(kei, prompt, length)
        self.action:_Action = _Action()
        self.private_messages_cache:dict[str,list[dict]] = {}
        self.group_messages_cache:dict[str,list[dict]] = {}
        logger.info("Maid类载入完成")
    
    async def analyzer(self, matcher:Matcher, bot:Bot, event:PrivateMessageEvent|GroupMessageEvent, Lock:asyncio.Lock, text:str|None) -> str:
        #验证内容不为空
        if text is None:
            raise Exception("UnknownThoughtError")
        logger.debug("正在解析回复")
        #初始化模板与变量
        line_preprocess_form = r"<(.*?)>(.*?)</(.*?)>"
        content_preprocess_form = r"(.*?)\((.*)\)"
        tasks:dict[str,tuple|str] = {}
        #分行切片
        text_line = text.splitlines()
        #递归添加任务
        for line in text_line:
            if tmp := re.search(line_preprocess_form,line):
                line_mark = tmp.group(1)
                line_content = tmp.group(2)
            else:
                logger.warning("出现无法格式化的标签")
                continue
            match line_mark:
                case "Thought":
                    tasks["Thought"] = line_content
                    continue
                case "TimeMachine":
                    if tmp := re.search(content_preprocess_form,line_content):
                        line_method = tmp.group(1)
                        line_attr = tmp.group(2)
                    else:
                        logger.warning("TimeMachine标签内出现无法格式化的字段")
                        continue
                    match line_method:
                        case "RecordEvent":
                            tasks["RecordEvent"] = ast.literal_eval(line_attr)
                        case "RecordProfile":
                            tasks["RecordProfile"] = ast.literal_eval(line_attr)
                        case "RemoveProfile":
                            tasks["RemoveProfile"] = ast.literal_eval(line_attr)
                        case "Recall":
                            tasks["Recall"] = ast.literal_eval(line_attr)
                        case _:
                            logger.warning("TimeMachine标签中出现未定义的方法")
                    continue
                case "ChatClient":
                    if tmp := re.search(content_preprocess_form,line_content):
                        line_method = tmp.group(1)
                        line_attr = tmp.group(2)
                    else:
                        logger.warning("ChatClient标签内出现无法格式化的字段")
                        continue
                    match line_method:
                        case "send_msg":
                            tasks["send_msg"] = ast.literal_eval(line_attr)
                        case _:
                            logger.warning("ChatClient标签内出现未定义的方法")
                    continue
                case "Interaction":
                    if tmp := re.search(content_preprocess_form,line_content):
                        line_method = tmp.group(1)
                        line_attr = tmp.group(2)
                    else:
                        logger.warning("Intercation标签内出现无法格式化的字段")
                        continue
                    match line_method:
                        case "send_sexpic":
                            tasks["send_sexpic"] = ast.literal_eval(line_attr)
                        case "send_18comic":
                            tasks["send_18comic"] = ast.literal_eval(line_attr)
                        case _:
                            logger.warning("Interaction标签内出现未定义的方法")
                    continue
        logger.debug("回复解析完成")
        #执行任务
        for k,v in tasks.items():
            match k:
                case "Thought":
                    logger.info(f"Maid:{v}") if type(v) is str else logger.warning(f"输出Maid思考，但是得到了一个意料之外的结果:{v}")
                    continue
                case "RecordEvent":
                    if type(v) is tuple:
                        await self.mind.time_machine.record_event(*v)
                        continue
                    else:
                        logger.warning(f"执行RecordEvent时出现意料之外的参数:{v}")
                        return ""
                case "RecordProfile":
                    if type(v) is tuple:
                        await self.mind.time_machine.record_profile(*v)
                        continue
                    else:
                        logger.warning(f"执行RecordProfile时出现意料之外的参数:{v}")
                        return ""
                case "RemoveProfile":
                    if type(v) is tuple:
                        await self.mind.time_machine.remove_profile(*v)
                        continue
                    else:
                        logger.warning(f"执行RemoveProfile时出现意料之外的参数:{v}")
                        return ""
                case "Recall":
                    if type(v) is tuple:
                        return await self.mind.time_machine.recall(*v)
                    else:
                        logger.warning(f"执行Recall时出现意料之外的参数:{v}")
                        return ""
                case "send_msg":
                    if type(v) is tuple:
                        await self.action.chat_client.send_msg(matcher,v)
                        continue
                    elif type(v) is str:
                        await self.action.chat_client.send_msg(matcher,(v,))
                        continue
                    else:
                        logger.warning(f"执行send_msg时出现意料之外的参数:{v}")
                        return ""
                case "send_sexpic":
                    if type(v) is str:
                        if Lock.locked():
                            Lock.release()
                        try:
                            await self.action.send_sexpic(matcher,v)
                            if type(event) is GroupMessageEvent:
                                await asyncio.sleep(0.5)
                                await matcher.send(Message(MessageSegment.at(str(event.sender.user_id))))
                        except Exception as e:
                            raise e
                        finally:
                            await Lock.acquire()
                    else:
                        logger.warning(f"执行send_sexpic时出现意料之外的参数{v}")
                        return ""
                case "send_18comic":
                    if type(v) is str and type(event) is GroupMessageEvent:
                        if Lock.locked():
                            Lock.release()
                        try:
                            await self.action.send_18comic(matcher,bot,event,v)
                            if type(event) is GroupMessageEvent:
                                await asyncio.sleep(0.5)
                                await matcher.send(Message(MessageSegment.at(str(event.sender.user_id))))
                        except Exception as e:
                            raise e
                        finally:
                            await Lock.acquire()
                    else:
                        logger.warning(f"执行send_18comic时出现意料之外的参数{v}")
                        return ""
                case _:
                    logger.warning(f"出现意料之外的任务:{k}")
                    return ""
        return ""
    
    def listen_and_echo(self):
        #设置收集触发器
        self.collecting = on_message(priority=1, block=True)
        logger.info("Maid开始监听和响应消息")

        #设置回复处理函数
        async def into_reply_private(matcher:Matcher, bot:Bot, event:PrivateMessageEvent):
            user_id = str(event.user_id)
            if self.private_messages_cache[user_id]:
                logger.info(f"Maid开始回复{user_id}")
                await self.mind.context_update(user_id,self.private_messages_cache[user_id])
                result = await self.mind.thought(user_id)
                self.private_messages_cache[user_id].clear()
                while True:
                    analyzation = await self.analyzer(matcher,bot,event,self.locks[user_id],result)
                    if analyzation:
                        await self.mind.toolcall_update(user_id,analyzation)
                        result = await self.mind.thought(user_id)
                    else:
                        break

        async def into_reply_group(matcher:Matcher, bot:Bot, event:GroupMessageEvent):
            user_id = str(event.sender.user_id)
            group_id = str(event.group_id)
            if self.group_messages_cache[group_id]:
                logger.info(f"Maid开始回复{group_id}")
                await self.mind.context_update(user_id,self.group_messages_cache[group_id],group_id)
                result = await self.mind.thought(group_id)
                self.group_messages_cache[group_id].clear()
                while True:
                    analyzation = await self.analyzer(matcher,bot,event,self.locks[group_id],result)
                    if analyzation:
                        await self.mind.toolcall_update(group_id,analyzation)
                        result = await self.mind.thought(group_id)
                    else:
                        break

        #设置收集响应器
        @self.collecting.handle()
        async def collect_private_handle(matcher:Matcher, bot:Bot, event:PrivateMessageEvent):
            #归档消息
            user = event.sender.nickname
            user_id = str(event.sender.user_id)
            time = datetime.now().strftime("%Y-%m-%d/%H:%M")
            content = event.message
            if not user_id in self.private_messages_cache.keys():
                self.private_messages_cache[user_id] = []
            if not user_id in self.locks.keys():
                self.locks.setdefault(user_id,asyncio.Lock())
            self.private_messages_cache[user_id].append({"user":user,"user_id":user_id,"time":time,"content":content})
            logger.info(f"Maid抓住了一条来自{user_id}的消息并归档:{content}")
            if self.locks[user_id].locked():
                self.timeouts[user_id] += 5
                await matcher.finish()
            #回复逻辑
            await self.locks[user_id].acquire()
            self.timeouts[user_id] = 10
            while self.timeouts[user_id]:
                tmp = self.timeouts[user_id]
                self.timeouts[user_id] = 0
                await asyncio.sleep(tmp)
            try:
                await into_reply_private(matcher,bot,event)
            except Exception as e:
                raise e
            finally:
                if self.locks[user_id].locked():
                    self.locks[user_id].release()
            await matcher.finish()
        
        @self.collecting.handle()
        async def collect_group_handle(matcher:Matcher, bot:Bot, event:GroupMessageEvent):
            #归档消息
            group_id = str(event.group_id)
            user = event.sender.nickname
            user_id = str(event.sender.user_id)
            time = datetime.now().strftime("%Y-%m-%d/%H:%M")
            content = event.message
            if not group_id in self.group_messages_cache.keys():
                self.group_messages_cache[group_id] = []
            if not group_id in self.locks.keys():
                self.locks.setdefault(group_id,asyncio.Lock())
            if event.to_me:
                self.group_messages_cache[group_id].append({"user":user,"user_id":user_id,"time":time,"content":"[@了我]"+content})
            else:
                self.group_messages_cache[group_id].append({"user":user,"user_id":user_id,"time":time,"content":content})
            logger.info(f"Maid抓住了一条来自{group_id}的消息并归档:{content}")
            if self.locks[group_id].locked():
                self.timeouts[group_id] += 5
                await matcher.finish()
            #回复逻辑
            await self.locks[group_id].acquire()
            self.timeouts[group_id] = 10
            while self.timeouts[group_id]:
                tmp = self.timeouts[group_id]
                self.timeouts[group_id] = 0
                await asyncio.sleep(tmp)
            try:
                await into_reply_group(matcher,bot,event)
            except Exception as e:
                raise e
            finally:
                if self.locks[group_id].locked():
                    self.locks[group_id].release()
            await matcher.finish()

        #记录日志
        logger.info("Maid正在监听")

'''公有抽象类/抽象方法'''

#      .--.
#     |o_o |
#     |:_/ | 深知自己的代码写的一坨所以放个不吉利的家伙在这里
#    //   \ \
#   (|     | )
#  /'\_   _/`\
#  \___)=(___/