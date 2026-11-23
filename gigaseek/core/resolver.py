"""
GIGASEEK Async Resolver
High-performance DNS resolution with caching and rotation
"""

import asyncio
import aiodns
import socket
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import time
import ipaddress


@dataclass
class DNSResult:
    """DNS resolution result"""
    domain: str
    record_type: str
    values: List[str]
    timestamp: float = field(default_factory=time.time)
    ttl: int = 300
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


@dataclass
class DomainInfo:
    """Comprehensive domain information"""
    domain: str
    ips: Set[str] = field(default_factory=set)
    mx_records: List[str] = field(default_factory=list)
    ns_records: List[str] = field(default_factory=list)
    txt_records: List[str] = field(default_factory=list)
    cname_records: List[str] = field(default_factory=list)
    soa_record: Optional[str] = None
    subdomains: Set[str] = field(default_factory=set)
    reverse_dns: Dict[str, str] = field(default_factory=dict)
    asn_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "ips": list(self.ips),
            "mx_records": self.mx_records,
            "ns_records": self.ns_records,
            "txt_records": self.txt_records,
            "cname_records": self.cname_records,
            "soa_record": self.soa_record,
            "subdomains": list(self.subdomains),
            "reverse_dns": self.reverse_dns,
            "asn_info": self.asn_info,
        }


