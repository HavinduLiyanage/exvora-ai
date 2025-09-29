"""Itinerary Analysis functionality for Exvora MCP Server"""

from typing import Any, Dict, List, Optional
from collections import defaultdict, Counter


class ItineraryAnalyzer:
    def __init__(self, poi_manager):
        self.poi_manager = poi_manager

    async def analyze(self, itinerary: Dict[str, Any]) -> str:
        """Analyze an itinerary for insights and metrics"""
        
        if not itinerary or not itinerary.get('days'):
            raise ValueError("Invalid itinerary format - missing 'days' field")
        
        # Load POI data for enrichment
        pois = await self.poi_manager.load_pois()
        poi_map = {poi.get('poi_id'): poi for poi in pois}
        
        # Initialize analysis structure
        analysis = {
            'total_days': len(itinerary['days']),
            'total_cost': 0,
            'total_activities': 0,
            'total_transfers': 0,
            'total_walking_minutes': 0,
            'themes': Counter(),
            'regions': Counter(),
            'price_distribution': {'low': 0, 'medium': 0, 'high': 0},
            'daily_stats': [],
            'time_distribution': defaultdict(int),
            'activity_durations': [],
            'cost_breakdown': {'activities': 0, 'estimated_transport': 0}
        }
        
        # Analyze each day
        for day in itinerary['days']:
            day_stats = await self._analyze_day(day, poi_map)
            analysis['daily_stats'].append(day_stats)
            
            # Aggregate totals
            analysis['total_cost'] += day_stats['cost']
            analysis['total_activities'] += day_stats['activities']
            analysis['total_transfers'] += day_stats['transfers']
            analysis['total_walking_minutes'] += day_stats['walking_minutes']
            
            # Aggregate themes and regions
            for theme in day_stats['themes']:
                analysis['themes'][theme] += 1
            for region in day_stats['regions']:
                analysis['regions'][region] += 1
            
            # Aggregate price distribution
            for price_band, count in day_stats['price_distribution'].items():
                analysis['price_distribution'][price_band] += count
            
            # Time distribution analysis
            for hour in day_stats['activity_hours']:
                analysis['time_distribution'][hour] += 1
            
            # Activity durations
            analysis['activity_durations'].extend(day_stats['activity_durations'])
        
        # Generate formatted report
        return self._format_analysis_report(analysis, itinerary)

    async def _analyze_day(self, day: Dict[str, Any], poi_map: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single day's itinerary"""
        
        day_stats = {
            'date': day.get('date'),
            'cost': day.get('summary', {}).get('est_cost', 0),
            'activities': 0,
            'transfers': 0,
            'walking_minutes': 0,
            'themes': set(),
            'regions': set(),
            'price_distribution': {'low': 0, 'medium': 0, 'high': 0},
            'activity_hours': [],
            'activity_durations': [],
            'start_time': None,
            'end_time': None
        }
        
        items = day.get('items', [])
        
        for item in items:
            if item.get('type') == 'transfer':
                day_stats['transfers'] += 1
                if item.get('mode') == 'WALK':
                    day_stats['walking_minutes'] += item.get('duration_minutes', 0)
            
            elif item.get('place_id'):  # Activity
                day_stats['activities'] += 1
                
                # Track start/end times
                start_time = item.get('start')
                end_time = item.get('end')
                
                if start_time:
                    if not day_stats['start_time'] or start_time < day_stats['start_time']:
                        day_stats['start_time'] = start_time
                    
                    # Extract hour for time distribution
                    try:
                        hour = int(start_time.split(':')[0])
                        day_stats['activity_hours'].append(hour)
                    except (ValueError, IndexError):
                        pass
                
                if end_time:
                    if not day_stats['end_time'] or end_time > day_stats['end_time']:
                        day_stats['end_time'] = end_time
                
                # Calculate activity duration
                if start_time and end_time:
                    try:
                        start_h, start_m = map(int, start_time.split(':'))
                        end_h, end_m = map(int, end_time.split(':'))
                        duration = (end_h * 60 + end_m) - (start_h * 60 + start_m)
                        day_stats['activity_durations'].append(duration)
                    except (ValueError, IndexError):
                        pass
                
                # Enrich with POI data
                poi = poi_map.get(item['place_id'])
                if poi:
                    # Themes
                    for theme in poi.get('themes', []):
                        day_stats['themes'].add(theme)
                    
                    # Region
                    if poi.get('region'):
                        day_stats['regions'].add(poi['region'])
                    
                    # Price distribution
                    price_band = poi.get('price_band')
                    if price_band in day_stats['price_distribution']:
                        day_stats['price_distribution'][price_band] += 1
        
        # Convert sets to lists for JSON serialization
        day_stats['themes'] = list(day_stats['themes'])
        day_stats['regions'] = list(day_stats['regions'])
        
        return day_stats

    def _format_analysis_report(self, analysis: Dict[str, Any], itinerary: Dict[str, Any]) -> str:
        """Format the analysis into a readable report"""
        
        currency = itinerary.get('currency', 'LKR')
        
        # Calculate averages
        avg_cost_per_day = analysis['total_cost'] / analysis['total_days'] if analysis['total_days'] > 0 else 0
        avg_activities_per_day = analysis['total_activities'] / analysis['total_days'] if analysis['total_days'] > 0 else 0
        
        # Top themes and regions
        top_themes = analysis['themes'].most_common(5)
        top_regions = analysis['regions'].most_common(3)
        
        # Activity duration stats
        durations = analysis['activity_durations']
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Time distribution analysis
        peak_hours = sorted(analysis['time_distribution'].items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Build report
        report = f"# 📊 Itinerary Analysis Report\n\n"
        
        # Overview section
        report += f"## 📋 Overview\n"
        report += f"- **Duration:** {analysis['total_days']} days\n"
        report += f"- **Total Cost:** {analysis['total_cost']:.2f} {currency}\n"
        report += f"- **Total Activities:** {analysis['total_activities']}\n"
        report += f"- **Total Transfers:** {analysis['total_transfers']}\n"
        report += f"- **Walking Time:** {analysis['total_walking_minutes']} minutes\n"
        report += f"- **Avg Cost/Day:** {avg_cost_per_day:.2f} {currency}\n"
        report += f"- **Avg Activities/Day:** {avg_activities_per_day:.1f}\n\n"
        
        # Theme distribution
        report += f"## 🎯 Theme Distribution\n"
        if top_themes:
            for theme, count in top_themes:
                percentage = (count / analysis['total_activities']) * 100 if analysis['total_activities'] > 0 else 0
                report += f"- **{theme}:** {count} activities ({percentage:.1f}%)\n"
        else:
            report += "No theme data available\n"
        report += "\n"
        
        # Regional coverage
        report += f"## 🗺️ Regional Coverage\n"
        if top_regions:
            for region, count in top_regions:
                percentage = (count / analysis['total_activities']) * 100 if analysis['total_activities'] > 0 else 0
                report += f"- **{region}:** {count} activities ({percentage:.1f}%)\n"
        else:
            report += "No region data available\n"
        report += "\n"
        
        # Price distribution
        report += f"## 💰 Price Distribution\n"
        total_priced = sum(analysis['price_distribution'].values())
        if total_priced > 0:
            for band, count in analysis['price_distribution'].items():
                percentage = (count / total_priced) * 100
                report += f"- **{band.title()}:** {count} activities ({percentage:.1f}%)\n"
        else:
            report += "No price data available\n"
        report += "\n"
        
        # Time analysis
        report += f"## ⏰ Activity Timing\n"
        if peak_hours:
            report += f"**Peak Activity Hours:**\n"
            for hour, count in peak_hours:
                report += f"- **{hour:02d}:00:** {count} activities\n"
        
        if avg_duration > 0:
            report += f"\n**Average Activity Duration:** {avg_duration:.0f} minutes\n"
        report += "\n"
        
        # Daily breakdown
        report += f"## 📅 Daily Breakdown\n"
        for day_stats in analysis['daily_stats']:
            themes_str = ', '.join(day_stats['themes'][:3])
            if len(day_stats['themes']) > 3:
                themes_str += f" (+{len(day_stats['themes']) - 3} more)"
            
            report += f"**{day_stats['date']}:**\n"
            report += f"- Activities: {day_stats['activities']}, Transfers: {day_stats['transfers']}\n"
            report += f"- Cost: {day_stats['cost']} {currency}\n"
            report += f"- Time: {day_stats['start_time'] or 'N/A'} - {day_stats['end_time'] or 'N/A'}\n"
            report += f"- Themes: {themes_str or 'None'}\n"
            if day_stats['walking_minutes'] > 0:
                report += f"- Walking: {day_stats['walking_minutes']} minutes\n"
            report += "\n"
        
        # Recommendations
        report += f"## 💡 Insights & Recommendations\n"
        
        # Balance analysis
        theme_diversity = len(analysis['themes'])
        if theme_diversity >= 4:
            report += "✅ Good theme diversity - well-balanced itinerary\n"
        elif theme_diversity >= 2:
            report += "⚠️ Moderate theme diversity - consider adding more variety\n"
        else:
            report += "❗ Limited theme diversity - consider broader activity types\n"
        
        # Cost analysis
        if avg_cost_per_day > 150:
            report += "💸 High daily spending - consider budget-friendly alternatives\n"
        elif avg_cost_per_day < 50:
            report += "💰 Budget-friendly itinerary - room for premium experiences\n"
        else:
            report += "💯 Well-balanced budget allocation\n"
        
        # Activity density
        if avg_activities_per_day > 4:
            report += "🏃 High activity density - ensure adequate rest time\n"
        elif avg_activities_per_day < 2:
            report += "🐌 Light activity schedule - opportunity to add more experiences\n"
        else:
            report += "⚖️ Good activity pacing\n"
        
        return report