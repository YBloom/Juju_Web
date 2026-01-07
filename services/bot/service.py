
import asyncio
import logging
from ncatbot.core import BotClient, GroupMessage, PrivateMessage
from services.hulaquan.service import HulaquanService
from services.bot.handlers import BotHandler
from services.bot.notifier import BotNotifier

log = logging.getLogger(__name__)

class BotService:
    def __init__(self):
        self.client = BotClient()
        self.hlq_service = HulaquanService()
        self.handler = BotHandler(self.hlq_service)
        self.notifier = BotNotifier(self.client)
        
        self._setup_events()

    def _setup_events(self):
        @self.client.group_event()
        async def on_group_message(msg: GroupMessage):
            # Self Ignore
            # if msg.user_id == self.client.self_id: return
            
            response = await self.handler.handle_group_message(
                group_id=msg.group_id,
                user_id=msg.user_id,
                message=msg.raw_message, 
                sender_role=msg.sender.role # Assuming sender object exists
            )
            
            if response:
                await self.client.send_group_msg(group_id=msg.group_id, message=response)

        @self.client.private_event()
        async def on_private_message(msg: PrivateMessage):
             # Handle private commands if needed
             pass

    async def start(self, **kwargs):
        """Start the bot client."""
        log.info("Starting Bot Service...")
        
        # Start Notifier
        asyncio.create_task(self.notifier.start())
        
        # Start Bot Client
        # run() is usually blocking in older versions, but in v4 with asyncio, it might be async 
        # or we use start() if available.
        # Based on typical OneBot libs, run() is the entry point.
        # If run() blocks, we need to be careful about task scheduling.
        # But this is "main_bot.py", so blocking is fine.
        
        # NOTE: ncatbot v4 run() might handle loop.
        # We need to configure it via config.yaml or arguments.
        # We will assume env vars or file config is handled by ncatbot internal logic.
        
        # Re-using the logic from old main.py to set config path if needed?
        # Old main.py patched config. Here we rely on standard ncatbot config. 
        # User should ensure config/onebot11_<qq>.json exists.
        
        # Use a dummy User ID for run? Or read from config?
        # The user provided "3044829389" in main.py.
        await self.client.run() 

    async def stop(self):
        await self.notifier.stop()
        await self.hlq_service.close()
