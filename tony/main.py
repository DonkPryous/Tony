import os
import json
import time
import hashlib
import hmac
import logging
import sys
from typing import Awaitable
import tornado.locks
import tornado.ioloop
import tornado.web

from dotenv import load_dotenv
from tornado import gen
from tornado.log import enable_pretty_logging, LogFormatter
from .broadcaster import Broadcaster_Singleton
from .branch import BranchManagement
from .server import ServerManagement
from .patcher import PatcherClientManagement, PatcherServerManagement
from .api import GameStatusChecker, GameReloader
from .utils import encrypt, decrypt, CONSTANTS, log, get_remote_host

load_dotenv()
enable_pretty_logging()

class BaseHandler(tornado.web.RequestHandler):
    def initialize(self) -> None:
        self.bCanProcess = True
        self.sReturnPost = "Got your request! I'm processing it, give me a moment.."

    def prepare(self) -> None:
        ## Disable verification for built
        if self.settings["debug"]:
            return

        ## Security checkup
        ## 1. Check if request body is a valid slack call
        if not 'X-Slack-Request-Timestamp' in self.request.headers or not 'X-Slack-Signature' in self.request.headers:
            log(f"Odd request coming from host {get_remote_host(self.request)}. Dropping.", "warning")
            self.request.connection.close()
            return

        ## 2. Check timestamp from header
        if abs(int(time.time()) - int(self.request.headers['X-Slack-Request-Timestamp'])) > int(os.getenv("REQUEST_TIMEOUT")):
            log(f"Intrusive requests coming from host {get_remote_host(self.request)}. Dropping.", "warning")
            self.request.connection.close()
            return

        ## 3. Create pre-hashed chain
        secretChain = "v0:" + self.request.headers['X-Slack-Request-Timestamp'] + ":" + self.request.body.decode()

        ## 4. Create hashed signature
        secretSignature = "v0=" + hmac.new(os.getenv("SECRET_ID").encode("utf-8"), secretChain.encode("utf-8"), hashlib.sha256).hexdigest()

        ## 5. Check signature
        if not hmac.compare_digest(secretSignature, self.request.headers['X-Slack-Signature']):
            log(f"Verification was unsuccessful for host {get_remote_host(self.request)}. Dropping.", "warning")
            self.request.connection.close()
            return

        ## 6. Check if request was sent from valid channel
        if self.get_argument("channel_name", "", True).lower() != os.getenv("CHANNEL_NAME").lower():
            log("Request came from not permitted channel {}. Dropping.".format(self.get_argument("channel_name", "", True).lower()), "warning")
            self.sReturnPost = f"Hold your horses mate. Not this channel, have a look at: {os.getenv('CHANNEL_NAME')}"
            self.bCanProcess = False
            return

    def set_default_headers(self) -> None:
        ## This headers are required by slack to validate a response
        self.set_header("Content-Type", 'application/json')

    async def process_request(self, sArguments: str) -> None:
        pass

    async def post(self) -> None:
        ## Write response, send it and wait a bit for slack to process it
        ## Then, process request by using webhook as response handler
        self.write(json.dumps({"text" : self.sReturnPost}))
        await self.flush()
        await self.finish()
        await gen.sleep(0.1)

        if self.__check_status():
            ## Ok, buffer flushed, sleep done, now process command
            await self.process_request(self.get_argument("text", "", True))
            await Broadcaster_Singleton.send("Did what I could. Tony out.")

    def process_error(self, sFuncName: str, rException: Exception) -> None:
        log(f"Following error occured for function: {sFuncName}:", "error")
        log(f"{type(rException).__name__}: {str(rException)}", "error")

    def __check_status(self):
        return self.bCanProcess

    async def unknown_command(self):
        await Broadcaster_Singleton.send("I cannot perform any sort of this action. Double check your command mate!")

class HomeHandler(BaseHandler):
    async def get(self):
        self.write(json.dumps({"text" : "Your reached the place where devil says good night"}))

class BranchHandler(BaseHandler):
    async def process_request(self, sArguments: str):
        log(f"[Branch Handler] A request came from {get_remote_host(self.request)} following arguments: {sArguments}", "info")

        lArguments = sArguments.split()
        if len(lArguments) < 2:
            await self.list_branches()
            return

        if lArguments[1] == "check":
            await self.get_current_branch(lArguments[0])
        elif lArguments[1] == "switch" and len(lArguments) >= 3:
            await self.switch_branch(lArguments[0], lArguments[2])
        elif lArguments[1] == "update":
            await self.update_repository(lArguments[0])
        elif lArguments[1] == "list":
            await self.list_branches(lArguments[0])
        else:
            await self.unknown_command()

    async def switch_branch(self, sType: str, sBranch: str):
        try:
            branchEvent = BranchManagement(Broadcaster_Singleton)
            await branchEvent.change_branch(sType, sBranch)
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        if branchEvent.check_results():
            await Broadcaster_Singleton.send(f"Running branch was switched to {sBranch}!")

    async def get_current_branch(self, sType: str):
        sBranch = ""
        try:
            branchEvent = BranchManagement(Broadcaster_Singleton)
            sBranch = await branchEvent.get_current_branch(sType)
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send("You are currently running on branch:")
        await Broadcaster_Singleton.send(sBranch)

    async def list_branches(self, sType: str = "ALL"):
        sBranches = ""
        try:
            branchEvent = BranchManagement(Broadcaster_Singleton)
            sBranches = await branchEvent.fetch_branch(sType)
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send("Following branches are available:")
        await Broadcaster_Singleton.send(sBranches)

    async def update_repository(self, sType: str = "ALL"):
        sCurBranch = ""
        try:
            branchEvent = BranchManagement(Broadcaster_Singleton)
            sCurBranch = await branchEvent.get_current_branch(sType)
            await branchEvent.update_repository(sType)
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        if branchEvent.check_results():
            await Broadcaster_Singleton.send(f"Branch {sCurBranch.strip()} was updated!")

