from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message,MessageSegment
from nonebot.params import Arg,ArgPlainText
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot import on_command,on_keyword,on_notice,on_message

import nonebot,asyncio,aiofiles,aiohttp
from mcp.server.fastmcp import FastMCP

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="Project-Maid-Anthropic-MCP",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

action_client = FastMCP("action_client")

'''
以下方法公有
'''
@action_client.tool()
async def chat_send_msg() -> str:
    return "TODO"

@action_client.tool()
async def chat_send_poke() -> str:
    return "TODO"

@action_client.tool()
async def chat_send_sticker() -> str:
    return "TODO"

'''
以下方法私有
'''

@action_client.tool()
async def net_download_jmcomic() -> str:
    return "TODO"

@action_client.tool()
async def net_looking_for_artpic() -> str:
    return "TODO"