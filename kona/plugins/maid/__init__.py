from pathlib import Path

import nonebot,asyncio,aiofiles,aiohttp
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message,MessageSegment,MessageEvent,PrivateMessageEvent,GroupMessageEvent,NoticeEvent,Event,Bot
from nonebot.params import Arg,ArgPlainText
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.rule import to_me
from nonebot import on_command,on_keyword,on_notice,on_message

from .config import Config
from datetime import datetime

__plugin_meta__ = PluginMetadata(
    name="Maid",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

'''
以下代码为业务代码
'''

from .plugins.project_maid_openai import Maid

PhantomMaid = Maid(48)
PhantomMaid.listen_and_echo()