class ServerHandler(BaseHandler):
    def data_received(self, chunk: bytes) -> Awaitable[None] | None:
        return super().data_received(chunk)

    async def process_request(self, sArguments: str):
        log(f"[Server Handler] A request came from {get_remote_host(self.request)} following arguments: {sArguments}", "info")

        lArguments = sArguments.split()
        if len(lArguments) < 1:
            return

        if len(lArguments) >= 2 and lArguments[1] == "rebuild":
            if lArguments[0] == "core":
                await self.rebuild_core(lArguments[0])
            elif lArguments[0] == "quest":
                await self.rebuild_quest(lArguments[0])
        elif lArguments[0] == "reload" and len(lArguments) >= 2:
            await self.reload_game(lArguments[1])
        elif lArguments[0] == "start":
            await self.start_game()
        elif lArguments[0] == "stop":
            await self.stop_game()
        elif lArguments[0] == "restart":
            await self.restart_game()
        elif lArguments[0] == "update":
            await self.update_server()
        elif lArguments[0] == "status":
            await self.check_status()
        else:
            await self.unknown_command()

    async def rebuild_core(self, sType: str):
        sCurBranch = ""
        try:
            branchEvent = BranchManagement(Broadcaster_Singleton)
            sCurBranch = await branchEvent.get_current_branch(sType)

            serverEvent = ServerManagement(Broadcaster_Singleton)
            await serverEvent.rebuild_core()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send(f"Core was rebuilt! Running branch: {sCurBranch.strip()}")

    async def rebuild_quest(self, sType: str):
        sCurBranch = ""
        try:
            branchEvent = BranchManagement(Broadcaster_Singleton)
            sCurBranch = await branchEvent.get_current_branch("LOCALE")

            serverEvent = ServerManagement(Broadcaster_Singleton)
            await serverEvent.rebuild_quest()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send(f"Quest was rebuilt! Running branch: {sCurBranch.strip()}")

    async def start_game(self):
        try:
            serverEvent = ServerManagement(Broadcaster_Singleton)
            await serverEvent.start_game()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send("Server was started!")

    async def stop_game(self):
        try:
            serverEvent = ServerManagement(Broadcaster_Singleton)
            await serverEvent.stop_game()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send("Server was stopped!")

    async def restart_game(self):
        try:
            serverEvent = ServerManagement(Broadcaster_Singleton)
            await serverEvent.restart_game()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send("Server was restarted!")

    async def update_server(self):
        try:
            serverEvent = ServerManagement(Broadcaster_Singleton)
            await serverEvent.update_server()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send("Server was updated!")

    async def check_status(self):
        try:
            serverEvent = GameStatusChecker(Broadcaster_Singleton)
            await serverEvent.check_channels_status()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

    async def reload_game(self, sType : str):
        try:
            ## First, update branch
            branchEvent = BranchManagement(Broadcaster_Singleton)
            sCurBranch = await branchEvent.get_current_branch(sType)
            await branchEvent.update_repository(sType)

            ## Then, rebuild quest
            await self.rebuild_quest("")

            ## And now, reload game
            serverEvent = GameReloader(Broadcaster_Singleton)
            await serverEvent.reload_game(sType)
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        await Broadcaster_Singleton.send("Game was reloaded!")

