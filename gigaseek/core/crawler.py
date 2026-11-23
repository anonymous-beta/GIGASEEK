"""
GIGASEEK Super Crawler
The demon that walks the web — aggressive, smart, relentless
"""

import asyncio
import re
import time
import random
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
import orjson

from ..utils.http import StealthSession, Response
from ..utils.parser import DataExtractor, ContentAnalyzer
from ..config import Config


@dataclass
class CrawlResult:
    """Result from crawling a URL"""
    url: str
    status: int
    depth: int
    links_found: List[str] = field(default_factory=list)
    data_extracted: Optional[dict] = None
    error: Optional[str] = None
    response_time: float = 0.0
    content_type: str = ""
    size: int = 0


@dataclass
class CrawlTarget:
    """Target for crawling"""
    url: str
    depth: int = 0
    max_depth: int = 3
    allowed_domains: Optional[Set[str]] = None
    keywords: List[str] = field(default_factory=list)
    extract_data: bool = True


class URLFrontier:
    """
    Intelligent URL frontier with prioritization
    """
    
    def __init__(self, max_size: int = 100000):
        self.high_priority: deque = deque()
        self.normal_priority: deque = deque()
        self.low_priority: deque = deque()
        self.visited: Set[str] = set()
        self.max_size = max_size
        self.url_patterns = {
            'high': re.compile(r'(profile|user|account|about|contact|info|bio|member|people|author)', re.I),
            'low': re.compile(r'(login|signup|register|cart|checkout|search|tag|category|archive|page/\d+|feed|rss|atom)', re.I),
        }
    
    def add(self, url: str, priority: str = "normal", depth: int = 0):
        """Add URL to frontier with priority"""
        if url in self.visited:
            return
        
        if len(self.visited) >= self.max_size:
            return
        
        # Clean URL
        url, _ = urldefrag(url)
        
        # Determine priority based on URL pattern
        if priority == "auto":
            if self.url_patterns['high'].search(url):
                priority = "high"
            elif self.url_patterns['low'].search(url):
                priority = "low"
            else:
                priority = "normal"
        
        item = (url, depth)
        
        if priority == "high":
            self.high_priority.append(item)
        elif priority == "low":
            self.low_priority.append(item)
        else:
            self.normal_priority.append(item)
    
    def get(self) -> Optional[Tuple[str, int]]:
        """Get next URL from frontier"""
        if self.high_priority:
            url, depth = self.high_priority.popleft()
        elif self.normal_priority:
            url, depth = self.normal_priority.popleft()
        elif self.low_priority:
            url, depth = self.low_priority.popleft()
        else:
            return None
        
        if url in self.visited:
            return self.get()  # Recursively get next
        
        self.visited.add(url)
        return url, depth
    
    def is_empty(self) -> bool:
        return not (self.high_priority or self.normal_priority or self.low_priority)
    
    def size(self) -> int:
        return len(self.high_priority) + len(self.normal_priority) + len(self.low_priority)
    
    def visited_count(self) -> int:
        return len(self.visited)


