"""
Advanced HTTP utilities for GIGASEEK
Stealth session management with rotation and evasion
"""

import asyncio
import random
import aiohttp
import aiohttp_socks
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from fake_useragent import UserAgent
import orjson
from ..config import Config


@dataclass
class Response:
    """Custom response object"""
    url: str
    status: int
    headers: Dict[str, str]
    body: bytes
    text: str
    elapsed: float
    redirected: bool
    final_url: str
    
    @property
    def json(self) -> Optional[dict]:
        """Parse JSON response"""
        try:
            return orjson.loads(self.body)
        except:
            return None
    
    @property
    def size(self) -> int:
        """Response size in bytes"""
        return len(self.body)


class RequestRotator:
    """Rotates requests through different configurations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.ua = UserAgent()
        self.request_count = 0
        self.current_proxy_index = 0
        
        # Header pools
        self.accept_encodings = [
            "gzip, deflate, br",
            "gzip, deflate",
            "gzip",
            "*",
        ]
        
        self.accept_languages = config.stealth.accept_language_pool
        
        self.accepts = [
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "*/*",
        ]
    
    def get_headers(self) -> Dict[str, str]:
        """Generate randomized headers"""
        headers = {
            "User-Agent": self.ua.random if self.config.crawler.user_agent_rotation else self.ua.chrome,
            "Accept": random.choice(self.accepts),
            "Accept-Language": random.choice(self.accept_languages),
            "Accept-Encoding": random.choice(self.accept_encodings),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": random.choice(["max-age=0", "no-cache", "no-store"]),
        }
        
        # Randomly add extra headers
        if random.random() > 0.5:
            headers["DNT"] = str(random.choice([0, 1]))
        
        if random.random() > 0.7:
            headers["Referer"] = random.choice([
                "https://www.google.com/",
                "https://www.bing.com/",
                "https://duckduckgo.com/",
                "https://www.reddit.com/",
            ])
        
        return headers
    
    def get_proxy(self) -> Optional[str]:
        """Get next proxy from rotation"""
        if not self.config.proxy.enabled:
            return None
        
        all_proxies = (
            self.config.proxy.http +
            self.config.proxy.https +
            self.config.proxy.socks4 +
            self.config.proxy.socks5
        )
        
        if not all_proxies:
            return None
        
        proxy = all_proxies[self.current_proxy_index % len(all_proxies)]
        self.current_proxy_index += 1
        return proxy


class StealthSession:
    """
    Advanced async HTTP session with stealth capabilities
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.rotator = RequestRotator(config)
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def start(self):
        """Initialize the session"""
        self.semaphore = asyncio.Semaphore(self.config.crawler.max_concurrent_requests)
        
        # Setup connector with DNS rotation
        self._connector = aiohttp.TCPConnector(
            limit=self.config.crawler.max_concurrent_requests,
            limit_per_host=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
            enable_cleanup_closed=True,
            verify_ssl=self.config.crawler.verify_ssl,
        )
        
        # Create session
        timeout = aiohttp.ClientTimeout(total=self.config.crawler.timeout)
        
        self.session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            cookie_jar=aiohttp.CookieJar() if self.config.crawler.cookie_jar else None,
            trust_env=True,
        )
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
        if self._connector:
            await self._connector.close()
    
    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        json_data: Optional[dict] = None,
        params: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
        proxy: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Response:
        """
        Make HTTP request with stealth features
        """
        if not self.session:
            raise RuntimeError("Session not started. Use 'async with' or call start()")
        
        async with self.semaphore:
            # Apply stealth delays
            if self.config.stealth.enabled and self.config.stealth.random_delays:
                delay = random.uniform(
                    self.config.stealth.min_delay,
                    self.config.stealth.max_delay
                )
                await asyncio.sleep(delay)
            
            # Prepare headers
            req_headers = self.rotator.get_headers() if self.config.crawler.header_rotation else {}
            if headers:
                req_headers.update(headers)
            
            # Get proxy
            if not proxy and self.config.proxy.enabled:
                proxy = self.rotator.get_proxy()
            
            # Prepare request
            request_kwargs = {
                "headers": req_headers,
                "allow_redirects": allow_redirects and self.config.crawler.follow_redirects,
                "proxy": proxy,
            }
            
            if data:
                request_kwargs["data"] = data
            if json_data:
                request_kwargs["json"] = json_data
            if params:
                request_kwargs["params"] = params
            if timeout:
                request_kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)
            
            # Execute with retries
            last_exception = None
            for attempt in range(self.config.crawler.max_retries):
                try:
                    start_time = asyncio.get_event_loop().time()
                    
                    async with self.session.request(method, url, **request_kwargs) as resp:
                        body = await resp.read()
                        elapsed = asyncio.get_event_loop().time() - start_time
                        
                        # Check content length limit
                        if len(body) > self.config.crawler.max_content_length:
                            body = body[:self.config.crawler.max_content_length]
                        
                        return Response(
                            url=url,
                            status=resp.status,
                            headers=dict(resp.headers),
                            body=body,
                            text=body.decode('utf-8', errors='replace'),
                            elapsed=elapsed,
                            redirected=resp.history != [],
                            final_url=str(resp.url),
                        )
                
                except asyncio.TimeoutError:
                    last_exception = asyncio.TimeoutError(f"Timeout after {timeout or self.config.crawler.timeout}s")
                except aiohttp.ClientError as e:
                    last_exception = e
                except Exception as e:
                    last_exception = e
                
                # Exponential backoff
                if attempt < self.config.crawler.max_retries - 1:
                    backoff = self.config.crawler.retry_backoff ** attempt
                    await asyncio.sleep(backoff)
            
            # All retries failed
            raise last_exception or Exception("Request failed after all retries")
    
    async def get(self, url: str, **kwargs) -> Response:
        """GET request"""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Response:
        """POST request"""
        return await self.request("POST", url, **kwargs)
    
    async def head(self, url: str, **kwargs) -> Response:
        """HEAD request"""
        return await self.request("HEAD", url, **kwargs)
    
    async def bulk_request(
        self,
        requests: List[Dict[str, Any]],
        max_concurrent: Optional[int] = None,
    ) -> List[Union[Response, Exception]]:
        """
        Execute multiple requests concurrently
        Each request dict should have: method, url, and optional kwargs
        """
        if max_concurrent:
            semaphore = asyncio.Semaphore(max_concurrent)
        else:
            semaphore = self.semaphore
        
        async def bounded_request(req):
            async with semaphore:
                try:
                    return await self.request(
                        req.get("method", "GET"),
                        req["url"],
                        **{k: v for k, v in req.items() if k not in ["method", "url"]}
                    )
                except Exception as e:
                    return e
        
        tasks = [bounded_request(req) for req in requests]
        return await asyncio.gather(*tasks)
