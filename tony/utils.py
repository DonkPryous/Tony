import re
import os
import logging

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

CONSTANTS: dict = {
    "SECRET_ID_PATCHER" : os.getenv("SECRET_ID_PATCHER").encode("utf-8"),
    "PATCHER_GREETINGS" : os.getenv("PATCHER_GREETINGS"),
    "SERVER_USER" : os.getenv("SERVER_USER"),
    "BASE_DIRECTORY" : os.getenv("BASE_DIRECTORY"),
    "ENCODING_TYPE" : os.getenv("ENCODING_TYPE"),
    "SERVER_RELATIVE_PATH" : os.getenv("SERVER_RELATIVE_PATH"),
    "CORE_RELATIVE_PATH" : os.getenv("CORE_RELATIVE_PATH"),
    "LOCALE_RELATIVE_PATH" : os.getenv("SERVER_RELATIVE_PATH") + os.getenv("LOCALE_RELATIVE_PATH"),
    "QUEST_RELATIVE_PATH" : os.getenv("SERVER_RELATIVE_PATH") + os.getenv("QUEST_RELATIVE_PATH"),
    "COMPILATION_COMMAND" : os.getenv("COMPILATION_COMMAND"),
    "START_COMMAND" : os.getenv("START_COMMAND"),
    "STOP_COMMAND" : os.getenv("STOP_COMMAND"),
    "PATCHER_HOST" : os.getenv("PATCHER_HOST"),
    "PATCHER_ABSOLUTE_FILES_PATH" : os.getenv("PATCHER_ABSOLUTE_FILES_PATH"),
    "GAME_HOST" : os.getenv("GAME_HOST"),
    "GAME_PORTS" : os.getenv("GAME_PORTS").strip().split(","),
    "GAME_AUTH_PORT" : os.getenv("GAME_AUTH_PORT"),
    "GAME_PORTS_NAME" : os.getenv("GAME_PORTS_NAME").strip().split(","),
    "GAME_API_PASS" : os.getenv("GAME_API_PASS"),
}

LOGGING_TYPE: dict = {
    "debug" : logging.debug,
    "info" : logging.info,
    "warning" : logging.warning,
    "error" : logging.error
}

def beautify_results(sOutput: str) -> str:
    sNewOutput = []
    for line in sOutput.split("\n"):
        try:
            line = line.decode()
        except Exception:
            pass

        if line.find("->") != -1:
            ## Skip references
            continue

        try:
            ## Look out for regen pattern
            line = re.findall(r"(?:origin/*)+(\S*)", line)[0]
        except Exception:
            pass

        ## Read string up to nline
        sNewOutput.append(line)

    return "\n".join(sNewOutput)

def encrypt(sTxt) -> str:
    hFernet = Fernet(CONSTANTS["SECRET_ID_PATCHER"])
    if not type(sTxt) is str:
        sTxt = str(sTxt)

    return hFernet.encrypt(sTxt.encode("utf-8")).decode()

def decrypt(sTxt) -> str:
    hFernet = Fernet(CONSTANTS["SECRET_ID_PATCHER"])
    if not type(sTxt) is bytes:
        sTxt = sTxt.encode("utf-8")

    return hFernet.decrypt(sTxt).decode()

def log(sTxt: str, sType: str="info") -> None:
    global LOGGING_TYPE
    LOGGING_TYPE[sType](sTxt)

def get_remote_host(rRequest: str) -> str:
    return rRequest.headers.get("X-Real-IP") or rRequest.headers.get("X-Forwarded-For") or rRequest.remote_ip