class SuperCrawler:
    """
    The GIGASEEK Super Crawler
    Aggressive, intelligent web crawling with data extraction
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.session: Optional[StealthSession] = None
        self.extractor = DataExtractor()
        self.analyzer = ContentAnalyzer()
        self.frontier = URLFrontier()
        self.results: List[CrawlResult] = []
        self.callbacks: List[Callable] = []
        self.running = False
        self.stats = {
            "urls_crawled": 0,
            "urls_failed": 0,
            "data_found": 0,
            "start_time": None,
            "end_time": None,
        }
        
        # Content filters
        self.allowed_content_types = [
            "text/html", "application/json", "text/plain", "text/xml"
        ]
        
        # Link extraction pattern
        self.link_pattern = re.compile(
            r'href=["\'](.*?)["\']',
            re.I | re.S
        )
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """Initialize crawler"""
        self.session = StealthSession(self.config)
        await self.session.start()
        self.running = True
    
    async def close(self):
        """Cleanup"""
        if self.session:
            await self.session.close()
        self.running = False
    
    def add_callback(self, callback: Callable[[CrawlResult], None]):
        """Add callback for crawl results"""
        self.callbacks.append(callback)
    
    async def crawl(
        self,
        seed_urls: List[str],
        max_depth: int = 3,
        max_pages: int = 1000,
        allowed_domains: Optional[Set[str]] = None,
        keywords: Optional[List[str]] = None,
        extract_data: bool = True,
    ) -> List[CrawlResult]:
        """
        Main crawling method
        """
        self.stats["start_time"] = time.time()
        self.results = []
        
        # Add seed URLs
        for url in seed_urls:
            self.frontier.add(url, priority="high", depth=0)
        
        # Crawl loop
        pages_crawled = 0
        batch_size = min(50, self.config.crawler.max_concurrent_requests)
        
        while not self.frontier.is_empty() and pages_crawled < max_pages and self.running:
            # Get batch of URLs
            batch = []
            for _ in range(batch_size):
                item = self.frontier.get()
                if item is None:
                    break
                url, depth = item
                batch.append(CrawlTarget(
                    url=url,
                    depth=depth,
                    max_depth=max_depth,
                    allowed_domains=allowed_domains,
                    keywords=keywords or [],
                    extract_data=extract_data,
                ))
            
            if not batch:
                break
            
            # Crawl batch concurrently
            tasks = [self._crawl_url(target) for target in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, CrawlResult):
                    self.results.append(result)
                    pages_crawled += 1
                    self.stats["urls_crawled"] += 1
                    
                    # Trigger callbacks
                    for callback in self.callbacks:
                        try:
                            callback(result)
                        except Exception:
                            pass
                    
                    # Add found links to frontier
                    if result.links_found and result.depth < max_depth:
                        for link in result.links_found[:20]:  # Limit links per page
                            # Check domain restrictions
                            if allowed_domains:
                                link_domain = urlparse(link).netloc
                                if not any(d in link_domain for d in allowed_domains):
                                    continue
                            
                            priority = "auto"
                            if keywords and any(kw.lower() in link.lower() for kw in keywords):
                                priority = "high"
                            
                            self.frontier.add(link, priority=priority, depth=result.depth + 1)
                
                elif isinstance(result, Exception):
                    self.stats["urls_failed"] += 1
        
        self.stats["end_time"] = time.time()
        return self.results
    
    async def _crawl_url(self, target: CrawlTarget) -> CrawlResult:
        """Crawl a single URL"""
        result = CrawlResult(
            url=target.url,
            status=0,
            depth=target.depth,
        )
        
        try:
            # Fetch page
            response = await self.session.get(
                target.url,
                allow_redirects=True,
            )
            
            result.status = response.status
            result.response_time = response.elapsed
            result.size = len(response.body)
            result.content_type = response.headers.get("Content-Type", "")
            
            # Check content type
            if not any(ct in result.content_type for ct in self.allowed_content_types):
                return result
            
            # Extract links
            result.links_found = self._extract_links(response.text, target.url)
            
            # Extract data
            if target.extract_data:
                analysis = self.analyzer.analyze_response(response.text, target.url)
                result.data_extracted = {
                    "emails": list(analysis["extracted"].emails),
                    "phones": list(analysis["extracted"].phones),
                    "usernames": list(analysis["extracted"].usernames),
                    "social_links": analysis["extracted"].social_links,
                    "addresses": list(analysis["extracted"].addresses),
                    "osint_score": analysis["osint_score"],
                }
                
                if analysis["osint_score"] > 0:
                    self.stats["data_found"] += 1
            
            return result
            
        except Exception as e:
            result.error = str(e)
            return result
    
    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract links from HTML"""
        links = []
        base_domain = urlparse(base_url).netloc
        
        for match in self.link_pattern.findall(html):
            # Skip certain links
            if match.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                continue
            
            # Make absolute
            absolute_url = urljoin(base_url, match)
            
            # Remove fragment
            absolute_url, _ = urldefrag(absolute_url)
            
            # Only follow http/https
            if not absolute_url.startswith(('http://', 'https://')):
                continue
            
            # Same domain or subdomain
            link_domain = urlparse(absolute_url).netloc
            if base_domain in link_domain or link_domain in base_domain:
                links.append(absolute_url)
        
        # Deduplicate while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        return unique_links[:50]  # Limit per page
    
    async def bulk_probe(
        self,
        urls: List[str],
        method: str = "GET",
        max_concurrent: int = 200,
    ) -> List[Tuple[str, int, float]]:
        """
        Quickly probe multiple URLs to check status
        Returns list of (url, status, response_time)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def probe(url: str) -> Tuple[str, int, float]:
            async with semaphore:
                try:
                    if method == "HEAD":
                        response = await self.session.head(url, timeout=10)
                    else:
                        response = await self.session.get(url, timeout=10)
                    return url, response.status, response.elapsed
                except:
                    return url, 0, 0.0
        
        tasks = [probe(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return list(results)
    
    def get_stats(self) -> dict:
        """Get crawler statistics"""
        stats = self.stats.copy()
        if stats["start_time"] and stats["end_time"]:
            stats["duration"] = stats["end_time"] - stats["start_time"]
            stats["urls_per_second"] = stats["urls_crawled"] / stats["duration"] if stats["duration"] > 0 else 0
        stats["frontier_size"] = self.frontier.size()
        stats["visited_count"] = self.frontier.visited_count()
        return stats
