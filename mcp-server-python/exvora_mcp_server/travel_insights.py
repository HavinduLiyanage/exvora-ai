"""Travel Insights functionality for Exvora MCP Server"""

from typing import Any, Dict, List, Optional
from collections import Counter


class TravelInsights:
    def __init__(self, poi_manager):
        self.poi_manager = poi_manager

    async def get_insights(
        self,
        region: Optional[str] = None,
        season: Optional[str] = None,
        budget_range: Optional[str] = None,
        interests: Optional[List[str]] = None
    ) -> str:
        """Generate contextual travel insights and recommendations"""
        
        pois = await self.poi_manager.load_pois()
        interests = interests or []
        
        insights = "# 🏝️ Sri Lanka Travel Insights\n\n"
        
        # Regional insights
        if region:
            insights += await self._get_regional_insights(pois, region)
        
        # Seasonal insights
        if season:
            insights += self._get_seasonal_insights(season)
        
        # Budget insights
        if budget_range:
            insights += await self._get_budget_insights(pois, budget_range)
        
        # Interest-based recommendations
        if interests:
            insights += await self._get_interest_insights(pois, interests)
        
        # General recommendations
        insights += self._get_general_recommendations(pois)
        
        return insights

    async def _get_regional_insights(self, pois: List[Dict[str, Any]], region: str) -> str:
        """Generate insights for a specific region"""
        
        # Filter POIs by region
        regional_pois = [
            poi for poi in pois 
            if poi.get('region', '').lower().find(region.lower()) != -1
        ]
        
        if not regional_pois:
            return f"## 📍 {region} Region\n❗ No POIs found for this region in our dataset.\n\n"
        
        # Analyze regional characteristics
        themes = Counter()
        price_bands = Counter()
        total_cost = 0
        
        for poi in regional_pois:
            for theme in poi.get('themes', []):
                themes[theme] += 1
            
            price_band = poi.get('price_band')
            if price_band:
                price_bands[price_band] += 1
            
            total_cost += poi.get('estimated_cost', 0)
        
        avg_cost = total_cost / len(regional_pois) if regional_pois else 0
        top_themes = themes.most_common(3)
        
        insights = f"## 📍 {region} Region\n"
        insights += f"- **Available POIs:** {len(regional_pois)}\n"
        insights += f"- **Average Cost:** {avg_cost:.0f} LKR per activity\n"
        
        if top_themes:
            insights += f"- **Popular Themes:** {', '.join([f'{theme} ({count})' for theme, count in top_themes])}\n"
        
        # Price distribution
        if price_bands:
            insights += f"- **Price Distribution:** "
            price_info = []
            for band in ['low', 'medium', 'high']:
                count = price_bands.get(band, 0)
                if count > 0:
                    price_info.append(f"{count} {band}")
            insights += ', '.join(price_info) + "\n"
        
        # Top recommendations
        insights += f"\n**Top Recommendations in {region}:**\n"
        # Sort by estimated cost (ascending) and take top 3
        sorted_pois = sorted(regional_pois, key=lambda x: x.get('estimated_cost', 0))[:3]
        for i, poi in enumerate(sorted_pois, 1):
            insights += f"{i}. **{poi.get('name', 'Unknown')}** - {poi.get('estimated_cost', 0)} LKR\n"
            insights += f"   - Themes: {', '.join(poi.get('themes', []))}\n"
        
        insights += "\n"
        return insights

    def _get_seasonal_insights(self, season: str) -> str:
        """Generate seasonal travel recommendations"""
        
        insights = f"## 🌤️ {season.title()} Season Tips\n"
        
        season_lower = season.lower()
        
        if 'dry' in season_lower or 'peak' in season_lower:
            insights += "**Best Time for:**\n"
            insights += "- 🏖️ Beach destinations (West & South coast)\n"
            insights += "- 🥾 Hiking and trekking activities\n"
            insights += "- 🏛️ Cultural site visits (comfortable weather)\n"
            insights += "- 📸 Photography (clear skies)\n\n"
            
            insights += "**Recommendations:**\n"
            insights += "- Book accommodations early (peak season)\n"
            insights += "- Consider early morning starts for popular sites\n"
            insights += "- Pack sunscreen and light, breathable clothing\n"
            insights += "- Perfect for outdoor adventures and water activities\n\n"
            
        elif 'wet' in season_lower or 'monsoon' in season_lower:
            insights += "**Best Time for:**\n"
            insights += "- 🏔️ Hill country experiences (Kandy, Ella, Nuwara Eliya)\n"
            insights += "- 🏛️ Indoor cultural activities and museums\n"
            insights += "- 🍵 Tea plantation tours\n"
            insights += "- 🏖️ East coast beaches (Arugam Bay, Trincomalee)\n\n"
            
            insights += "**Recommendations:**\n"
            insights += "- Pack waterproof gear and umbrella\n"
            insights += "- Focus on covered attractions and indoor experiences\n"
            insights += "- Great for fewer crowds and lower prices\n"
            insights += "- Lush green landscapes - excellent for nature photography\n\n"
            
        else:
            insights += "**General Seasonal Advice:**\n"
            insights += "- Check local weather forecasts before traveling\n"
            insights += "- Sri Lanka has micro-climates - weather varies by region\n"
            insights += "- Shoulder seasons often offer the best balance of weather and prices\n\n"
        
        return insights

    async def _get_budget_insights(self, pois: List[Dict[str, Any]], budget_range: str) -> str:
        """Generate budget-specific recommendations"""
        
        # Filter POIs by budget range
        budget_map = {
            'budget': 'low',
            'mid-range': 'medium',
            'luxury': 'high'
        }
        
        target_price_band = budget_map.get(budget_range.lower())
        if not target_price_band:
            return f"## 💰 Budget Insights\n❗ Unknown budget range: {budget_range}\n\n"
        
        budget_pois = [poi for poi in pois if poi.get('price_band') == target_price_band]
        
        if not budget_pois:
            return f"## 💰 {budget_range.title()} Budget\n❗ No POIs found for this budget range.\n\n"
        
        # Calculate statistics
        costs = [poi.get('estimated_cost', 0) for poi in budget_pois]
        avg_cost = sum(costs) / len(costs) if costs else 0
        min_cost = min(costs) if costs else 0
        max_cost = max(costs) if costs else 0
        
        # Theme analysis
        themes = Counter()
        for poi in budget_pois:
            for theme in poi.get('themes', []):
                themes[theme] += 1
        
        insights = f"## 💰 {budget_range.title()} Budget Recommendations\n"
        insights += f"- **Available Options:** {len(budget_pois)} POIs\n"
        insights += f"- **Price Range:** {min_cost:.0f} - {max_cost:.0f} LKR\n"
        insights += f"- **Average Cost:** {avg_cost:.0f} LKR per activity\n"
        
        if budget_range.lower() == 'budget':
            insights += f"- **Daily Budget Estimate:** {avg_cost * 3:.0f} - {avg_cost * 4:.0f} LKR (3-4 activities)\n"
        elif budget_range.lower() == 'mid-range':
            insights += f"- **Daily Budget Estimate:** {avg_cost * 2:.0f} - {avg_cost * 3:.0f} LKR (2-3 activities)\n"
        else:  # luxury
            insights += f"- **Daily Budget Estimate:** {avg_cost * 2:.0f}+ LKR (2+ premium activities)\n"
        
        # Top themes for this budget
        top_themes = themes.most_common(3)
        if top_themes:
            insights += f"- **Popular Categories:** {', '.join([theme for theme, _ in top_themes])}\n"
        
        # Budget-specific tips
        insights += "\n**Budget Tips:**\n"
        if budget_range.lower() == 'budget':
            insights += "- Many temples and cultural sites have low or no entry fees\n"
            insights += "- Nature experiences often offer great value\n"
            insights += "- Consider public transport for transfers\n"
            insights += "- Local markets and street food for authentic experiences\n"
        elif budget_range.lower() == 'mid-range':
            insights += "- Good balance of quality and affordability\n"
            insights += "- Mix free attractions with paid experiences\n"
            insights += "- Consider private transport for comfort\n"
            insights += "- Restaurant dining with local specialties\n"
        else:  # luxury
            insights += "- Premium experiences and exclusive access\n"
            insights += "- Private guides and personalized tours\n"
            insights += "- High-end accommodations and dining\n"
            insights += "- Helicopter tours and luxury transport options\n"
        
        insights += "\n"
        return insights

    async def _get_interest_insights(self, pois: List[Dict[str, Any]], interests: List[str]) -> str:
        """Generate recommendations based on traveler interests"""
        
        insights = f"## 🎯 Based on Your Interests\n"
        
        for interest in interests:
            # Find POIs matching this interest
            matching_pois = []
            for poi in pois:
                # Check themes
                themes_match = any(
                    interest.lower() in theme.lower() 
                    for theme in poi.get('themes', [])
                )
                # Check tags
                tags_match = any(
                    interest.lower() in tag.lower() 
                    for tag in poi.get('tags', [])
                )
                
                if themes_match or tags_match:
                    matching_pois.append(poi)
            
            if matching_pois:
                insights += f"\n### {interest.title()}\n"
                insights += f"- **{len(matching_pois)} relevant POIs** available\n"
                
                # Top recommendations (sort by cost, take 3)
                top_pois = sorted(matching_pois, key=lambda x: x.get('estimated_cost', 0))[:3]
                insights += f"- **Top Recommendations:** {', '.join([poi.get('name', 'Unknown') for poi in top_pois])}\n"
                
                # Average cost for this interest
                costs = [poi.get('estimated_cost', 0) for poi in matching_pois]
                avg_cost = sum(costs) / len(costs) if costs else 0
                insights += f"- **Average Cost:** {avg_cost:.0f} LKR\n"
                
                # Best regions for this interest
                regions = Counter()
                for poi in matching_pois:
                    if poi.get('region'):
                        regions[poi['region']] += 1
                
                if regions:
                    top_region = regions.most_common(1)[0]
                    insights += f"- **Best Region:** {top_region[0]} ({top_region[1]} options)\n"
        
        return insights

    def _get_general_recommendations(self, pois: List[Dict[str, Any]]) -> str:
        """Generate general travel recommendations for Sri Lanka"""
        
        # Analyze dataset for general insights
        total_pois = len(pois)
        themes = Counter()
        regions = Counter()
        
        for poi in pois:
            for theme in poi.get('themes', []):
                themes[theme] += 1
            if poi.get('region'):
                regions[poi['region']] += 1
        
        top_themes = themes.most_common(3)
        top_regions = regions.most_common(3)
        
        insights = f"## 🌟 General Sri Lanka Recommendations\n\n"
        
        # Must-visit categories
        insights += f"### 🏛️ Must-Visit Categories\n"
        if top_themes:
            for theme, count in top_themes:
                insights += f"- **{theme}:** {count} destinations available\n"
        
        insights += f"\n### 🗺️ Top Regions to Explore\n"
        if top_regions:
            for region, count in top_regions:
                insights += f"- **{region}:** {count} attractions\n"
        
        # Classic recommendations
        insights += f"\n### 🎯 Classic Sri Lankan Experiences\n"
        insights += "- **Cultural Triangle:** Sigiriya, Dambulla, Polonnaruwa\n"
        insights += "- **Hill Country:** Kandy, Ella, Nuwara Eliya (tea country)\n"
        insights += "- **Southern Coast:** Galle Fort, Unawatuna, Mirissa\n"
        insights += "- **Wildlife:** Yala National Park, Udawalawe\n"
        insights += "- **Adventure:** Hiking, surfing, white-water rafting\n"
        
        insights += f"\n### 🚗 Transportation Tips\n"
        insights += "- **Trains:** Scenic routes through hill country\n"
        insights += "- **Tuk-tuks:** Perfect for short distances and local exploration\n"
        insights += "- **Private Driver:** Recommended for multi-day trips\n"
        insights += "- **Domestic Flights:** Time-saving for longer distances\n"
        
        insights += f"\n### 📅 Ideal Trip Duration\n"
        insights += "- **Weekend (2-3 days):** Focus on one region (Colombo + Kandy)\n"
        insights += "- **Week (5-7 days):** Cultural Triangle + Hill Country\n"
        insights += "- **Extended (10+ days):** Full island circuit including beaches\n"
        
        insights += f"\n### 🍛 Food & Culture\n"
        insights += "- **Must-try dishes:** Rice & curry, hoppers, kottu roti\n"
        insights += "- **Tea culture:** Ceylon tea plantation visits\n"
        insights += "- **Spice gardens:** Learn about Sri Lankan spices\n"
        insights += "- **Local markets:** Authentic cultural experiences\n"
        
        insights += f"\n### ⚠️ Travel Tips\n"
        insights += "- **Best months:** December to March (dry season)\n"
        insights += "- **Monsoons:** May-September (west/south), October-March (east/north)\n"
        insights += "- **Currency:** Sri Lankan Rupee (LKR)\n"
        insights += "- **Language:** Sinhala, Tamil, English widely spoken\n"
        insights += "- **Respect:** Dress modestly at religious sites\n"
        
        insights += f"\n**Dataset Coverage:** {total_pois} verified attractions across Sri Lanka\n"
        
        return insights