"""
GIGASEEK Configuration Management
Handles all configuration, settings, and environment variables
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    enabled: bool = False
    http: List[str] = Field(default_factory=list)
    https: List[str] = Field(default_factory=list)
    socks4: List[str] = Field(default_factory=list)
    socks5: List[str] = Field(default_factory=list)
    rotation_interval: int = 10


class RateLimitConfig(BaseModel):
    requests_per_second: int = 50
    burst_size: int = 100
    per_domain_delay: float = 0.1
    global_delay: float = 0.01


class CrawlerConfig(BaseModel):
    max_concurrent_requests: int = 500
    max_redirects: int = 5
    timeout: float = 15.0
    max_retries: int = 3
    retry_backoff: float = 1.5
    user_agent_rotation: bool = True
    header_rotation: bool = True
    cookie_jar: bool = True
    follow_redirects: bool = True
    verify_ssl: bool = False
    max_content_length: int = 10 * 1024 * 1024  # 10MB


class StealthConfig(BaseModel):
    enabled: bool = True
    random_delays: bool = True
    min_delay: float = 0.05
    max_delay: float = 0.5
    mimic_browser: bool = True
    accept_language_pool: List[str] = Field(default_factory=lambda: [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
        "es-ES,es;q=0.9,en;q=0.8",
        "fr-FR,fr;q=0.9,en;q=0.8",
        "de-DE,de;q=0.9,en;q=0.8",
        "it-IT,it;q=0.9,en;q=0.8",
        "pt-BR,pt;q=0.9,en;q=0.8",
        "ru-RU,ru;q=0.9,en;q=0.8",
        "ja-JP,ja;q=0.9,en;q=0.8",
        "zh-CN,zh;q=0.9,en;q=0.8",
    ])


class DatabaseConfig(BaseModel):
    path: str = "gigaseek.db"
    backup_interval: int = 3600
    max_connections: int = 20


class OutputConfig(BaseModel):
    format: str = "json"
    pretty: bool = True
    save_raw_html: bool = False
    save_screenshots: bool = False
    report_directory: str = "reports"


class ModuleConfig(BaseModel):
    enabled_modules: List[str] = Field(default_factory=lambda: [
        "username", "email", "phone", "domain", "social", "breach", "image", "geo"
    ])
    disabled_modules: List[str] = Field(default_factory=list)


class Config(BaseModel):
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    stealth: StealthConfig = Field(default_factory=StealthConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    modules: ModuleConfig = Field(default_factory=ModuleConfig)
    
    class Config:
        arbitrary_types_allowed = True
    
    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load configuration from file or create default"""
        if path and os.path.exists(path):
            with open(path, 'r') as f:
                if path.endswith('.yaml') or path.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            return cls(**data)
        
        # Try default locations
        for default_path in ["gigaseek.yaml", "gigaseek.json", "config.yaml", "config.json"]:
            if os.path.exists(default_path):
                with open(default_path, 'r') as f:
                    if default_path.endswith(('.yaml', '.yml')):
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)
                return cls(**data)
        
        return cls()
    
    def save(self, path: str = "gigaseek.yaml"):
        """Save configuration to file"""
        with open(path, 'w') as f:
            if path.endswith(('.yaml', '.yml')):
                yaml.dump(self.dict(), f, default_flow_style=False)
            else:
                json.dump(self.dict(), f, indent=2)
    
    def get_data_dir(self) -> Path:
        """Get data directory path"""
        data_dir = Path(__file__).parent / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir
    
    def get_site_db_path(self) -> Path:
        """Get site database path"""
        return self.get_data_dir() / "sites.json"
