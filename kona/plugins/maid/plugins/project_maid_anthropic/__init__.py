from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message,MessageSegment
from nonebot.params import Arg,ArgPlainText
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot import on_command,on_keyword,on_notice,on_message

from openai import AsyncOpenAI

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="Project-Maid-Anthropic",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

'''
以下抽象类/抽象方法公有
'''

class Maid:
    async def __init__(self, Kei:str, prompt:str, length:int) -> None:
        '''**Maid类初始化函数**
        Args:
            Kei: 你的API Key
            prompt: 你的人设提示词
            length: 最大上下文轮数 长度越大 短时记忆越长 同时token消耗量越高 此轮数包括请求轮与回复轮 请使用偶数
        此方法实例化并返回一个AI对象
        '''
        ##初始化属性和OpenAI SDK
        self.Kei = Kei
        self.mind = AsyncOpenAI(api_key=Kei, base_url="https://api.deepseek.com")
        self.context : list[dict[str,str]] = [{"role":"system","content":prompt}]
        self.length = length

    async def Thought(self, messages:list[dict[str,str]]) -> list[str]:
        '''**接收单条或连续消息 Maid回复你单条或连续消息**
        Args:
            messages: 传入单条或连续消息 接收list[dict["user","time","content"]参数
        Returns:
            list[str]
        '''
        content = ""
        #检查上下文长度
        if len(self.context)-1 > self.length:
            tmp = [self.context[0]]
            tmp.extend(self.context[len(self.context)-self.length:])
            self.context = tmp
        #拼接消息
        for seg in messages:
            content = content + f"{seg['user']}[{seg['time']}]:{seg['content']}\n"
        self.context.append({"role":"user","content":content})
        #请求回复
        #response = self.mind.chat.completions.create(model="deepseek-v4-flash")
        #返回<thought><actions>
        