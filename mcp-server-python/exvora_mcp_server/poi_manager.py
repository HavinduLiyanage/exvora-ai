"""POI Management functionality for Exvora MCP Server"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import csv
import io


class POIManager:
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.pois_file = data_path / "pois.sample.json"

    async def load_pois(self) -> List[Dict[str, Any]]:
        """Load POIs from the dataset file"""
        try:
            with open(self.pois_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except FileNotFoundError:
            raise FileNotFoundError(f"POI dataset not found at {self.pois_file}")
        except Exception as e:
            raise Exception(f"Failed to load POI data: {str(e)}")

    async def save_pois(self, pois: List[Dict[str, Any]]) -> None:
        """Save POIs to the dataset file"""
        try:
            with open(self.pois_file, 'w', encoding='utf-8') as f:
                json.dump(pois, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Failed to save POI data: {str(e)}")

    async def search_pois(
        self,
        themes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        price_band: Optional[str] = None,
        region: Optional[str] = None,
        max_cost: Optional[float] = None,
        limit: int = 10
    ) -> str:
        """Search POIs with various filters"""
        pois = await self.load_pois()
        
        filtered = []
        for poi in pois:
            # Theme filtering
            if themes:
                poi_themes = poi.get('themes', [])
                if not any(theme.lower() in [t.lower() for t in poi_themes] for theme in themes):
                    continue
            
            # Tag filtering
            if tags:
                poi_tags = poi.get('tags', [])
                if not any(tag.lower() in [t.lower() for t in poi_tags] for tag in tags):
                    continue
            
            # Price band filtering
            if price_band and poi.get('price_band') != price_band:
                continue
            
            # Region filtering
            if region:
                poi_region = poi.get('region', '')
                if region.lower() not in poi_region.lower():
                    continue
            
            # Cost filtering
            if max_cost and poi.get('estimated_cost', 0) > max_cost:
                continue
            
            filtered.append(poi)
        
        # Limit results
        filtered = filtered[:limit]
        
        # Format response
        result = f"Found {len(filtered)} POIs matching your criteria:\n\n"
        
        for poi in filtered:
            result += f"**{poi.get('name', 'Unknown')}** ({poi.get('poi_id', 'No ID')})\n"
            result += f"- Themes: {', '.join(poi.get('themes', []))}\n"
            result += f"- Tags: {', '.join(poi.get('tags', []))}\n"
            result += f"- Price: {poi.get('price_band', 'N/A')} ({poi.get('estimated_cost', 0)} LKR)\n"
            result += f"- Duration: {poi.get('duration_minutes', 'N/A')} minutes\n"
            result += f"- Region: {poi.get('region', 'N/A')}\n\n"
        
        return result

    async def get_poi_details(self, poi_id: str, place_id: Optional[str] = None) -> str:
        """Get detailed information about a specific POI"""
        pois = await self.load_pois()
        
        poi = None
        for p in pois:
            if p.get('poi_id') == poi_id or (place_id and p.get('place_id') == place_id):
                poi = p
                break
        
        if not poi:
            raise ValueError(f"POI not found with ID: {poi_id or place_id}")
        
        # Format opening hours
        opening_hours = poi.get('opening_hours', {})
        hours_text = "Not specified"
        if opening_hours:
            hours_list = []
            for day, times in opening_hours.items():
                if isinstance(times, list) and times:
                    time_str = ', '.join([f"{t.get('open', '')}-{t.get('close', '')}" for t in times])
                    hours_list.append(f"- {day.upper()}: {time_str}")
                else:
                    hours_list.append(f"- {day.upper()}: Closed")
            hours_text = '\n'.join(hours_list)
        
        result = f"**{poi.get('name', 'Unknown')}**\n\n"
        result += "**Details:**\n"
        result += f"- POI ID: {poi.get('poi_id', 'N/A')}\n"
        result += f"- Place ID: {poi.get('place_id', 'N/A')}\n"
        result += f"- Coordinates: {poi.get('coords', {}).get('lat', 'N/A')}, {poi.get('coords', {}).get('lng', 'N/A')}\n"
        result += f"- Themes: {', '.join(poi.get('themes', []))}\n"
        result += f"- Tags: {', '.join(poi.get('tags', []))}\n"
        result += f"- Price Band: {poi.get('price_band', 'N/A')}\n"
        result += f"- Estimated Cost: {poi.get('estimated_cost', 0)} LKR\n"
        result += f"- Duration: {poi.get('duration_minutes', 'N/A')} minutes\n"
        result += f"- Region: {poi.get('region', 'N/A')}\n"
        result += f"- Safety Flags: {', '.join(poi.get('safety_flags', []))}\n"
        result += f"- Seasonality: {poi.get('seasonality', 'Year-round')}\n\n"
        result += f"**Opening Hours:**\n{hours_text}\n\n"
        result += f"**Description:** {poi.get('description', 'No description available')}\n\n"
        result += f"**Raw Data:**\n```json\n{json.dumps(poi, indent=2, ensure_ascii=False)}\n```"
        
        return result

    async def add_poi(
        self,
        poi_id: str,
        name: str,
        coords: Dict[str, float],
        tags: List[str],
        themes: List[str],
        price_band: str,
        place_id: Optional[str] = None,
        estimated_cost: Optional[float] = None,
        duration_minutes: Optional[int] = None,
        region: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> str:
        """Add a new POI to the dataset"""
        pois = await self.load_pois()
        
        # Check for duplicate poi_id
        if any(p.get('poi_id') == poi_id for p in pois):
            raise ValueError(f"POI with ID {poi_id} already exists")
        
        # Create new POI
        new_poi = {
            "poi_id": poi_id,
            "place_id": place_id,
            "name": name,
            "coords": coords,
            "tags": tags,
            "themes": themes,
            "price_band": price_band,
            "estimated_cost": estimated_cost or 0,
            "duration_minutes": duration_minutes or 60,
            "region": region,
            "description": description,
            "opening_hours": kwargs.get('opening_hours', {}),
            "safety_flags": [],
            "seasonality": "year-round"
        }
        
        pois.append(new_poi)
        await self.save_pois(pois)
        
        result = f"✅ Successfully added POI: **{name}** ({poi_id})\n\n"
        result += "The POI has been added to the dataset with the following details:\n"
        result += f"- Themes: {', '.join(themes)}\n"
        result += f"- Tags: {', '.join(tags)}\n"
        result += f"- Price Band: {price_band}\n"
        result += f"- Location: {coords['lat']}, {coords['lng']}\n\n"
        result += f"Total POIs in dataset: {len(pois)}"
        
        return result

    async def export_data(
        self,
        format: str = "json",
        filter: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export POI data in various formats"""
        pois = await self.load_pois()
        
        # Apply filters if provided
        if filter:
            filtered_pois = []
            for poi in pois:
                # Theme filter
                if 'themes' in filter:
                    poi_themes = poi.get('themes', [])
                    if not any(theme in poi_themes for theme in filter['themes']):
                        continue
                
                # Price band filter
                if 'price_band' in filter and poi.get('price_band') != filter['price_band']:
                    continue
                
                # Region filter
                if 'region' in filter and poi.get('region') != filter['region']:
                    continue
                
                filtered_pois.append(poi)
            pois = filtered_pois
        
        # Generate export data
        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            
            # CSV Header
            writer.writerow([
                'poi_id', 'name', 'lat', 'lng', 'themes', 'tags', 
                'price_band', 'estimated_cost', 'duration_minutes', 'region'
            ])
            
            # CSV Rows
            for poi in pois:
                coords = poi.get('coords', {})
                writer.writerow([
                    poi.get('poi_id', ''),
                    poi.get('name', ''),
                    coords.get('lat', ''),
                    coords.get('lng', ''),
                    ';'.join(poi.get('themes', [])),
                    ';'.join(poi.get('tags', [])),
                    poi.get('price_band', ''),
                    poi.get('estimated_cost', 0),
                    poi.get('duration_minutes', ''),
                    poi.get('region', '')
                ])
            
            export_data = output.getvalue()
            filename = 'pois_export.csv'
            
        elif format == "geojson":
            features = []
            for poi in pois:
                coords = poi.get('coords', {})
                if coords.get('lat') and coords.get('lng'):
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [coords['lng'], coords['lat']]
                        },
                        "properties": {
                            "poi_id": poi.get('poi_id'),
                            "name": poi.get('name'),
                            "themes": poi.get('themes', []),
                            "tags": poi.get('tags', []),
                            "price_band": poi.get('price_band'),
                            "estimated_cost": poi.get('estimated_cost'),
                            "duration_minutes": poi.get('duration_minutes'),
                            "region": poi.get('region')
                        }
                    }
                    features.append(feature)
            
            geojson_data = {
                "type": "FeatureCollection",
                "features": features
            }
            export_data = json.dumps(geojson_data, indent=2, ensure_ascii=False)
            filename = 'pois_export.geojson'
            
        else:  # JSON format
            export_data = json.dumps(pois, indent=2, ensure_ascii=False)
            filename = 'pois_export.json'
        
        # Save to file
        export_path = self.data_path.parent / "mcp-server-python" / filename
        export_path.parent.mkdir(exist_ok=True)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(export_data)
        
        result = f"✅ **Data Export Complete**\n\n"
        result += f"- **Format:** {format.upper()}\n"
        result += f"- **Records:** {len(pois)} POIs\n"
        result += f"- **File:** {filename}\n"
        result += f"- **Location:** {export_path}\n\n"
        result += f"**Preview:**\n```{format}\n{export_data[:500]}{'...' if len(export_data) > 500 else ''}\n```"
        
        return result