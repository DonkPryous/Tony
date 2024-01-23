import os
import json
import xml.etree.ElementTree as ET
from hashlib import md5
from xml.dom import minidom

from tornado.httpclient import AsyncHTTPClient
from .task import BaseTask
from .utils import CONSTANTS, encrypt, decrypt
from .branch import BranchManagement
from .broadcaster import Broadcaster

class PatcherClientManagement(BaseTask):
    def __init__(self, rBroadcaster: Broadcaster):
        super().__init__(rBroadcaster)

        ## Initialize http client
        self.hHttpClient = AsyncHTTPClient()

    def __del__(self):
        super().__del__()
        self.hHttpClient.close()

    async def get_branch(self) -> str:
        ## Request branch from remote host by sending encrypted message
        ## If message doesn't match, host will close the connection
        jsResponse = await self.hHttpClient.fetch(CONSTANTS["PATCHER_HOST"], lambda err: None, method="GET", headers={"Content-Type" : 'application/json', 'Content-Message' : encrypt(self.get_greetings())}, body=None, request_timeout=float(os.getenv("REQUEST_TIMEOUT")))
        jsResponse = json.loads(jsResponse.body)

        if int(decrypt(jsResponse["error_code"])) != 0:
            await self.rBroadcaster.send("An error occured when tried to check the branch!")
            await self.rBroadcaster.send("Error message:")
            await self.rBroadcaster.send(decrypt(jsResponse["error_message"]))

        ## Decrypt incoming results
        self.lResults = (int(decrypt(jsResponse["error_code"])), decrypt(jsResponse["branch"]), decrypt(jsResponse["error_message"]))
        return self.lResults[1]

    async def switch_branch(self, sBranch: str) -> None:
        ## Request branch from remote host by sending encrypted message
        ## If message doesn't match, host will close the connection
        jsResponse = await self.hHttpClient.fetch(CONSTANTS["PATCHER_HOST"], lambda err: None, method="POST", headers={"Content-Type" : 'application/json', 'Content-Message' : encrypt(self.get_greetings())}, body=json.dumps({"branch" : encrypt(sBranch), "type" : "switch"}), request_timeout=float(os.getenv("REQUEST_TIMEOUT")))
        jsResponse = json.loads(jsResponse.body)

        if int(decrypt(jsResponse["error_code"])) != 0:
            await self.rBroadcaster.send("An error occured when tried to switch the branch!")
            await self.rBroadcaster.send("Error message:")
            await self.rBroadcaster.send(decrypt(jsResponse["error_message"]))

        self.lResults = (int(decrypt(jsResponse["error_code"])), decrypt(jsResponse["branch"]), decrypt(jsResponse["error_message"]))

    async def update_repository(self) -> None:
        ## Update repository on remote host by sending encrypted message
        ## If message doesn't match, host will close the connection
        jsResponse = await self.hHttpClient.fetch(CONSTANTS["PATCHER_HOST"], lambda err: None, method="POST", headers={"Content-Type" : 'application/json', 'Content-Message' : encrypt(self.get_greetings())}, body=json.dumps({"branch" : "", "type" : "update"}), request_timeout=float(os.getenv("REQUEST_TIMEOUT")))
        jsResponse = json.loads(jsResponse.body)

        if int(decrypt(jsResponse["error_code"])) != 0:
            await self.rBroadcaster.send("An error occured when tried to switch the branch!")
            await self.rBroadcaster.send("Error message:")
            await self.rBroadcaster.send(decrypt(jsResponse["error_message"]))

        self.lResults = (int(decrypt(jsResponse["error_code"])), decrypt(jsResponse["branch"]), decrypt(jsResponse["error_message"]))

    def get_secret(self) -> str:
        return CONSTANTS["SECRET_ID_PATCHER"]

    def get_greetings(self) -> str:
        return CONSTANTS["PATCHER_GREETINGS"]

