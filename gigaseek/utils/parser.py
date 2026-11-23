"""
Advanced parsing utilities for GIGASEEK
Extract data from HTML, JSON, and text responses
"""

import re
import json
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from selectolax.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import orjson


@dataclass
class ExtractedData:
    """Container for extracted data"""
    emails: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    usernames: Set[str] = field(default_factory=set)
    urls: Set[str] = field(default_factory=set)
    social_links: Dict[str, List[str]] = field(default_factory=dict)
    addresses: Set[str] = field(default_factory=set)
    names: Set[str] = field(default_factory=set)
    images: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    
    def merge(self, other: "ExtractedData"):
        """Merge another ExtractedData into this one"""
        self.emails.update(other.emails)
        self.phones.update(other.phones)
        self.usernames.update(other.usernames)
        self.urls.update(other.urls)
        self.addresses.update(other.addresses)
        self.names.update(other.names)
        self.images.update(other.images)
        
        for platform, links in other.social_links.items():
            if platform not in self.social_links:
                self.social_links[platform] = []
            self.social_links[platform].extend(links)
        
        self.metadata.update(other.metadata)


class DataExtractor:
    """Extract various data types from web content"""
    
    # Regex patterns
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    PHONE_PATTERNS = [
        re.compile(r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
        re.compile(r'\+?[2-9]\d{1,2}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'),
        re.compile(r'\(\d{3}\)\s?\d{3}-\d{4}'),
    ]
    
    USERNAME_PATTERN = re.compile(
        r'@([a-zA-Z0-9._-]{2,30})\b'
    )
    
    URL_PATTERN = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    
    # Social platform patterns
    SOCIAL_PATTERNS = {
        "twitter": re.compile(r'(?:twitter\.com|x\.com)/(@?[a-zA-Z0-9_]{1,15})', re.I),
        "instagram": re.compile(r'instagram\.com/([a-zA-Z0-9._]{1,30})', re.I),
        "facebook": re.compile(r'facebook\.com/([a-zA-Z0-9.]{1,50})', re.I),
        "linkedin": re.compile(r'linkedin\.com/(?:in|company)/([a-zA-Z0-9-]{1,100})', re.I),
        "github": re.compile(r'github\.com/([a-zA-Z0-9-]{1,39})', re.I),
        "youtube": re.compile(r'youtube\.com/@?([a-zA-Z0-9_-]{1,100})', re.I),
        "tiktok": re.compile(r'tiktok\.com/@([a-zA-Z0-9._]{1,24})', re.I),
        "reddit": re.compile(r'reddit\.com/user/([a-zA-Z0-9_-]{1,20})', re.I),
        "pinterest": re.compile(r'pinterest\.com/([a-zA-Z0-9_-]{1,30})', re.I),
        "snapchat": re.compile(r'snapchat\.com/add/([a-zA-Z0-9._]{1,30})', re.I),
        "telegram": re.compile(r't\.me/([a-zA-Z0-9_]{1,32})', re.I),
        "discord": re.compile(r'discord\.gg/([a-zA-Z0-9-]{1,100})', re.I),
    }
    
    def __init__(self):
        self.parser: Optional[HTMLParser] = None
    
    def extract_from_html(self, html: str, base_url: str = "") -> ExtractedData:
        """Extract all data types from HTML content"""
        data = ExtractedData()
        data.raw_text = html
        
        # Parse HTML
        self.parser = HTMLParser(html)
        
        # Extract from text content
        text_content = self.parser.text()
        
        # Emails
        data.emails.update(self.extract_emails(text_content))
        data.emails.update(self.extract_emails_from_html(html))
        
        # Phones
        data.phones.update(self.extract_phones(text_content))
        
        # Usernames
        data.usernames.update(self.extract_usernames(text_content))
        
        # URLs
        data.urls.update(self.extract_urls(text_content))
        
        # Social links
        data.social_links = self.extract_social_links(html, base_url)
        
        # Images
        data.images.update(self.extract_images(html, base_url))
        
        # Metadata
        data.metadata = self.extract_metadata(html)
        
        # Addresses (basic pattern matching)
        data.addresses.update(self.extract_addresses(text_content))
        
        return data
    
    def extract_from_json(self, json_data: str or dict) -> ExtractedData:
        """Extract data from JSON content"""
        data = ExtractedData()
        
        if isinstance(json_data, str):
            try:
                parsed = orjson.loads(json_data)
            except:
                return data
        else:
            parsed = json_data
        
        # Convert to string for regex extraction
        json_str = json.dumps(parsed)
        data.raw_text = json_str
        
        # Extract using regex
        data.emails.update(self.extract_emails(json_str))
        data.phones.update(self.extract_phones(json_str))
        data.usernames.update(self.extract_usernames(json_str))
        data.urls.update(self.extract_urls(json_str))
        
        return data
    
    def extract_emails(self, text: str) -> Set[str]:
        """Extract email addresses from text"""
        emails = set()
        matches = self.EMAIL_PATTERN.findall(text)
        
        for email in matches:
            # Filter out common false positives
            if not any(x in email.lower() for x in ['example.com', 'test.com', 'fake.com', 'email.com']):
                if len(email) < 100:  # Sanity check
                    emails.add(email.lower())
        
        return emails
    
    def extract_emails_from_html(self, html: str) -> Set[str]:
        """Extract emails from mailto links and obfuscated sources"""
        emails = set()
        
        # mailto links
        mailto_pattern = re.compile(r'mailto:([^"\'>\s]+@[^"\'>\s]+)', re.I)
        emails.update(mailto_pattern.findall(html))
        
        # Common obfuscation patterns
        obfuscated = re.compile(r'([a-zA-Z0-9._%+-]+)\s*\[at\]\s*([a-zA-Z0-9.-]+)\s*\[dot\]\s*([a-zA-Z]{2,})', re.I)
        for match in obfuscated.findall(html):
            emails.add(f"{match[0]}@{match[1]}.{match[2]}".lower())
        
        return {e.lower() for e in emails if len(e) < 100}
    
    def extract_phones(self, text: str) -> Set[str]:
        """Extract phone numbers from text"""
        phones = set()
        
        for pattern in self.PHONE_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                # Clean up the number
                cleaned = re.sub(r'[^\d+]', '', match)
                if 7 <= len(cleaned) <= 15:  # Valid phone length
                    phones.add(cleaned)
        
        return phones
    
    def extract_usernames(self, text: str) -> Set[str]:
        """Extract usernames (mentions) from text"""
        usernames = set()
        matches = self.USERNAME_PATTERN.findall(text)
        
        for username in matches:
            # Filter out common false positives
            if username.lower() not in {'example', 'test', 'user', 'admin', 'null', 'undefined'}:
                if 2 <= len(username) <= 30:
                    usernames.add(username)
        
        return usernames
    
    def extract_urls(self, text: str) -> Set[str]:
        """Extract URLs from text"""
        urls = set()
        matches = self.URL_PATTERN.findall(text)
        
        for url in matches:
            # Basic filtering
            if not any(x in url.lower() for x in ['example.com', 'test.com', 'w3.org', 'schema.org']):
                if len(url) < 500:
                    urls.add(url)
        
        return urls
    
    def extract_social_links(self, html: str, base_url: str = "") -> Dict[str, List[str]]:
        """Extract social media links and usernames"""
        social = {}
        
        for platform, pattern in self.SOCIAL_PATTERNS.items():
            matches = pattern.findall(html)
            if matches:
                social[platform] = list(set(matches))
        
        # Also extract from href attributes
        if self.parser:
            for node in self.parser.css('a[href]'):
                href = node.attributes.get('href', '')
                if not href:
                    continue
                
                # Make absolute URL
                if base_url and not href.startswith('http'):
                    href = urljoin(base_url, href)
                
                for platform, pattern in self.SOCIAL_PATTERNS.items():
                    match = pattern.search(href)
                    if match:
                        if platform not in social:
                            social[platform] = []
                        username = match.group(1)
                        if username not in social[platform]:
                            social[platform].append(username)
        
        return social
    
    def extract_images(self, html: str, base_url: str = "") -> Set[str]:
        """Extract image URLs"""
        images = set()
        
        if self.parser:
            for node in self.parser.css('img[src]'):
                src = node.attributes.get('src', '')
                if src:
                    if base_url and not src.startswith('http'):
                        src = urljoin(base_url, src)
                    if not any(x in src.lower() for x in ['logo', 'icon', 'pixel', 'tracking']):
                        images.add(src)
        
        return images
    
    def extract_metadata(self, html: str) -> Dict[str, Any]:
        """Extract meta tags and structured data"""
        metadata = {}
        
        if not self.parser:
            return metadata
        
        # Standard meta tags
        for node in self.parser.css('meta[name], meta[property]'):
            name = node.attributes.get('name') or node.attributes.get('property')
            content = node.attributes.get('content', '')
            if name and content:
                metadata[name] = content
        
        # Open Graph
        og_data = {}
        for node in self.parser.css('meta[property^="og:"]'):
            prop = node.attributes.get('property', '')
            content = node.attributes.get('content', '')
            if prop and content:
                og_data[prop] = content
        
        if og_data:
            metadata['open_graph'] = og_data
        
        # Twitter Cards
        twitter_data = {}
        for node in self.parser.css('meta[name^="twitter:"]'):
            name = node.attributes.get('name', '')
            content = node.attributes.get('content', '')
            if name and content:
                twitter_data[name] = content
        
        if twitter_data:
            metadata['twitter_card'] = twitter_data
        
        # JSON-LD structured data
        for node in self.parser.css('script[type="application/ld+json"]'):
            try:
                json_data = orjson.loads(node.text())
                if '@type' in json_data:
                    metadata['structured_data'] = json_data
            except:
                pass
        
        return metadata
    
    def extract_addresses(self, text: str) -> Set[str]:
        """Extract potential addresses from text"""
        addresses = set()
        
        # Basic address patterns
        patterns = [
            # Street address
            re.compile(r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\b', re.I),
            # City, State ZIP
            re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'),
            # ZIP code
            re.compile(r'\b\d{5}(?:-\d{4})?\b'),
        ]
        
        for pattern in patterns:
            matches = pattern.findall(text)
            addresses.update(matches)
        
        return addresses
    
    def extract_names(self, text: str) -> Set[str]:
        """Extract potential person names from text"""
        names = set()
        
        # Simple pattern: Capitalized words that could be names
        name_pattern = re.compile(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b')
        
        for match in name_pattern.findall(text):
            first, last = match
            # Filter out common non-names
            if first.lower() not in {'the', 'this', 'that', 'these', 'those', 'there', 'where', 'when', 'what', 'how', 'why', 'is', 'are', 'was', 'were'}:
                if len(first) > 1 and len(last) > 1:
                    names.add(f"{first} {last}")
        
        return names


class ContentAnalyzer:
    """Analyze content for OSINT value"""
    
    def __init__(self):
        self.extractor = DataExtractor()
    
    def analyze_response(self, html: str, url: str) -> Dict[str, Any]:
        """Full analysis of an HTTP response"""
        extracted = self.extractor.extract_from_html(html, url)
        
        # Calculate OSINT value score
        score = 0
        score += len(extracted.emails) * 10
        score += len(extracted.phones) * 8
        score += len(extracted.usernames) * 5
        score += len(extracted.social_links) * 15
        score += len(extracted.addresses) * 12
        
        return {
            "url": url,
            "extracted": extracted,
            "osint_score": score,
            "has_contact_info": len(extracted.emails) > 0 or len(extracted.phones) > 0,
            "has_social": len(extracted.social_links) > 0,
            "data_types": {
                "emails": len(extracted.emails),
                "phones": len(extracted.phones),
                "usernames": len(extracted.usernames),
                "social_platforms": len(extracted.social_links),
                "addresses": len(extracted.addresses),
            }
        }
