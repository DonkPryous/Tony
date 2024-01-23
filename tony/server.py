import os

from .task import BaseTask
from .branch import BranchManagement
from .utils import CONSTANTS
from .broadcaster import Broadcaster

class ServerManagement(BaseTask):

    LIST_NAME: str = "locale_list"
    SOURCE_COMPILATION: tuple[str, str] = (("cd {}/{}".format(CONSTANTS["BASE_DIRECTORY"], CONSTANTS["CORE_RELATIVE_PATH"]), "Entering source directory.."), (CONSTANTS["COMPILATION_COMMAND"], "Rebuilding source from scratches.."))
    QUEST_COMPILATION_PREBUILD: tuple[str, str] = (("cd {}/{}".format(CONSTANTS["BASE_DIRECTORY"], CONSTANTS["QUEST_RELATIVE_PATH"]), "Entering quest directory.."), 
                        ("rm -rf object", "Removing object direcory.."),
                        ("mkdir object", "Recreacting object directory.."),
    )
    QUEST_COMPILATION_COMMAND: str = "./qc {}"
    SERVER_START: tuple[str, str] = (("cd {}/{}".format(CONSTANTS["BASE_DIRECTORY"], CONSTANTS["SERVER_RELATIVE_PATH"]), "Entering server directory.."), (CONSTANTS["START_COMMAND"], "Starting server.."))
    SERVER_STOP: tuple[str, str] = (("cd {}/{}".format(CONSTANTS["BASE_DIRECTORY"], CONSTANTS["SERVER_RELATIVE_PATH"]), "Entering server directory.."), (CONSTANTS["STOP_COMMAND"], "Stopping server.."))

    def __init__(self, rBroadcaster: Broadcaster):
        super().__init__(rBroadcaster)

    async def rebuild_core(self) -> None:
        ## Stop server
        await self.rBroadcaster.send("Stopping server if running..")
        await self.stop_game(bIgnoreResults = True) ## Try to stop game regardless of current status

        ## Update repo
        await self.rBroadcaster.send("Updating server repo..")
        cBranch = BranchManagement(self.rBroadcaster)
        await cBranch.update_repository("CORE")

        ## Run rebuild script
        await self.rBroadcaster.send("Rebuilding core..")
        self.lCommand = self.SOURCE_COMPILATION
        await self.run()

        ## Start game again
        await self.rBroadcaster.send("Starting server..")
        await self.start_game()

    async def rebuild_quest(self) -> None:
        await self.rBroadcaster.send("Cleaning up old work..")
        ## Run prebuild events
        self.lCommand = self.QUEST_COMPILATION_PREBUILD
        await self.run()

        ## Keep directory
        sCurDir = os.getcwd()

        ## Move into quest directory
        os.chdir(os.path.join(CONSTANTS["BASE_DIRECTORY"], CONSTANTS["QUEST_RELATIVE_PATH"]))

        ## Update repo
        await self.rBroadcaster.send("Updating server repo..")
        cBranch = BranchManagement(self.rBroadcaster)
        await cBranch.update_repository("LOCALE")

        await self.rBroadcaster.send("Rebuilding quests..")
        ## Recreate locale_list
        with open(self.LIST_NAME, mode="r+", encoding=CONSTANTS["ENCODING_TYPE"]) as fList:
            ## Keep track on compilation success rate
            sOutput = ""
            iCount = 0
            iFullCount = 0

            for line in fList:
                ## Refactored make.py
                iFullCount += 1
                filename = line

                self.lCommand = ((self.QUEST_COMPILATION_COMMAND.format(filename), ""), )
                sOutput += f"Compiling {line.strip()}.." + "\n"

                try:
                    await self.run()
                except Exception:
                    pass

                if not self.check_results():
                    sOutput = f"An error occured during compilation of {line}"
                    sOutput = "Compilation outputs following error:"
                    sOutput = self.lResults[2]
                    continue
                else:
                    sOutput += f"{line.strip()} was compiled successfully!" + "\n"
                    iCount += 1

            ## Send output as one message
            ## We don't jam slack with tons of notifications
            await self.rBroadcaster.send(sOutput[:-1])
            self.lCommand = (("chmod -R 770 object", "Setting permission to object folder.."), )
            await self.run()
            await self.rBroadcaster.send(f"{iCount}/{iFullCount} quests were compiled successfully!")

            ## Move back to main dir
            os.chdir(sCurDir)

    async def start_game(self, **kwargs) -> None:
        self.lCommand = self.SERVER_START
        await self.run(bSkipOutput = True, **kwargs) ## Skip output (we don't need that much of data processed)

    async def stop_game(self, **kwargs) -> None:
        self.lCommand = self.SERVER_STOP
        await self.run(bSkipOutput = True, **kwargs) ## Skip output (we don't need that much of data processed)

    async def restart_game(self, **kwargs) -> None:
        await self.rBroadcaster.send("Restarting server..")
        await self.stop_game(**kwargs)
        await self.start_game(**kwargs)
    
    async def update_server(self, **_) -> None:
        eventBranch = BranchManagement(self.rBroadcaster)
        await eventBranch.update_repository("LOCALE")
