# [context: linux x86_64 | asyncio + aiohttp | Discord API v9]
# Jimothy Rocks Discord Username Sniper — Random 4C Mode

import asyncio
import aiohttp
import json
import time
import random
import os
import sys
import string
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

@dataclass
class Config:
    tokens: List[str] = field(default_factory=list)
    passwords: Dict[str, str] = field(default_factory=dict)
    proxies: List[str] = field(default_factory=list)
    check_interval: float = 0.4
    claim_timeout: float = 8.0
    max_concurrent_checks: int = 15
    webhook_url: Optional[str] = None
    charset: str = "abcdefghijklmnopqrstuvwxyz0123456789_."
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    super_properties: str = "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEzMS4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTMxLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjM1NDE2NCwiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbH0="

    def load(self, path: str = "config.json"):
        if not os.path.exists(path):
            print(f"[!] {path} not found")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.tokens = [t.strip() for t in data.get("tokens", []) if t.strip()]
        self.passwords = data.get("passwords", {})
        self.proxies = [p.strip() for p in data.get("proxies", []) if p.strip()]
        self.check_interval = float(data.get("check_interval", 0.4))
        self.webhook_url = data.get("webhook_url")
        self.max_concurrent_checks = int(data.get("max_concurrent_checks", 15))
        self.charset = data.get("charset", self.charset)
        if not self.tokens:
            print("[!] no tokens")
            sys.exit(1)

class Logger:
    COLORS = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m",
        "SNIPE": "\033[95m",
        "RESET": "\033[0m"
    }

    @staticmethod
    def log(level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color = Logger.COLORS.get(level, "")
        reset = Logger.COLORS["RESET"]
        print(f"{color}[{ts}] [{level}] {msg}{reset}")

class ProxyRotator:
    def __init__(self, proxies: List[str]):
        self.proxies = proxies
        self.index = 0
        self.lock = asyncio.Lock()

    async def next(self) -> Optional[str]:
        if not self.proxies:
            return None
        async with self.lock:
            proxy = self.proxies[self.index % len(self.proxies)]
            self.index += 1
            return proxy

class UsernameChecker:
    CHECK_URL = "https://discord.com/api/v9/unique-username/username-attempt-unauthed"

    def __init__(self, config: Config, proxy_rotator: ProxyRotator):
        self.config = config
        self.proxy_rotator = proxy_rotator
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(config.max_concurrent_checks)

    async def start(self):
        timeout = aiohttp.ClientTimeout(total=12)
        connector = aiohttp.TCPConnector(limit=60, ttl_dns_cache=300, ssl=False)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

    async def close(self):
        if self.session:
            await self.session.close()

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "User-Agent": self.config.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/register",
            "X-Super-Properties": self.config.super_properties,
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }

    async def is_available(self, username: str) -> Optional[bool]:
        async with self.semaphore:
            proxy = await self.proxy_rotator.next()
            payload = {"username": username}
            try:
                async with self.session.post(
                    self.CHECK_URL,
                    json=payload,
                    headers=self._headers(),
                    proxy=proxy
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        taken = data.get("taken", True)
                        return not taken
                    elif resp.status == 429:
                        retry = float(resp.headers.get("Retry-After", 2))
                        Logger.log("WARN", f"rate limited — sleep {retry}s")
                        await asyncio.sleep(retry + 0.2)
                        return None
                    else:
                        return None
            except Exception as e:
                return None

class UsernameClaimer:
    CLAIM_URL = "https://discord.com/api/v9/users/@me"

    def __init__(self, config: Config, proxy_rotator: ProxyRotator):
        self.config = config
        self.proxy_rotator = proxy_rotator
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        timeout = aiohttp.ClientTimeout(total=self.config.claim_timeout)
        connector = aiohttp.TCPConnector(limit=20, ssl=False)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

    async def close(self):
        if self.session:
            await self.session.close()

    def _headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": self.config.user_agent,
            "X-Super-Properties": self.config.super_properties,
            "X-Discord-Locale": "en-US",
            "X-Discord-Timezone": "America/New_York",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/channels/@me",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }

    async def claim(self, username: str, token: str) -> bool:
        password = self.config.passwords.get(token)
        if not password:
            Logger.log("ERROR", f"no password for token {token[:18]}...")
            return False

        proxy = await self.proxy_rotator.next()
        payload = {"username": username, "password": password}

        try:
            async with self.session.patch(
                self.CLAIM_URL,
                json=payload,
                headers=self._headers(token),
                proxy=proxy
            ) as resp:
                if resp.status == 200:
                    Logger.log("SNIPE", f"🔥 CLAIMED @{username}")
                    await self._webhook(f"**SNIPED 4C** `@{username}`")
                    return True
                elif resp.status == 429:
                    retry = float(resp.headers.get("Retry-After", 3))
                    await asyncio.sleep(retry)
                    return False
                else:
                    return False
        except Exception:
            return False

    async def _webhook(self, content: str):
        if not self.config.webhook_url:
            return
        try:
            async with self.session.post(self.config.webhook_url, json={"content": content}) as _:
                pass
        except:
            pass

class Sniper:
    def __init__(self, config: Config):
        self.config = config
        self.proxy_rotator = ProxyRotator(config.proxies)
        self.checker = UsernameChecker(config, self.proxy_rotator)
        self.claimer = UsernameClaimer(config, self.proxy_rotator)
        self.running = True
        self.stats = {"checked": 0, "available": 0, "claimed": 0}

    def generate_4c(self) -> str:
        # Discord rules: no consecutive dots, can't start/end with .
        while True:
            name = "".join(random.choices(self.config.charset, k=4))
            if ".." not in name and not name.startswith(".") and not name.endswith("."):
                return name

    async def start(self):
        await self.checker.start()
        await self.claimer.start()
        Logger.log("INFO", f"loaded {len(self.config.tokens)} tokens | proxies={len(self.config.proxies)}")
        Logger.log("SUCCESS", "RANDOM 4C SNIPER LIVE — hunting")

        workers = [asyncio.create_task(self._worker(i)) for i in range(self.config.max_concurrent_checks)]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            pass
        finally:
            await self.checker.close()
            await self.claimer.close()

    async def _worker(self, worker_id: int):
        while self.running:
            username = self.generate_4c()
            available = await self.checker.is_available(username)
            self.stats["checked"] += 1

            if available is True:
                self.stats["available"] += 1
                Logger.log("SUCCESS", f"AVAILABLE → @{username} — claiming")
                success = await self._fire_claims(username)
                if success:
                    self.stats["claimed"] += 1
                    Logger.log("SNIPE", f"LOCKED @{username}")
                    # keep hunting more after a claim

            if self.stats["checked"] % 50 == 0:
                Logger.log("INFO", f"stats | checked={self.stats['checked']} avail={self.stats['available']} claimed={self.stats['claimed']}")

            await asyncio.sleep(self.config.check_interval + random.uniform(0.02, 0.12))

    async def _fire_claims(self, username: str) -> bool:
        tasks = [self.claimer.claim(username, token) for token in self.config.tokens]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return any(r is True for r in results)

async def main():
    config = Config()
    config.load("config.json")
    sniper = Sniper(config)
    try:
        await sniper.start()
    except KeyboardInterrupt:
        Logger.log("WARN", "killed")
        sniper.running = False

if __name__ == "__main__":
    asyncio.run(main())
