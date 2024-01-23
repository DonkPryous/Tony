import os
import time
import subprocess

from tornado import gen
from .broadcaster import Broadcaster
from .utils import CONSTANTS

class BaseTask:

    DEFAULT_TIMEOUT: int = 60*5

    def __init__(self, rBroadcaster: Broadcaster, user: str = CONSTANTS["SERVER_USER"], lCommand: str = ""):
        self.rBroadcaster = rBroadcaster
        self.sUserName = user
        self.lCommand = lCommand
        self.lResults = [-1, "NOT SET", "NOT SET"]

    def __del__(self):
        pass

    async def run(self, bSkipOutput: bool = False, bIgnoreResults: bool = False, bSilentCall: bool = False) -> None:
        ## Save directory for any walk that my happen
        sCurDir = os.getcwd()

        for sCommand, sNotification in self.lCommand:
            ## If there is any corresponding notification, send it now
            if len(sNotification) > 0 and not bSilentCall:
                await self.rBroadcaster.send(sNotification)

            ## Check if command is a walk
            if sCommand.find("cd") != -1:
                try:
                    os.chdir(sCommand.strip("cd").strip(" "))
                except Exception as e:
                    self.lResults = [1, "", f"An error occured when trying to access path: {e}"]
                    ## Always check results before carry on (well.. with exception)
                    if not bIgnoreResults:
                        await self.results()
                    return
            else:
                ## Fork a child
                with subprocess.Popen(sCommand, shell=True, user=self.sUserName, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
                    ## We cannot use proc.wait() due to lack of courtine implementation (block whole thread)
                    ttStartTime = int(time.time())
                    while proc.poll() == None:
                        await gen.sleep(0.1)
                        if int(time.time())-ttStartTime >= self.DEFAULT_TIMEOUT:
                            break

                    self.lResults = [proc.returncode, "".join(map(lambda item: item.decode(), proc.stdout.readlines())) if not bSkipOutput else "", "".join(map(lambda item: item.decode(), proc.stderr.readlines())) if not bSkipOutput else ""]

                    ## Always check results before carry on (well.. with exception)
                    if not bIgnoreResults:
                        try:
                            await self.results()
                        except Exception:
                            if len(self.lResults[2]) == 0:
                                proc.terminate()

                            os.chdir(sCurDir)
                            return

        ## Restore working dir
        os.chdir(sCurDir)

    def check_results(self) -> bool:
        return self.lResults[0] == 0

    def get_error(self) -> str:
        return self.lResults[1]

    async def results(self) -> list[str]:
        if not self.check_results():
            await self.rBroadcaster.send("An error occurred during command's execution!")
            await self.rBroadcaster.send(f"Error code: {self.lResults[0]}")
            await self.rBroadcaster.send(f"Error message: {self.lResults[2]}")
            raise RuntimeError

        return self.lResults
