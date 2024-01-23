import asyncio
import socket

from .broadcaster import Broadcaster
from .utils import CONSTANTS

class GameAPIConnector:

    STATUS_CHECK_TIMEOUT = 3
    WRITE_TIMEOUT = 60
    GAME_HEADER = "\x40"

    def __init__(self, lConnectionInfo : list, rBroadcaster: Broadcaster):
        self.lConnectionInfo = lConnectionInfo
        self.rBroadcaster = rBroadcaster
        self.sockReader, self.sockerWriter = None, None

    def __del__(self):
        self.clear()

    async def clear(self):
        if self.sockerWriter:
            self.sockerWriter.close()
            await self.sockerWriter.wait_closed()

        self.sockReader, self.sockerWriter = None, None

    async def __write(self, sData):
        self.sockerWriter.write("{}{}\n".format(self.GAME_HEADER, sData).encode("utf-8"))
        await self.sockerWriter.drain()

    async def __read(self):
        sRed = await self.sockReader.read(128)
        if sRed.find(b"\x00") != -1:
            sRed = sRed[sRed.rfind(b"\x00") + 1:]

        return sRed.decode("ascii", "ignore").replace("\r", "").replace("\n", " ")

    def get_connection_info(self):
        return self.lConnectionInfo

    async def establish_connection(self, iTimeout : int):
        await self.clear()

        try:
            rFuture = asyncio.open_connection(*self.lConnectionInfo)
            (self.sockReader, self.sockerWriter) = await asyncio.wait_for(rFuture, timeout=iTimeout)
        except Exception:
            return "OFF"

        return "ON"

    async def send_call(self, sCall):
        ## Establish connection
        sStatus = await self.establish_connection(self.WRITE_TIMEOUT)
        if sStatus == "OFF":
            return None

        ## Send password
        await self.__write(CONSTANTS["GAME_API_PASS"])
        sRes = await self.__read()
        if sRes.find("SUCCESS") == -1:
            return sRes

        ## Send call
        await self.__write(sCall)

        ## Return result
        sRes = await self.__read()
        return sRes

class GameStatusChecker(GameAPIConnector):
    def __init__(self, rBroadcaster):
        super().__init__([], rBroadcaster)
        self.rBroadcaster = rBroadcaster

    def __del__(self):
        super().__del__()
        self.rBroadcaster = None

    async def check_channels_status(self):
        await self.rBroadcaster.send("Checking server status..")

        sReturnStr = ""
        ## Check game
        for iNum, iPortNum in enumerate(CONSTANTS["GAME_PORTS"]):
            self.lConnectionInfo = (CONSTANTS["GAME_HOST"], iPortNum)
            sRes = await self.establish_connection(self.STATUS_CHECK_TIMEOUT)
            sReturnStr += f"{CONSTANTS['GAME_PORTS_NAME'][iNum]} status: *{sRes}*\n"

        ## Check auth
        self.lConnectionInfo = (CONSTANTS["GAME_HOST"], CONSTANTS["GAME_AUTH_PORT"])
        sRes = await self.establish_connection(self.STATUS_CHECK_TIMEOUT)
        sReturnStr += f"Auth status: *{sRes}*\n"

        await self.rBroadcaster.send(sReturnStr)

class GameReloader(GameAPIConnector):

    RELOAD_TYPES : dict = {
        "LOCALE" : "RELOAD_LOCALE",
        "PROTO" : "RELOAD_PROTOS",
        "ALL" : "RELOAD_ALL",
    }

    def __init__(self, rBroadcaster):
        super().__init__([], rBroadcaster)
        self.rBroadcaster = rBroadcaster

    def __del__(self):
        super().__del__()
        self.rBroadcaster = None

    async def reload_game(self, sType : str):
        if not sType.upper() in self.RELOAD_TYPES:
            await self.rBroadcaster.send(f"Requested type is not found in reload list: {sType}")
            return

        await self.rBroadcaster.send("Reloading server as requested..")

        sRes = ""
        for iNum, iPortNum in enumerate(CONSTANTS["GAME_PORTS"]):
            self.lConnectionInfo = (CONSTANTS["GAME_HOST"], iPortNum)
            sStat = ""

            if sType != "ALL":
                sStat = await self.send_call(self.RELOAD_TYPES[sType.upper()])
            else:
                sStat = await self.send_call(self.RELOAD_TYPES[sType.upper()] if iNum == 0 else "LOCALE") ## We need to reload proto only once

            if not sStat:
                sRes += f"Cannot reload {CONSTANTS['GAME_PORTS_NAME'][iNum]} because it's off!\n"
            else:
                sRes += f"Return message from {CONSTANTS['GAME_PORTS_NAME'][iNum]}: *{sStat}*\n"

            if sType.upper() == "PROTO":
                await self.rBroadcaster.send("Protos have been reloaded!")
                return ## We do not need to iterate further

        await self.rBroadcaster.send(sRes)