class PatcherServerManagement(BaseTask):

    EXCEPTION_EXTENSIONS: tuple[str] = ("xml", "php")
    EXCEPTION_DIRS: tuple[str] = (".git", )
    EXCEPTION_FILES: tuple[str] = ("index.xml", "index.html", ".gitkeep")

    def __init__(self, rBroadcaster: Broadcaster):
        super().__init__(rBroadcaster)

        ## Initialize http client
        self.hHttpClient = AsyncHTTPClient()

    def __del__(self):
        super().__del__()
        self.hHttpClient.close()

    async def send_branch(self) -> None:
        ## Get current branch
        branchEvent = None
        sBranchName = ""

        try:
            branchEvent = BranchManagement(self.rBroadcaster)
            sBranchName = await branchEvent.get_current_branch("PATCHER", bIgnoreResults=True, bSilentCall=True)
        except Exception:
            ## Let it go
            ## Error will be processed by server nonetheless
            return
        finally:
            self.lResults = branchEvent.lResults

        ## Setting formatted branch
        self.lResults = branchEvent.lResults

    async def update_repository(self) -> None:
        ## Get current branch
        branchEvent = None

        try:
            branchEvent = BranchManagement(self.rBroadcaster)
            await branchEvent.update_repository("PATCHER", bIgnoreResults=True, bSilentCall=True)
        except Exception:
            ## Let it go
            ## Error will be processed by server nonetheless
            return
        finally:
            self.lResults = branchEvent.lResults

        ## Setting formatted branch
        self.lResults = branchEvent.lResults
        if self.check_results():
            self.__generate_list()
            self.lResults = branchEvent.lResults

    async def switch_branch(self, sBranch: str) -> None:
        ## Decode incoming branch
        sBranch = decrypt(sBranch)

        ## Get branch list
        branchEvent = None
        lBranches = []

        try:
            branchEvent = BranchManagement(self.rBroadcaster)
            lBranches = await branchEvent.fetch_branch("PATCHER", bIgnoreResults=True, bSilentCall=True)
        except Exception:
            ## Let it go
            ## Error will be processed by server nonetheless
            pass

        self.lResults = branchEvent.lResults
        if self.check_results():
            if not sBranch in lBranches:
                self.lResults[0] = 1
                self.lResults[2] = f"Branch {sBranch} doesn't exist on server repo!"
            else:
                await branchEvent.change_branch("PATCHER", sBranch, bIgnoreResults=True, bSilentCall=True)
                self.__generate_list()
                self.lResults = branchEvent.lResults

    def __generate_list(self) -> None:
        ## Save current path
        sCurDir = os.getcwd()

        ## Top node for xml
        xmlRoot = ET.Element("FileProfiler", {"FormatVersion" : "1"})
        xmlFileList = ET.SubElement(xmlRoot, "File_List")

        ## Walk to patcher public directory
        os.chdir(CONSTANTS["PATCHER_ABSOLUTE_FILES_PATH"])
        for (root, _, files) in os.walk(".", topdown=True):
            ## Checking for excepted dirs
            bFound = False
            for sDir in self.EXCEPTION_DIRS:
                if root.find(sDir) != -1:
                    bFound = True
                    continue

            if bFound:
                continue
				
            for sFile in files:
                sExt = sFile[sFile.rfind(".")+1:] if sFile.rfind(".") != -1 else ""
                if sExt in self.EXCEPTION_EXTENSIONS:
                    ## Skip this extension
                    continue

                ## Checking for excepted files
                if sFile in self.EXCEPTION_FILES:
                    ## Skip this extension
                    continue

                ## Generating nodes
                ET.SubElement(xmlFileList, "File", {"FileName" : os.path.join(root, sFile)[2:],
                                                    "FileSize" : str(os.path.getsize(os.path.join(root, sFile))),
                                                    "FileMD5" : self.__get_file_md5(os.path.join(root, sFile))})

        ## Saving xml
        with open("index.xml", "w", encoding="utf-8") as hFile:
            hFile.write(self.__prettify(xmlRoot))

        ## Jumping back to home dir
        os.chdir(sCurDir)

    def __get_file_md5(self, sFileName: str) -> str:
        ## Process file without chunking
        md5CheckSummer = md5()
        with open(sFileName, "rb") as hFile:
            md5CheckSummer.update(hFile.read())

        return md5CheckSummer.hexdigest()

    def __prettify(self, elem: str) -> str:
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
