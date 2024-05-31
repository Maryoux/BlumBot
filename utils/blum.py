import random
from utils.core import logger
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestWebView, GetMessagesViews
import asyncio
from urllib.parse import unquote
from data import config
import aiohttp
from fake_useragent import UserAgent
import time

class Start:
    def __init__(self, thread: int, account: str, proxy: [str, None]):
        self.proxy = f"http://{proxy}" if proxy is not None else None
        self.thread = thread

        if proxy:
            proxy = {
                "scheme": "http",
                "hostname": proxy.split(":")[1].split("@")[1],
                "port": int(proxy.split(":")[2]),
                "username": proxy.split(":")[0],
                "password": proxy.split(":")[1].split("@")[0]
            }

        self.client = Client(name=account, api_id=config.API_ID, api_hash=config.API_HASH, workdir=config.WORKDIR, proxy=proxy)

        headers = {'User-Agent': UserAgent(os='android').random}
        self.session = aiohttp.ClientSession(headers=headers, trust_env=True)

    async def main(self):
        await asyncio.sleep(random.uniform(config.ACC_DELAY[0], config.ACC_DELAY[1]))
        await self.login()

        while True:
            try:
                currentTimestamp = time.time()
                tokenExp = self.token_expiry-currentTimestamp
                
                # Relogin logic (refresh the token if necessary)
                if (tokenExp <=0):
                    await self.relogin()
                    logger.success(f"Thread {self.thread} | Token refreshed.")
                else:
                    msg = await self.claim_daily_reward()
                    if isinstance(msg, bool) and msg:
                        logger.info(f"Thread {self.thread} | Claimed daily reward!")

                    await self.play_game()
                    await asyncio.sleep()

                    start_time, end_time,play_passes = await self.balance()
                    if start_time is None and end_time is None:
                        await self.start()
                        logger.info(f"Thread {self.thread} | Start farming!")

                    elif start_time is not None and end_time is not None and currentTimestamp >= end_time:
                        balance = await self.claim()
                        logger.success(f"Thread {self.thread} | Claimed reward! Balance: {balance}")
                    else:
                        logger.info(f"Thread {self.thread} | Next claim in {end_time-currentTimestamp} seconds!")
                        if(end_time-currentTimestamp <= tokenExp):
                            logger.info(f"Thread {self.thread} | Sleep {end_time-currentTimestamp} seconds!")
                            await asyncio.sleep(end_time-currentTimestamp)
                        else:
                            logger.info(f"Thread {self.thread} | Refresh token in {tokenExp} seconds!")
                            await asyncio.sleep(tokenExp)
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Thread {self.thread} | Error: {e}")

    async def play_game(self):
        start_time, end_time, play_passes = await self.balance()
        while (int(play_passes)>0):
            logger.info(f"Thread {self.thread} | Play remaining: {play_passes}")
            game_id = await self.start_game()
            if not game_id:
                logger.error(f"Thread {self.thread} | Couldn't start play in game!")
                continue

            logger.info(f"Thread {self.thread} | Start play in game! GameId: {game_id}")

            msg, points = await self.claim_game(game_id)
            if isinstance(msg, bool) and msg:
                logger.success(f"Thread {self.thread} | Finish play in game! Reward: {points}")
            else:
                logger.error(f"Thread {self.thread} | Couldn't play game; msg: {msg}")

            await asyncio.sleep(random.uniform(5, 10))
            start_time, end_time, play_passes = await self.balance()

    async def claim_daily_reward(self):
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/daily-reward?offset=-180", proxy=self.proxy)
        txt = await resp.text()
        await asyncio.sleep(1)
        return True if txt == 'OK' else txt

    async def start_game(self):
        await asyncio.sleep(random.uniform(5, 10))
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/game/play", proxy=self.proxy)
        resp_json = await resp.json()

        return (resp_json).get("gameId")

    async def claim_game(self, game_id: str):
        await asyncio.sleep(random.uniform(60, 65))
        points = random.randint(config.POINT[0], config.POINT[1])
        json_data = {"gameId": game_id, "points": points}
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data, proxy=self.proxy)
        txt = await resp.text()

        return True if txt == 'OK' else txt, points

    async def claim(self):
        resp = await self.session.post("https://game-domain.blum.codes/api/v1/farming/claim", proxy=self.proxy)
        resp_json = await self.parse_json_response(resp)
        return resp_json.get("availableBalance")

    async def start(self):
        await self.session.post("https://game-domain.blum.codes/api/v1/farming/start", proxy=self.proxy)

    async def balance(self):
        resp = await self.session.get("https://game-domain.blum.codes/api/v1/user/balance", proxy=self.proxy)
        resp_json = await self.parse_json_response(resp)
        if resp_json.get("farming"):
            start_time = resp_json.get("farming").get("startTime")
            end_time = resp_json.get("farming").get("endTime")
            finalEndTime = finalStartTime = None
            if start_time is not None:
                finalStartTime = float(start_time/1000)
            if end_time is not None:
                finalEndTime = float(end_time/1000)

            return finalStartTime, finalEndTime, resp_json.get("playPasses")
        return None, None, resp_json.get("playPasses")

    async def login(self):
        json_data = {"query": await self.get_tg_web_data()}

        resp = await self.session.post("https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP", json=json_data, proxy=self.proxy)
        token_data = await self.parse_json_response(resp)
        self.session.headers['Authorization'] = "Bearer " + token_data.get("token").get("access")

        # Calculate token expiry time (assuming token lifetime is known)
        self.token_expiry = time.time() + token_data.get("token").get("expires_in", 3600) - 60  # 60 seconds before actual expiry

    async def relogin(self):
        await self.login()

    async def get_tg_web_data(self):
        await self.client.connect()

        try:
            async for msg in self.client.get_chat_history(-1002136959923, limit=1):
                msg_id = msg.id
            await self.client.invoke(GetMessagesViews(
                peer=await self.client.resolve_peer(-1002136959923),
                id=list(range(msg_id-random.randint(50, 100), msg_id + 1)),
                increment=True
            ))

        except: pass

        web_view = await self.client.invoke(RequestWebView(
            peer=await self.client.resolve_peer('BlumCryptoBot'),
            bot=await self.client.resolve_peer('BlumCryptoBot'),
            platform='android',
            from_bot_menu=False,
            url='https://telegram.blum.codes/'
        ))

        auth_url = web_view.url
        await self.client.disconnect()
        return unquote(string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))

    async def parse_json_response(self, response):
        if response.headers.get('Content-Type') == 'application/json':
            return await response.json()
        else:
            logger.error(f"Unexpected content type: {response.headers.get('Content-Type')}. Response: {await response.text()}")
            response.raise_for_status()
