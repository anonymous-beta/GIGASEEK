"""
GIGASEEK Engine
The central orchestrator that coordinates all modules
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from .crawler import SuperCrawler, CrawlResult
from .resolver import AsyncResolver
from .extractor import ExtractionEngine
from .database import DatabaseManager, Target, Finding, Scan
from ..utils.logger import DemonLogger


@dataclass
class ScanResult:
    """Result from a scan"""
    module: str
    target: str
    findings_count: int
    duration: float
    findings: List[Finding] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ScanProgress:
    """Scan progress information"""
    total_modules: int
    completed_modules: int
    current_module: str
    status: str = "running"
    findings_so_far: int = 0


class GigaseekEngine:
    """
    The GIGASEEK Engine — central orchestrator
    Coordinates all OSINT modules and data flow
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = DemonLogger("gigaseek.engine")
        self.db: Optional[DatabaseManager] = None
        self.crawler: Optional[SuperCrawler] = None
        self.resolver: Optional[AsyncResolver] = None
        self.extractor = ExtractionEngine()
        
        # Module registry
        self.modules: Dict[str, Any] = {}
        self.module_instances: Dict[str, Any] = {}
        
        # Progress tracking
        self.progress_callbacks: List[Callable[[ScanProgress], None]] = []
        self.current_progress: Optional[ScanProgress] = None
        
        # Results
        self.results: List[ScanResult] = []
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """Initialize the engine"""
        self.logger.info("Initializing GIGASEEK Engine...")
        
        # Initialize database
        self.db = DatabaseManager(self.config.database.path)
        await self.db.connect()
        self.logger.success("Database connected")
        
        # Initialize crawler
        self.crawler = SuperCrawler(self.config)
        await self.crawler.start()
        self.logger.success("Super Crawler initialized")
        
        # Initialize resolver
        self.resolver = AsyncResolver()
        await self.resolver.start()
        self.logger.success("Async Resolver initialized")
        
        # Load modules
        await self._load_modules()
        
        self.logger.success("GIGASEEK Engine ready")
    
    async def close(self):
        """Cleanup"""
        if self.crawler:
            await self.crawler.close()
        if self.resolver:
            await self.resolver.close()
        if self.db:
            await self.db.close()
        self.logger.info("Engine shutdown complete")
    
    async def _load_modules(self):
        """Dynamically load OSINT modules"""
        from ..modules.username import UsernameModule
        from ..modules.email import EmailModule
        from ..modules.phone import PhoneModule
        from ..modules.domain import DomainModule
        from ..modules.social import SocialModule
        from ..modules.breach import BreachModule
        
        module_classes = {
            "username": UsernameModule,
            "email": EmailModule,
            "phone": PhoneModule,
            "domain": DomainModule,
            "social": SocialModule,
            "breach": BreachModule,
        }
        
        for name, cls in module_classes.items():
            if name in self.config.modules.disabled_modules:
                continue
            
            try:
                instance = cls(self)
                self.module_instances[name] = instance
                self.modules[name] = cls
                self.logger.debug(f"Loaded module: {name}")
            except Exception as e:
                self.logger.error(f"Failed to load module {name}: {e}")
        
        self.logger.success(f"Loaded {len(self.module_instances)} modules")
    
    def register_progress_callback(self, callback: Callable[[ScanProgress], None]):
        """Register callback for scan progress updates"""
        self.progress_callbacks.append(callback)
    
    def _update_progress(self, progress: ScanProgress):
        """Update progress and notify callbacks"""
        self.current_progress = progress
        for callback in self.progress_callbacks:
            try:
                callback(progress)
            except Exception:
                pass
    
    async def scan(
        self,
        target_type: str,
        target_value: str,
        modules: Optional[List[str]] = None,
        deep: bool = False,
    ) -> List[ScanResult]:
        """
        Main scan method — run OSINT modules against a target
        """
        self.logger.info(f"Starting scan: {target_type} = {target_value}")
        
        # Create target in database
        target = Target(type=target_type, value=target_value)
        target_id = await self.db.insert_target(target)
        
        # Determine which modules to run
        if modules:
            modules_to_run = [m for m in modules if m in self.module_instances]
        else:
            # Auto-select based on target type
            modules_to_run = self._select_modules(target_type)
        
        if not modules_to_run:
            self.logger.warning("No modules available for target type")
            return []
        
        # Initialize progress
        progress = ScanProgress(
            total_modules=len(modules_to_run),
            completed_modules=0,
            current_module="",
        )
        
        self.results = []
        
        # Run modules
        for module_name in modules_to_run:
            module = self.module_instances[module_name]
            
            progress.current_module = module_name
            self._update_progress(progress)
            
            self.logger.info(f"Running module: {module_name}")
            
            # Start scan record
            scan = Scan(target_id=target_id, module=module_name)
            scan_id = await self.db.start_scan(scan)
            
            start_time = time.time()
            
            try:
                # Run the module
                findings = await module.scan(target_value, deep=deep)
                
                # Store findings
                for finding in findings:
                    finding.target_id = target_id
                
                if findings:
                    await self.db.insert_findings_bulk(findings)
                
                duration = time.time() - start_time
                
                # Complete scan
                await self.db.complete_scan(scan_id, len(findings))
                
                result = ScanResult(
                    module=module_name,
                    target=target_value,
                    findings_count=len(findings),
                    duration=duration,
                    findings=findings,
                )
                
                self.results.append(result)
                progress.findings_so_far += len(findings)
                
                self.logger.success(
                    f"Module {module_name} complete: {len(findings)} findings in {duration:.2f}s"
                )
                
            except Exception as e:
                duration = time.time() - start_time
                await self.db.complete_scan(scan_id, 0, str(e))
                
                result = ScanResult(
                    module=module_name,
                    target=target_value,
                    findings_count=0,
                    duration=duration,
                    error=str(e),
                )
                
                self.results.append(result)
                self.logger.error(f"Module {module_name} failed: {e}")
            
            progress.completed_modules += 1
            self._update_progress(progress)
        
        progress.status = "completed"
        self._update_progress(progress)
        
        self.logger.success(f"Scan complete: {progress.findings_so_far} total findings")
        
        return self.results
    
    def _select_modules(self, target_type: str) -> List[str]:
        """Auto-select modules based on target type"""
        mapping = {
            "username": ["username", "social", "breach"],
            "email": ["email", "breach", "social"],
            "phone": ["phone", "breach"],
            "domain": ["domain", "breach"],
            "name": ["social", "breach"],
            "ip": ["domain"],
        }
        
        return mapping.get(target_type, list(self.module_instances.keys()))
    
    async def get_target_report(self, target_id: int) -> Dict[str, Any]:
        """Generate comprehensive report for a target"""
        findings = await self.db.get_target_findings(target_id)
        
        # Group by type
        by_type = {}
        for finding in findings:
            if finding.data_type not in by_type:
                by_type[finding.data_type] = []
            by_type[finding.data_type].append({
                "value": finding.data_value,
                "source": finding.source,
                "url": finding.url,
                "confidence": finding.confidence,
            })
        
        return {
            "target_id": target_id,
            "total_findings": len(findings),
            "findings_by_type": by_type,
            "generated_at": datetime.now().isoformat(),
        }
    
    async def get_statistics(self) -> dict:
        """Get engine statistics"""
        db_stats = await self.db.get_statistics()
        
        crawler_stats = self.crawler.get_stats() if self.crawler else {}
        resolver_stats = self.resolver.get_stats() if self.resolver else {}
        
        return {
            "database": db_stats,
            "crawler": crawler_stats,
            "resolver": resolver_stats,
            "modules_loaded": list(self.module_instances.keys()),
        }
