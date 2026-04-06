"""Mock heatmap repository."""

from __future__ import annotations

import math

# 5 mock districts with centers
_MOCK_CENTERS = [
    {"code": "D3001", "lat": 37.4979, "lng": 127.0276},  # 강남역
    {"code": "D3002", "lat": 37.5563, "lng": 126.9220},  # 홍대
    {"code": "D3003", "lat": 37.5407, "lng": 127.0700},  # 건대
    {"code": "D3004", "lat": 37.5636, "lng": 126.9830},  # 명동
    {"code": "D3005", "lat": 37.5547, "lng": 126.9707},  # 서울역
]


def _generate_weight(hour: int, base: float) -> float:
    """Generate a realistic population weight based on hour."""
    # Peak at 12-13 and 18-19, low at 3-5
    peak1 = math.exp(-0.5 * ((hour - 12.5) / 2.5) ** 2)
    peak2 = math.exp(-0.5 * ((hour - 18) / 2) ** 2)
    night = 0.1 if 0 <= hour <= 5 else 0.3
    return base * (night + 0.7 * max(peak1, peak2))


class MockHeatmapRepository:
    async def get_heatmap_data(
        self, time_slot: int, quarter: str | None = None
    ) -> dict:
        points = []
        for c in _MOCK_CENTERS:
            weight = _generate_weight(time_slot, 1.0)
            # Add some jitter around center
            for dx, dy in [(0, 0), (0.002, 0.001), (-0.001, 0.002), (0.001, -0.001)]:
                points.append({
                    "lat": c["lat"] + dx,
                    "lng": c["lng"] + dy,
                    "weight": round(weight * (1.0 + dx * 100), 2),
                })
        return {
            "time_slot": time_slot,
            "quarter": quarter or "2025Q3",
            "points": points,
        }

    async def get_heatmap_all(self, quarter: str | None = None) -> dict:
        slots = {}
        for hour in range(24):
            data = await self.get_heatmap_data(hour, quarter)
            slots[str(hour)] = data["points"]
        return {
            "quarter": quarter or "2025Q3",
            "slots": slots,
        }
