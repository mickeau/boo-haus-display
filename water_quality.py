"""
Exmouth Beach Water Quality Monitor
Fetches and displays water quality data from Environment Agency API.
Exports JSON data suitable for e-ink displays.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional


class ExmouthWaterQuality:
    """Fetch and process Exmouth bathing water quality data."""
    
    # Water quality thresholds (EU Bathing Water Directive)
    THRESHOLDS = {
        'ecoli': [(250, 'Excellent'), (500, 'Good'), (900, 'Sufficient')],
        'enterococci': [(100, 'Excellent'), (200, 'Good'), (330, 'Sufficient')]
    }
    
    def __init__(self, beach_id: str = "ukk4301-22300"):
        self.beach_id = beach_id
        self.base_url = "https://environment.data.gov.uk"
    
    def _get_json(self, endpoint: str, params: dict = None) -> dict:
        """Make API request and return JSON response."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API Error ({endpoint}): {e}")
            return {}
    
    def _extract_items(self, data: dict) -> List[dict]:
        """Extract items from LDA API response."""
        return data.get('result', {}).get('items', [])
    
    def _get_rating(self, value: Optional[float], bacteria_type: str) -> str:
        """Determine rating for bacterial count."""
        if value is None:
            return 'Unknown'
        
        for threshold, rating in self.THRESHOLDS[bacteria_type]:
            if value < threshold:
                return rating
        return 'Poor'
    
    def _get_overall_rating(self, ecoli: Optional[float], enterococci: Optional[float]) -> str:
        """Get worst rating of the two bacteria types."""
        ratings = {'Excellent': 1, 'Good': 2, 'Sufficient': 3, 'Poor': 4, 'Unknown': 5}
        
        ecoli_rating = self._get_rating(ecoli, 'ecoli')
        entero_rating = self._get_rating(enterococci, 'enterococci')
        
        worst = max(ecoli_rating, entero_rating, key=lambda r: ratings.get(r, 5))
        return worst if worst != 'Unknown' else 'Unknown'
    
    def _parse_datetime(self, date_str: str) -> Dict[str, str]:
        """Parse datetime from API response."""
        try:
            # Handle URI format: http://reference.data.gov.uk/id/gregorian-instant/2025-08-12T10:40:00
            if 'gregorian-instant' in str(date_str):
                date_str = date_str.split('/')[-1]
            
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return {
                'date': dt.strftime('%Y-%m-%d'),
                'time': dt.strftime('%H:%M:%S'),
                'datetime': dt.isoformat()
            }
        except (ValueError, AttributeError):
            return {'date': str(date_str), 'time': 'N/A', 'datetime': str(date_str)}
    
    def _safe_get(self, obj, *keys, default='N/A'):
        """Safely navigate nested dictionaries/lists."""
        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, list) and obj:
                obj = obj[0]
            else:
                return default
        return obj if obj is not None else default
    
    def get_beach_info(self) -> dict:
        """Fetch beach metadata."""
        data = self._get_json(f"/doc/bathing-water/{self.beach_id}.json")
        beach = data.get('primaryTopic', {})
        sp = beach.get('samplingPoint', {})
        
        return {
            'name': self._safe_get(beach, 'name', '_value'),
            'id': self.beach_id,
            'easting': sp.get('easting'),
            'northing': sp.get('northing'),
            'latitude': sp.get('lat'),
            'longitude': sp.get('long'),
            'district': self._safe_get(beach, 'district', 'name', '_value')
        }
    
    def get_current_classification(self) -> dict:
        """Fetch current annual classification."""
        data = self._get_json(f"/doc/bathing-water/{self.beach_id}.json")
        comp = data.get('primaryTopic', {}).get('latestComplianceAssessment', {})
        
        return {
            'rating': self._safe_get(comp, 'complianceClassification', 'name', '_value'),
            'year': self._safe_get(comp, 'sampleYear', 'ordinalYear')
        }
    
    def get_samples(self, limit: int = 10) -> List[dict]:
        """Fetch recent water quality samples."""
        endpoint = f"/doc/bathing-water-quality/in-season/bathing-water/{self.beach_id}.json"
        data = self._get_json(endpoint, {'_pageSize': limit, '_sort': '-sampleDateTime'})
        
        samples = []
        for item in self._extract_items(data):
            ecoli = item.get('escherichiaColiCount')
            entero = item.get('intestinalEnterococciCount')
            
            date_obj = item.get('sampleDateTime', {})
            date_str = date_obj.get('inXSDDateTime', date_obj) if isinstance(date_obj, dict) else date_obj
            dt_info = self._parse_datetime(str(date_str))
            
            samples.append({
                'date': dt_info['date'],
                'time': dt_info['time'],
                'datetime': dt_info['datetime'],
                'ecoli': ecoli,
                'ecoli_rating': self._get_rating(ecoli, 'ecoli') if ecoli else None,
                'enterococci': entero,
                'enterococci_rating': self._get_rating(entero, 'enterococci') if entero else None,
                'overall_rating': self._get_overall_rating(ecoli, entero)
            })
        
        return samples
    
    def get_compliance_history(self, limit: int = 10) -> List[dict]:
        """Fetch annual compliance history."""
        endpoint = f"/doc/bathing-water-quality/compliance-rBWD/bathing-water/{self.beach_id}.json"
        data = self._get_json(endpoint, {'_pageSize': limit})
        
        history = []
        for item in self._extract_items(data):
            history.append({
                'year': self._safe_get(item, 'sampleYear', 'ordinalYear'),
                'rating': self._safe_get(item, 'complianceClassification', 'name', '_value')
            })
        
        return history
    
    def get_risk_predictions(self, limit: int = 5) -> List[dict]:
        """Fetch pollution risk forecasts."""
        endpoint = f"/doc/bathing-water-quality/stp-risk-prediction/bathing-water/{self.beach_id}.json"
        data = self._get_json(endpoint, {'_pageSize': limit})
        
        predictions = []
        for item in self._extract_items(data):
            predictions.append({
                'issue_date': item.get('issueDate', 'N/A'),
                'risk_level': self._safe_get(item, 'riskLevel', 'name', '_value')
            })
        
        return predictions
    
    def generate_report(self) -> dict:
        """Generate complete water quality report."""
        samples = self.get_samples(10)
        
        return {
            'generated_at': datetime.now().isoformat(),
            'beach_info': self.get_beach_info(),
            'current_classification': self.get_current_classification(),
            'latest_sample': samples[0] if samples else {},
            'recent_samples': samples,
            'compliance_history': self.get_compliance_history(),
            'risk_predictions': self.get_risk_predictions()
        }
    
    def save_json(self, filename: str = 'exmouth_water_quality.json'):
        """Export data to JSON file."""
        data = self.generate_report()
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Exported to: {filename} ({len(json.dumps(data))} bytes)")
            return data
        except IOError as e:
            print(f"❌ Export failed: {e}")
            return None
    
    def display_report(self):
        """Display formatted report to console."""
        data = self.generate_report()
        beach = data['beach_info']
        current = data['current_classification']
        samples = data['recent_samples']
        
        # Header
        print("=" * 80)
        print(f"EXMOUTH BEACH - WATER QUALITY REPORT")
        print("=" * 80)
        
        # Beach info
        print(f"\n📍 {beach['name']} (ID: {beach['id']})")
        print(f"   Location: {beach['latitude']}, {beach['longitude']}")
        print(f"   District: {beach['district']}")
        
        # Current classification
        print(f"\n🎯 Current: {current['rating']} ({current['year']})")
        
        # Recent samples
        if samples:
            print(f"\n🔬 RECENT SAMPLES ({len(samples)})")
            print("-" * 80)
            for i, s in enumerate(samples, 1):
                print(f"\nSample {i} - {s['date']} at {s['time']}")
                
                if s['ecoli']:
                    emoji = "✅" if s['ecoli'] < 250 else ("✓" if s['ecoli'] < 500 else "⚠️")
                    print(f"  E. coli: {s['ecoli']} cfu/100ml {emoji} ({s['ecoli_rating']})")
                
                if s['enterococci']:
                    emoji = "✅" if s['enterococci'] < 100 else ("✓" if s['enterococci'] < 200 else "⚠️")
                    print(f"  Enterococci: {s['enterococci']} cfu/100ml {emoji} ({s['enterococci_rating']})")
                
                if s['ecoli'] and s['enterococci']:
                    print(f"  Overall: {s['overall_rating']}")
        else:
            print("\n❌ No recent samples (outside bathing season May-Sept)")
        
        # Compliance history
        history = data['compliance_history']
        if history:
            print(f"\n📅 COMPLIANCE HISTORY")
            print("-" * 80)
            for h in history:
                emoji = "🌟" if 'Excellent' in h['rating'] else ("✅" if 'Good' in h['rating'] else "⚠️")
                print(f"   {h['year']}: {h['rating']} {emoji}")
        
        # Risk predictions
        risks = data['risk_predictions']
        if risks:
            print(f"\n⚠️  RISK FORECASTS")
            print("-" * 80)
            for r in risks:
                print(f"   {r['issue_date']}: {r['risk_level']}")
        
        print("\n" + "=" * 80)
        
        # Save JSON
        self.save_json()


def main():
    """Run the water quality monitor."""
    monitor = ExmouthWaterQuality()
    monitor.display_report()
    
    print("\n💡 Usage:")
    print("   monitor = ExmouthWaterQuality('ukk4301-22300')")
    print("   data = monitor.generate_report()")
    print("   monitor.save_json('custom_filename.json')")
    print("\n📖 API Docs: https://environment.data.gov.uk/bwq/doc/api-reference-v0.6.html\n")


if __name__ == "__main__":
    main()