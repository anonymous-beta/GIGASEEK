"""
GIGASEEK Extraction Engine
Advanced data extraction and correlation
"""

import re
import asyncio
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import orjson

from .database import Finding, Target
from ..utils.parser import DataExtractor, ExtractedData


@dataclass
class CorrelationResult:
    """Result of correlating multiple data points"""
    key: str
    data_type: str
    occurrences: int
    sources: List[str]
    confidence: int
    related_data: Dict[str, Any] = field(default_factory=dict)


class ExtractionEngine:
    """
    Advanced extraction and correlation engine
    """
    
    def __init__(self):
        self.extractor = DataExtractor()
        self.correlations: Dict[str, CorrelationResult] = {}
        self.data_points: Dict[str, Set[str]] = defaultdict(set)  # type -> values
    
    def process_extracted_data(
        self,
        data: ExtractedData,
        source: str,
        target_id: int,
    ) -> List[Finding]:
        """
        Process extracted data into findings
        """
        findings = []
        
        # Process emails
        for email in data.emails:
            findings.append(Finding(
                target_id=target_id,
                source=source,
                url=source,
                data_type="email",
                data_value=email,
                confidence=80,
                raw_data={"context": "extracted_from_page"},
            ))
            self._add_data_point("email", email, source)
        
        # Process phones
        for phone in data.phones:
            findings.append(Finding(
                target_id=target_id,
                source=source,
                url=source,
                data_type="phone",
                data_value=phone,
                confidence=70,
                raw_data={"context": "extracted_from_page"},
            ))
            self._add_data_point("phone", phone, source)
        
        # Process usernames
        for username in data.usernames:
            findings.append(Finding(
                target_id=target_id,
                source=source,
                url=source,
                data_type="username",
                data_value=username,
                confidence=60,
                raw_data={"context": "extracted_from_page"},
            ))
            self._add_data_point("username", username, source)
        
        # Process social links
        for platform, usernames in data.social_links.items():
            for username in usernames:
                findings.append(Finding(
                    target_id=target_id,
                    source=source,
                    url=source,
                    data_type="social",
                    data_value=f"{platform}:{username}",
                    confidence=90,
                    raw_data={"platform": platform, "username": username},
                ))
                self._add_data_point("social", f"{platform}:{username}", source)
        
        # Process addresses
        for address in data.addresses:
            findings.append(Finding(
                target_id=target_id,
                source=source,
                url=source,
                data_type="address",
                data_value=address,
                confidence=50,
                raw_data={"context": "extracted_from_page"},
            ))
            self._add_data_point("address", address, source)
        
        return findings
    
    def _add_data_point(self, data_type: str, value: str, source: str):
        """Add data point for correlation"""
        key = f"{data_type}:{value}"
        
        if key not in self.correlations:
            self.correlations[key] = CorrelationResult(
                key=key,
                data_type=data_type,
                occurrences=0,
                sources=[],
                confidence=0,
            )
        
        corr = self.correlations[key]
        corr.occurrences += 1
        if source not in corr.sources:
            corr.sources.append(source)
        
        # Calculate confidence based on occurrences and source diversity
        base_confidence = {
            "email": 80,
            "phone": 75,
            "username": 65,
            "social": 90,
            "address": 55,
        }.get(data_type, 50)
        
        source_bonus = min(len(corr.sources) * 5, 20)
        occurrence_bonus = min(corr.occurrences * 2, 10)
        
        corr.confidence = min(base_confidence + source_bonus + occurrence_bonus, 100)
        
        self.data_points[data_type].add(value)
    
    def get_correlations(self, min_occurrences: int = 2) -> List[CorrelationResult]:
        """Get correlated data points"""
        return [
            corr for corr in self.correlations.values()
            if corr.occurrences >= min_occurrences
        ]
    
    def find_related(self, data_type: str, value: str) -> List[CorrelationResult]:
        """Find data related to a specific value"""
        related = []
        
        # Find same type
        for key, corr in self.correlations.items():
            if corr.data_type == data_type and value.lower() in corr.key.lower():
                related.append(corr)
        
        # Find in same sources
        target_key = f"{data_type}:{value}"
        if target_key in self.correlations:
            target_sources = set(self.correlations[target_key].sources)
            
            for key, corr in self.correlations.items():
                if key != target_key:
                    source_overlap = target_sources.intersection(corr.sources)
                    if source_overlap:
                        related.append(corr)
        
        return related
    
    def generate_profile(self) -> Dict[str, Any]:
        """Generate comprehensive profile from correlated data"""
        profile = {
            "emails": list(self.data_points.get("email", set())),
            "phones": list(self.data_points.get("phone", set())),
            "usernames": list(self.data_points.get("username", set())),
            "social_accounts": list(self.data_points.get("social", set())),
            "addresses": list(self.data_points.get("address", set())),
            "high_confidence_findings": [
                {
                    "type": corr.data_type,
                    "value": corr.key.split(":", 1)[1],
                    "confidence": corr.confidence,
                    "sources": corr.sources[:5],  # Top 5 sources
                }
                for corr in sorted(
                    self.correlations.values(),
                    key=lambda x: x.confidence,
                    reverse=True
                )[:20]
            ],
            "statistics": {
                "total_emails": len(self.data_points.get("email", set())),
                "total_phones": len(self.data_points.get("phone", set())),
                "total_usernames": len(self.data_points.get("username", set())),
                "total_social": len(self.data_points.get("social", set())),
                "total_addresses": len(self.data_points.get("address", set())),
            }
        }
        
        return profile
