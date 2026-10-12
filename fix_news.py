with open("commercial_stream.py", "r") as f:
    content = f.read()

content = content.replace(
    "def build_news_5(self) -> Panel: return self._build_news_generic(\"DEV WALLET MOVEMENT\", \"They said they burned the keys.\", \"Local dev caught fleeing to the metaverse on a virtual yacht!\")",
    "def build_news_5(self) -> Panel: return self._build_news_generic(\"DEV WALLET MOVEMENT\", \"They said they burned the keys.\", \"Local dev caught fleeing to the metaverse on a virtual yacht!\")\n    def build_news_6(self) -> Panel: return self._build_news_generic(\"VIRTUAL INFLATION\", \"Digital beans cost 400 SOL.\", \"The metaverse is suffering hyperinflation!\")"
)

with open("commercial_stream.py", "w") as f:
    f.write(content)

print("done")
