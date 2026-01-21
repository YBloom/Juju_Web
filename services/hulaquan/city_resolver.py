import json
import os
from typing import Dict, List, Optional
from pathlib import Path

class CityResolver:
    """Helper class to resolve city from venue name or title using configurable rules."""
    
    def __init__(self, config_path: str = "config/venue_city_mapping.json"):
        # Resolve absolute path relative to project root (assuming this file is in services/hulaquan)
        # But let's be robust: user might pass absolute path or relative
        if not os.path.isabs(config_path):
            # Try to find config relative to project root
            # Assumption: current working directory is usually project root in this environment
            # Or relative to this file: ../../config/venue_city_mapping.json
            base_dir = Path(os.getcwd())
            potential_path = base_dir / config_path
            if not potential_path.exists():
                # Fallback to module relative path
                base_dir = Path(__file__).parent.parent.parent
                potential_path = base_dir / config_path
            
            self.config_path = str(potential_path)
        else:
            self.config_path = config_path
            
        self.venue_rules: Dict[str, List[str]] = {}
        self.title_rules: Dict[str, List[str]] = {}
        self._load_config()

    def _load_config(self):
        try:
            if not os.path.exists(self.config_path):
                print(f"Warning: CityResolver config not found at {self.config_path}")
                return

            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.venue_rules = data.get("venue_keywords", {})
                self.title_rules = data.get("title_keywords", {})
        except Exception as e:
            print(f"Error loading CityResolver config: {e}")

    def from_venue(self, location: str) -> Optional[str]:
        if not location:
            return None
        
        for city, keywords in self.venue_rules.items():
            for kw in keywords:
                if kw in location:
                    return city
        return None

    def from_title(self, title: str) -> Optional[str]:
        if not title:
            return None
            
        for city, keywords in self.title_rules.items():
            for kw in keywords:
                if kw in title:
                    return city
        return None
