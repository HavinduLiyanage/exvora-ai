"""Data Validation functionality for Exvora MCP Server"""

from typing import Any, Dict, List, Tuple
import json


class DataValidator:
    def __init__(self, poi_manager):
        self.poi_manager = poi_manager

    async def validate(self, fix_issues: bool = False) -> str:
        """Validate the POI dataset for completeness and consistency"""
        
        pois = await self.poi_manager.load_pois()
        
        issues = []
        warnings = []
        fixed_count = 0
        
        # Track for duplicate detection
        poi_ids = set()
        place_ids = set()
        
        for index, poi in enumerate(pois):
            poi_name = poi.get('name', f'POI #{index}')
            
            # Critical validations (issues)
            issues.extend(self._validate_required_fields(poi, index, poi_name))
            issues.extend(self._validate_coordinates(poi, index, poi_name))
            issues.extend(self._validate_enums(poi, index, poi_name))
            
            # Duplicate detection
            poi_id = poi.get('poi_id')
            if poi_id:
                if poi_id in poi_ids:
                    issues.append(f"POI {index} ({poi_name}): Duplicate poi_id '{poi_id}'")
                else:
                    poi_ids.add(poi_id)
            
            place_id = poi.get('place_id')
            if place_id:
                if place_id in place_ids:
                    warnings.append(f"POI {index} ({poi_name}): Duplicate place_id '{place_id}'")
                else:
                    place_ids.add(place_id)
            
            # Warnings and auto-fixes
            warning_count, fix_count = await self._validate_and_fix_optional_fields(
                poi, index, poi_name, fix_issues
            )
            warnings.extend(warning_count)
            fixed_count += fix_count
        
        # Cross-validation checks
        issues.extend(self._validate_data_consistency(pois))
        
        # Save fixes if any were made
        if fix_issues and fixed_count > 0:
            await self.poi_manager.save_pois(pois)
        
        # Generate report
        return self._generate_validation_report(pois, issues, warnings, fixed_count)

    def _validate_required_fields(self, poi: Dict[str, Any], index: int, poi_name: str) -> List[str]:
        """Validate required fields are present and valid"""
        issues = []
        
        # Required string fields
        required_fields = ['poi_id', 'name']
        for field in required_fields:
            if not poi.get(field):
                issues.append(f"POI {index} ({poi_name}): Missing required field '{field}'")
        
        # Required array fields
        if not poi.get('themes') or not isinstance(poi.get('themes'), list) or len(poi.get('themes', [])) == 0:
            issues.append(f"POI {index} ({poi_name}): Missing or empty 'themes' array")
        
        if not poi.get('tags') or not isinstance(poi.get('tags'), list):
            issues.append(f"POI {index} ({poi_name}): Missing or invalid 'tags' array")
        
        return issues

    def _validate_coordinates(self, poi: Dict[str, Any], index: int, poi_name: str) -> List[str]:
        """Validate coordinate data"""
        issues = []
        
        coords = poi.get('coords')
        if not coords or not isinstance(coords, dict):
            issues.append(f"POI {index} ({poi_name}): Missing or invalid 'coords' object")
            return issues
        
        # Check latitude
        lat = coords.get('lat')
        if not isinstance(lat, (int, float)):
            issues.append(f"POI {index} ({poi_name}): Invalid latitude type")
        elif not (-90 <= lat <= 90):
            issues.append(f"POI {index} ({poi_name}): Latitude {lat} out of valid range (-90 to 90)")
        elif not (5.0 <= lat <= 10.0):  # Sri Lanka bounds
            issues.append(f"POI {index} ({poi_name}): Latitude {lat} outside Sri Lanka bounds")
        
        # Check longitude
        lng = coords.get('lng')
        if not isinstance(lng, (int, float)):
            issues.append(f"POI {index} ({poi_name}): Invalid longitude type")
        elif not (-180 <= lng <= 180):
            issues.append(f"POI {index} ({poi_name}): Longitude {lng} out of valid range (-180 to 180)")
        elif not (79.0 <= lng <= 82.0):  # Sri Lanka bounds
            issues.append(f"POI {index} ({poi_name}): Longitude {lng} outside Sri Lanka bounds")
        
        return issues

    def _validate_enums(self, poi: Dict[str, Any], index: int, poi_name: str) -> List[str]:
        """Validate enumerated fields"""
        issues = []
        
        # Price band validation
        price_band = poi.get('price_band')
        valid_price_bands = ['low', 'medium', 'high']
        if price_band not in valid_price_bands:
            issues.append(f"POI {index} ({poi_name}): Invalid price_band '{price_band}', must be one of {valid_price_bands}")
        
        return issues

    async def _validate_and_fix_optional_fields(
        self, poi: Dict[str, Any], index: int, poi_name: str, fix_issues: bool
    ) -> Tuple[List[str], int]:
        """Validate optional fields and apply fixes if requested"""
        warnings = []
        fixes = 0
        
        # Estimated cost validation and fixing
        estimated_cost = poi.get('estimated_cost')
        if estimated_cost is None:
            warnings.append(f"POI {index} ({poi_name}): Missing 'estimated_cost'")
            if fix_issues:
                poi['estimated_cost'] = 0
                fixes += 1
        elif not isinstance(estimated_cost, (int, float)) or estimated_cost < 0:
            warnings.append(f"POI {index} ({poi_name}): Invalid 'estimated_cost' value: {estimated_cost}")
            if fix_issues:
                poi['estimated_cost'] = 0
                fixes += 1
        
        # Duration validation and fixing
        duration = poi.get('duration_minutes')
        if duration is None:
            warnings.append(f"POI {index} ({poi_name}): Missing 'duration_minutes'")
            if fix_issues:
                poi['duration_minutes'] = 60  # Default 1 hour
                fixes += 1
        elif not isinstance(duration, (int, float)) or duration <= 0:
            warnings.append(f"POI {index} ({poi_name}): Invalid 'duration_minutes' value: {duration}")
            if fix_issues:
                poi['duration_minutes'] = 60
                fixes += 1
        
        # Opening hours consistency check
        if duration and duration > 0:
            opening_hours = poi.get('opening_hours')
            if not opening_hours or not isinstance(opening_hours, dict) or len(opening_hours) == 0:
                warnings.append(f"POI {index} ({poi_name}): Has duration but no opening hours specified")
        
        # Safety flags validation and fixing
        safety_flags = poi.get('safety_flags')
        if safety_flags is None:
            if fix_issues:
                poi['safety_flags'] = []
                fixes += 1
        elif not isinstance(safety_flags, list):
            warnings.append(f"POI {index} ({poi_name}): 'safety_flags' should be an array")
            if fix_issues:
                poi['safety_flags'] = []
                fixes += 1
        
        # Seasonality validation and fixing
        seasonality = poi.get('seasonality')
        if seasonality is None:
            if fix_issues:
                poi['seasonality'] = "year-round"
                fixes += 1
        elif not isinstance(seasonality, str):
            warnings.append(f"POI {index} ({poi_name}): 'seasonality' should be a string")
            if fix_issues:
                poi['seasonality'] = "year-round"
                fixes += 1
        
        # Region validation
        if not poi.get('region'):
            warnings.append(f"POI {index} ({poi_name}): Missing 'region' information")
        
        return warnings, fixes

    def _validate_data_consistency(self, pois: List[Dict[str, Any]]) -> List[str]:
        """Validate cross-data consistency"""
        issues = []
        
        # Check for reasonable distribution
        if len(pois) == 0:
            issues.append("Dataset is empty - no POIs found")
            return issues
        
        # Theme analysis
        all_themes = set()
        for poi in pois:
            all_themes.update(poi.get('themes', []))
        
        if len(all_themes) < 2:
            issues.append("Dataset has very limited theme diversity - consider adding more variety")
        
        # Price distribution analysis
        price_bands = [poi.get('price_band') for poi in pois if poi.get('price_band')]
        if len(set(price_bands)) < 2:
            issues.append("Dataset has limited price range diversity")
        
        # Coordinate clustering check (basic)
        coords = []
        for poi in pois:
            poi_coords = poi.get('coords', {})
            if poi_coords.get('lat') and poi_coords.get('lng'):
                coords.append((poi_coords['lat'], poi_coords['lng']))
        
        if len(coords) > 0:
            # Simple clustering check - if all points are within 0.1 degree, warn
            lats = [c[0] for c in coords]
            lngs = [c[1] for c in coords]
            lat_range = max(lats) - min(lats)
            lng_range = max(lngs) - min(lngs)
            
            if lat_range < 0.1 and lng_range < 0.1:
                issues.append("All POIs appear to be in a very small geographic area - consider broader coverage")
        
        return issues

    def _generate_validation_report(
        self, pois: List[Dict[str, Any]], issues: List[str], warnings: List[str], fixed_count: int
    ) -> str:
        """Generate a comprehensive validation report"""
        
        # Calculate dataset statistics
        total_pois = len(pois)
        pois_with_coords = len([p for p in pois if p.get('coords', {}).get('lat')])
        pois_with_hours = len([p for p in pois if p.get('opening_hours') and len(p.get('opening_hours', {})) > 0])
        pois_with_descriptions = len([p for p in pois if p.get('description')])
        
        # Cost statistics
        costs = [p.get('estimated_cost', 0) for p in pois if isinstance(p.get('estimated_cost'), (int, float))]
        avg_cost = sum(costs) / len(costs) if costs else 0
        
        # Theme statistics
        all_themes = set()
        for poi in pois:
            all_themes.update(poi.get('themes', []))
        
        # Region statistics
        regions = set()
        for poi in pois:
            if poi.get('region'):
                regions.add(poi['region'])
        
        # Build report
        report = "# 🔍 Dataset Validation Report\n\n"
        
        # Summary
        report += "## 📊 Summary\n"
        report += f"- **Total POIs:** {total_pois}\n"
        report += f"- **Critical Issues:** {len(issues)}\n"
        report += f"- **Warnings:** {len(warnings)}\n"
        report += f"- **Auto-fixed:** {fixed_count}\n\n"
        
        # Health status
        if len(issues) == 0:
            if len(warnings) == 0:
                report += "**Status:** ✅ Excellent - No issues found!\n\n"
            elif len(warnings) <= 5:
                report += "**Status:** ✅ Good - Minor warnings only\n\n"
            else:
                report += "**Status:** ⚠️ Fair - Multiple warnings to address\n\n"
        else:
            if len(issues) <= 3:
                report += "**Status:** ⚠️ Needs Attention - Some critical issues\n\n"
            else:
                report += "**Status:** ❌ Poor - Multiple critical issues\n\n"
        
        # Critical Issues
        if issues:
            report += "## ❌ Critical Issues\n"
            for issue in issues[:10]:  # Limit to first 10 for readability
                report += f"- {issue}\n"
            if len(issues) > 10:
                report += f"- ... and {len(issues) - 10} more issues\n"
            report += "\n"
        
        # Warnings
        if warnings:
            report += "## ⚠️ Warnings\n"
            for warning in warnings[:10]:  # Limit to first 10
                report += f"- {warning}\n"
            if len(warnings) > 10:
                report += f"- ... and {len(warnings) - 10} more warnings\n"
            report += "\n"
        
        # Dataset Health Metrics
        report += "## 📈 Dataset Health\n"
        report += f"- **POIs with coordinates:** {pois_with_coords}/{total_pois} ({(pois_with_coords/total_pois*100):.1f}%)\n"
        report += f"- **POIs with opening hours:** {pois_with_hours}/{total_pois} ({(pois_with_hours/total_pois*100):.1f}%)\n"
        report += f"- **POIs with descriptions:** {pois_with_descriptions}/{total_pois} ({(pois_with_descriptions/total_pois*100):.1f}%)\n"
        report += f"- **Average cost:** {avg_cost:.2f} LKR\n"
        report += f"- **Theme diversity:** {len(all_themes)} unique themes\n"
        report += f"- **Regional coverage:** {len(regions)} regions\n\n"
        
        # Recommendations
        report += "## 💡 Recommendations\n"
        
        if len(issues) > 0:
            report += "### Immediate Actions Required:\n"
            report += "1. **Fix critical issues** - Address missing required fields and invalid data\n"
            report += "2. **Validate coordinates** - Ensure all POIs have accurate location data\n"
            report += "3. **Standardize enums** - Use consistent price_band values\n\n"
        
        if len(warnings) > 0:
            report += "### Improvements Suggested:\n"
            report += "1. **Complete missing data** - Add descriptions, regions, opening hours\n"
            report += "2. **Enhance consistency** - Standardize data formats and values\n"
            report += "3. **Quality review** - Manual review of flagged items\n\n"
        
        # Data quality recommendations
        if total_pois < 50:
            report += "- **Expand dataset** - Consider adding more POIs for better coverage\n"
        
        if len(all_themes) < 5:
            report += "- **Diversify themes** - Add more theme categories for variety\n"
        
        if len(regions) < 5:
            report += "- **Broader coverage** - Include POIs from more regions\n"
        
        if pois_with_descriptions / total_pois < 0.5:
            report += "- **Add descriptions** - Enhance POI information with detailed descriptions\n"
        
        # Auto-fix summary
        if fixed_count > 0:
            report += f"\n**Auto-fixes Applied:** {fixed_count} items were automatically corrected.\n"
            report += "Re-run validation to see updated status.\n"
        
        return report