class PatcherClientHandler(BaseHandler):
    def data_received(self, chunk: bytes) -> Awaitable[None] | None:
        return super().data_received(chunk)

    async def process_request(self, sArguments: str):
        if len(os.getenv("PATCHER_HOST", "")) == 0:
            await Broadcaster_Singleton.send("Patcher is not configured!")
            return

        log(f"[Patcher Client Handler] A request came from {get_remote_host(self.request)} following arguments: {sArguments}", "info")

        lArguments = sArguments.split()
        if len(lArguments) < 1:
            return

        if lArguments[0] == "switch" and len(lArguments) >= 2:
            await self.switch_branch(lArguments[1])
        elif lArguments[0] == "check":
            await self.check_branch()
        elif lArguments[0] == "update":
            await self.update_repository()
        else:
            await self.unknown_command()

    async def switch_branch(self, sBranch: str):
        branchEvent = None

        try:
            branchEvent = PatcherClientManagement(Broadcaster_Singleton)
            await branchEvent.switch_branch(sBranch)
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        if branchEvent.check_results():
            await Broadcaster_Singleton.send(f"Running branch was switched to {sBranch}!")

    async def check_branch(self):
        branchEvent = None
        sCurBranch = ""

        try:
            branchEvent = PatcherClientManagement(Broadcaster_Singleton)
            sCurBranch = await branchEvent.get_branch()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        if branchEvent.check_results():
            await Broadcaster_Singleton.send(f"Patcher's running branch: {sCurBranch} and files's list was rebuilt!")

    async def update_repository(self):
        branchEvent = None

        try:
            branchEvent = PatcherClientManagement(Broadcaster_Singleton)
            await branchEvent.update_repository()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            return

        if branchEvent.check_results():
            await Broadcaster_Singleton.send("Patcher's list was updated!")

class PatcherServerHandler(BaseHandler):
    def data_received(self, chunk: bytes) -> Awaitable[None] | None:
        return super().data_received(chunk)

    def prepare(self):
        ## Check if I'm a patcher server
        if not os.getenv("IS_PATCHER_SERVER"):
            log(f"A request came from {get_remote_host(self.request)} but I'm not a patcher server. Dropping.", "warning")
            self.request.connection.close()
            return

        ## Check headers
        if not "Content-Type" in self.request.headers or self.request.headers["Content-Type"] != "application/json":
            log(f"Odd request coming from host {get_remote_host(self.request)}. Dropping.", "warning")
            self.request.connection.close()
            return

        ## Validate greetings message
        sMess = self.request.headers.get("Content-Message", "")
        if len(sMess) == 0:
            log("No greetings came from host {get_remote_host(self.request)}. Dropping.", "warning")
            self.request.connection.close()
            return

        ## Decipher it
        try:
            sMess = decrypt(sMess)
        except Exception:
            ## Decrypting failed
            ## This host is not allowed to connect
            log(f"Couldn't verify greetings from host {get_remote_host(self.request)}. Dropping.", "warning")
            self.request.connection.close()
            return

        ## Compare
        if sMess != CONSTANTS["PATCHER_GREETINGS"]:
            ## Messages don't match
            log(f"Couldn't verify greetings from host {get_remote_host(self.request)}. Dropping.", "warning")
            self.request.connection.close()
            return

        ## Everything is ok, you are allowed to connect

    async def get(self):
        log(f"[Patcher Server Handler] GET request came from host {get_remote_host(self.request)}.", "info")

        patcherEvent = None
        try:
            patcherEvent = PatcherServerManagement(Broadcaster_Singleton)
            await patcherEvent.send_branch()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            pass

        ## Process results and send it to request host
        (iResponse, sStdo, sStdr) = patcherEvent.lResults
        self.write(json.dumps({"error_code" : encrypt(iResponse), "error_message" : encrypt(sStdr), "branch" : encrypt(sStdo)}))

    async def post(self):
        log(f"[Patcher Server Handler] POST request came from host {get_remote_host(self.request)}.", "info")

        patcherEvent = None
        try:
            patcherEvent = PatcherServerManagement(Broadcaster_Singleton)
            jsResponse = json.loads(self.request.body)
            if jsResponse.get("type", "") == "switch":
                await patcherEvent.switch_branch(jsResponse.get("branch", ""))
            else:
                await patcherEvent.update_repository()
        except Exception as e:
            self.process_error(sys._getframe().f_code.co_name, e)
            pass

        ## Process results and send it to request host
        (iResponse, sStdo, sStdr) = patcherEvent.lResults
        self.write(json.dumps({"error_code" : encrypt(iResponse), "error_message" : encrypt(sStdr), "branch" : encrypt(sStdo)}))

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/branch", BranchHandler),
            (r"/server", ServerHandler),
            (r"/patcher", PatcherClientHandler),
            (r"/patcher_server", PatcherServerHandler),
        ]

        settings = {"title":"Tony", "debug":(os.getenv("DEBUG").lower() == "true"),
            "logging":("debug" if (os.getenv("DEBUG").lower() == "true") else "info"),
            "autoreload":False
        }

        super().__init__(handlers, **settings)

async def main():
    app = Application()
    app.listen(os.getenv("APP_PORT"), os.getenv("APP_HOST"))

    ## Setup loggers
    hLogger = logging.FileHandler(os.getenv("LOG_FILE"))
    hLogger.setFormatter(LogFormatter(color=True))
    lTornadoLoggers = (logging.getLogger("tornado.access"), logging.getLogger("tornado.application"), logging.getLogger("tornado.general"))

    for rLogger in lTornadoLoggers:
        rLogger.addHandler(hLogger)

    ## Assembly consumer and producer
    print("App PID: {os.getpid()}")

    shutdown_event = tornado.locks.Event()
    await shutdown_event.wait()

if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().run_sync(main)