class AsyncResolver:
    """
    High-performance asynchronous DNS resolver
    with caching, bulk operations, and multiple record types
    """
    
    def __init__(self, cache_size: int = 10000, cache_ttl: int = 300):
        self.resolver: Optional[aiodns.DNSResolver] = None
        self.cache: Dict[str, DNSResult] = {}
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.query_count = 0
        self.cache_hits = 0
        
        # Common DNS servers for rotation
        self.dns_servers = [
            "8.8.8.8", "8.8.4.4",  # Google
            "1.1.1.1", "1.0.0.1",  # Cloudflare
            "9.9.9.9", "149.112.112.112",  # Quad9
            "208.67.222.222", "208.67.220.220",  # OpenDNS
        ]
        self.current_dns_index = 0
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """Initialize the resolver"""
        # Try to use a rotating DNS server
        try:
            dns_server = self.dns_servers[self.current_dns_index]
            self.resolver = aiodns.DNSResolver(
                nameservers=[dns_server],
                timeout=5.0,
                tries=3,
            )
        except:
            # Fallback to system DNS
            self.resolver = aiodns.DNSResolver(
                timeout=5.0,
                tries=3,
            )
    
    async def close(self):
        """Cleanup"""
        self.cache.clear()
    
    def _get_cache_key(self, domain: str, record_type: str) -> str:
        return f"{record_type}:{domain}"
    
    def _get_from_cache(self, domain: str, record_type: str) -> Optional[DNSResult]:
        key = self._get_cache_key(domain, record_type)
        result = self.cache.get(key)
        
        if result and not result.is_expired():
            self.cache_hits += 1
            return result
        
        if result:
            # Expired, remove it
            del self.cache[key]
        
        return None
    
    def _add_to_cache(self, result: DNSResult):
        # Simple cache eviction
        if len(self.cache) >= self.cache_size:
            # Remove oldest entries
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1].timestamp)
            for key, _ in sorted_items[:100]:
                del self.cache[key]
        
        key = self._get_cache_key(result.domain, result.record_type)
        self.cache[key] = result
    
    async def resolve(self, domain: str, record_type: str = "A") -> DNSResult:
        """
        Resolve DNS record with caching
        """
        # Check cache first
        cached = self._get_from_cache(domain, record_type)
        if cached:
            return cached
        
        if not self.resolver:
            await self.start()
        
        self.query_count += 1
        values = []
        
        try:
            if record_type == "A":
                results = await self.resolver.query(domain, "A")
                values = [r.host for r in results]
            elif record_type == "AAAA":
                results = await self.resolver.query(domain, "AAAA")
                values = [r.host for r in results]
            elif record_type == "MX":
                results = await self.resolver.query(domain, "MX")
                values = [f"{r.priority} {r.host}" for r in results]
            elif record_type == "NS":
                results = await self.resolver.query(domain, "NS")
                values = [r.host for r in results]
            elif record_type == "TXT":
                results = await self.resolver.query(domain, "TXT")
                values = [r.text for r in results]
            elif record_type == "CNAME":
                result = await self.resolver.query(domain, "CNAME")
                values = [result.cname]
            elif record_type == "SOA":
                result = await self.resolver.query(domain, "SOA")
                values = [f"{result.nsname} {result.hostmaster}"]
            elif record_type == "PTR":
                result = await self.resolver.query(domain, "PTR")
                values = [result.name]
            else:
                raise ValueError(f"Unsupported record type: {record_type}")
        
        except aiodns.error.DNSError as e:
            # NXDOMAIN, timeout, etc.
            values = []
        except Exception:
            values = []
        
        result = DNSResult(
            domain=domain,
            record_type=record_type,
            values=values,
            ttl=self.cache_ttl,
        )
        
        self._add_to_cache(result)
        return result
    
    async def resolve_bulk(
        self,
        domains: List[str],
        record_types: List[str] = None,
        max_concurrent: int = 100,
    ) -> Dict[str, Dict[str, DNSResult]]:
        """
        Resolve multiple domains concurrently
        """
        if record_types is None:
            record_types = ["A", "MX", "NS", "TXT"]
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def resolve_domain(domain: str) -> Tuple[str, Dict[str, DNSResult]]:
            async with semaphore:
                results = {}
                for rt in record_types:
                    try:
                        results[rt] = await self.resolve(domain, rt)
                    except Exception as e:
                        results[rt] = DNSResult(domain, rt, [], ttl=0)
                return domain, results
        
        tasks = [resolve_domain(d) for d in domains]
        results = await asyncio.gather(*tasks)
        
        return dict(results)
    
    async def get_domain_info(self, domain: str) -> DomainInfo:
        """
        Get comprehensive domain information
        """
        info = DomainInfo(domain=domain)
        
        # Resolve main records
        a_records = await self.resolve(domain, "A")
        info.ips.update(a_records.values)
        
        aaaa_records = await self.resolve(domain, "AAAA")
        info.ips.update(aaaa_records.values)
        
        mx_records = await self.resolve(domain, "MX")
        info.mx_records = mx_records.values
        
        ns_records = await self.resolve(domain, "NS")
        info.ns_records = ns_records.values
        
        txt_records = await self.resolve(domain, "TXT")
        info.txt_records = txt_records.values
        
        cname_records = await self.resolve(domain, "CNAME")
        info.cname_records = cname_records.values
        
        soa_record = await self.resolve(domain, "SOA")
        info.soa_record = soa_record.values[0] if soa_record.values else None
        
        # Reverse DNS for IPs
        for ip in info.ips:
            try:
                if ipaddress.ip_address(ip).version == 4:
                    ptr_domain = ".".join(reversed(ip.split("."))) + ".in-addr.arpa"
                else:
                    ptr_domain = ".".join(reversed(ip.replace(":", ""))) + ".ip6.arpa"
                
                ptr_result = await self.resolve(ptr_domain, "PTR")
                if ptr_result.values:
                    info.reverse_dns[ip] = ptr_result.values[0]
            except:
                pass
        
        return info
    
    async def enumerate_subdomains(
        self,
        domain: str,
        wordlist: List[str] = None,
        max_concurrent: int = 200,
    ) -> Set[str]:
        """
        Enumerate subdomains using wordlist
        """
        if wordlist is None:
            # Built-in common subdomains
            wordlist = [
                "www", "mail", "ftp", "smtp", "pop", "ns1", "ns2", "ns3",
                "webmail", "webdisk", "cpanel", "whm", "autodiscover",
                "autoconfig", "m", "mobile", "api", "app", "apps",
                "dev", "staging", "test", "beta", "alpha", "demo",
                "admin", "dashboard", "panel", "portal", "login",
                "blog", "shop", "store", "forum", "support", "help",
                "cdn", "static", "assets", "media", "images",
                "secure", "ssl", "vpn", "proxy", "gateway",
                "git", "gitlab", "github", "jenkins", "ci", "cd",
                "db", "database", "mysql", "postgres", "redis",
                "cache", "queue", "worker", "cron", "backup",
                "mx", "spf", "dkim", "dmarc", "_dmarc",
                "office", "exchange", "owa", "sharepoint",
                "intranet", "internal", "private", "corp",
                "status", "monitor", "grafana", "kibana",
                "api-v1", "api-v2", "v1", "v2", "graphql",
                "auth", "oauth", "sso", "id", "identity",
                "pay", "payment", "billing", "checkout",
                "game", "games", "play", "media", "stream",
            ]
        
        found_subdomains = set()
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def check_subdomain(sub: str) -> Optional[str]:
            full_domain = f"{sub}.{domain}"
            async with semaphore:
                result = await self.resolve(full_domain, "A")
                if result.values:
                    return full_domain
                return None
        
        tasks = [check_subdomain(sub) for sub in wordlist]
        results = await asyncio.gather(*tasks)
        
        for result in results:
            if result:
                found_subdomains.add(result)
        
        return found_subdomains
    
    async def reverse_ip_lookup(self, ip: str) -> List[str]:
        """
        Find domains hosted on the same IP (basic version)
        """
        # This would ideally use a service like Bing IP search or HackerTarget
        # For now, do PTR lookup
        try:
            if ipaddress.ip_address(ip).version == 4:
                ptr_domain = ".".join(reversed(ip.split("."))) + ".in-addr.arpa"
            else:
                ptr_domain = ".".join(reversed(ip.replace(":", ""))) + ".ip6.arpa"
            
            result = await self.resolve(ptr_domain, "PTR")
            return result.values
        except:
            return []
    
    def get_stats(self) -> dict:
        """Get resolver statistics"""
        cache_hit_rate = (self.cache_hits / self.query_count * 100) if self.query_count > 0 else 0
        return {
            "total_queries": self.query_count,
            "cache_hits": self.cache_hits,
            "cache_size": len(self.cache),
            "cache_hit_rate": f"{cache_hit_rate:.2f}%",
        }
