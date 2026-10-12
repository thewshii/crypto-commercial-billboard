import re

with open("bot.py", "r") as f:
    content = f.read()

new_start = """    async def start(self):
        \"\"\"Start the bot.\"\"\"
        self.running = True
        await self.initialize()
        self.setup_keyboard_listener()
        
        # Play pixelart logo reveal
        try:
            import config
            if getattr(config, 'USE_PIXEL_BANNERS', False):
                import pixelart
                pixelart.logo_reveal("PUMP ML")
        except Exception:
            pass

        # Display initial dashboard view"""

content = content.replace('    async def start(self):\n        """Start the bot."""\n        self.running = True\n        await self.initialize()\n        self.setup_keyboard_listener()\n\n        # Display initial dashboard view', new_start)

with open("bot.py", "w") as f:
    f.write(content)
