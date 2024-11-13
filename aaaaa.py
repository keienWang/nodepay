import asyncio
import aiohttp
import time
import requests
import uuid
from loguru import logger
from colorama import Fore, Style, init
import sys
import logging
logging.disable(logging.ERROR)

# Initialize colorama
init(autoreset=True)

# Customize loguru to use color for different log levels
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{message}</level>", colorize=True)
logger.level("INFO", color=f"{Fore.GREEN}")
logger.level("DEBUG", color=f"{Fore.CYAN}")
logger.level("WARNING", color=f"{Fore.YELLOW}")
logger.level("ERROR", color=f"{Fore.RED}")
logger.level("CRITICAL", color=f"{Style.BRIGHT}{Fore.RED}")



PING_INTERVAL = 180
RETRIES = 120
TOKEN_FILE = 'np_tokens.txt'

DOMAIN_API = {
    "SESSION": "http://18.136.143.169/api/auth/session",
    "PING": "http://54.255.192.166/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}

def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

proxy_auth_status = {}

async def render_profile_info(token):
    global browser_id, account_info

    try:

        browser_id = uuidv4()
        response = await call_api(DOMAIN_API["SESSION"], {}, token)
        if response is None:
            return
        valid_resp(response)
        account_info = response["data"]
        if account_info.get("uid"):
            save_session_info(account_info)
        else:
            handle_logout()
            return
        await start_ping( token)
    except Exception as e:
        pass

async def call_api(url, data, token, max_retries=3):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://app.nodepay.ai",
    }

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=True)) as session:
        for attempt in range(max_retries):
            try:
                async with session.post(url, json=data, headers=headers, timeout=10) as response:
                    response.raise_for_status()
                    resp_json = await response.json()
                    return valid_resp(resp_json)

            except aiohttp.ClientResponseError as e:

                if e.status == 403:
                    return None
            except aiohttp.ClientConnectionError as e:
                pass

            except Exception as e:
                pass

            await asyncio.sleep(2 ** attempt)

    #logger.error(f"{Fore.RED}Failed API call to {url} after {max_retries} attempts with proxy {proxy}")
    return None

async def start_ping(token):
    try:
        while True:
            await ping(token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"{Fore.YELLOW}Ping task for proxy  was cancelled")
    except Exception as e:
        logger.error(f"{Fore.RED}Error in start_ping for proxy {e}")

async def ping(token):
    global last_ping_time, RETRIES, status_connect
    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time()),
            "version": '2.2.7'
        }

        response = await call_api(DOMAIN_API["PING"], data, token)
        if response["code"] == 0:
            logger.info(f"{Fore.GREEN}Ping successful via proxy: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(response)
    except Exception as e:

        handle_ping_fail( None)

def handle_ping_fail( response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout()
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout():
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    logger.info(f"{Fore.YELLOW}Logged out and cleared session info for proxy")


def save_session_info(data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": browser_id
    }
    pass


def load_tokens_from_file(filename):
    try:
        with open(filename, 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")


async def main():
    await asyncio.sleep(3)
    tokens = load_tokens_from_file(TOKEN_FILE)

    while True:
        for token in tokens:
            await render_profile_info( token)
            await asyncio.sleep(3)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
