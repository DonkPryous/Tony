import os
import json

from dotenv import load_dotenv
from tornado.httpclient import AsyncHTTPClient

## Load .env
load_dotenv()

class Broadcaster:
    def __init__(self):
        pass

    def __del__(self):
        pass

    async def send(self, sTxt: str) -> None:
        http_client = AsyncHTTPClient()
        ## Send message to slack's hook with appropriate header and json encoding
        await http_client.fetch(os.getenv("HOOK_URL"), lambda response: None, method="POST", headers={"Content-Type" : 'application/json'}, body=json.dumps({"text" : sTxt}))
        http_client.close()


## Singleton class for broadcaster
Broadcaster_Singleton = Broadcaster()

