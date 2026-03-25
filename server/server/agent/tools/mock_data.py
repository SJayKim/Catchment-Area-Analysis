"""Mock data for Phase 1A — 5 districts with realistic Seoul commercial data.

All data shapes match the return types of the real DB-backed tool functions.
"""

MOCK_QUARTER = "2025Q3"

# ---------------------------------------------------------------------------
# District metadata & polygons
# ---------------------------------------------------------------------------

DISTRICTS = {
    "D3001": {
        "code": "D3001",
        "name": "강남역",
        "type": "발달상권",
        "center": {"lat": 37.4979, "lng": 127.0276},
        "quarter": MOCK_QUARTER,
        "polygon": [
            [127.0240, 37.4995],
            [127.0310, 37.4995],
            [127.0310, 37.4960],
            [127.0240, 37.4960],
            [127.0240, 37.4995],
        ],
    },
    "D3002": {
        "code": "D3002",
        "name": "홍대입구",
        "type": "발달상권",
        "center": {"lat": 37.5563, "lng": 126.9237},
        "quarter": MOCK_QUARTER,
        "polygon": [
            [126.9200, 37.5585],
            [126.9275, 37.5585],
            [126.9275, 37.5540],
            [126.9200, 37.5540],
            [126.9200, 37.5585],
        ],
    },
    "D3003": {
        "code": "D3003",
        "name": "건대입구",
        "type": "발달상권",
        "center": {"lat": 37.5404, "lng": 127.0690},
        "quarter": MOCK_QUARTER,
        "polygon": [
            [127.0655, 37.5425],
            [127.0725, 37.5425],
            [127.0725, 37.5380],
            [127.0655, 37.5380],
            [127.0655, 37.5425],
        ],
    },
    "D3004": {
        "code": "D3004",
        "name": "명동",
        "type": "발달상권",
        "center": {"lat": 37.5636, "lng": 126.9860},
        "quarter": MOCK_QUARTER,
        "polygon": [
            [126.9830, 37.5655],
            [126.9890, 37.5655],
            [126.9890, 37.5615],
            [126.9830, 37.5615],
            [126.9830, 37.5655],
        ],
    },
    "D3005": {
        "code": "D3005",
        "name": "서울역",
        "type": "골목상권",
        "center": {"lat": 37.5547, "lng": 126.9706},
        "quarter": MOCK_QUARTER,
        "polygon": [
            [126.9675, 37.5568],
            [126.9738, 37.5568],
            [126.9738, 37.5525],
            [126.9675, 37.5525],
            [126.9675, 37.5568],
        ],
    },
}

# ---------------------------------------------------------------------------
# Floating population
# ---------------------------------------------------------------------------

FLOATING_POPULATION = {
    "D3001": {
        "district_code": "D3001",
        "quarter": MOCK_QUARTER,
        "daily_avg": 124350,
        "peak_hour": 18,
        "by_hour": [
            {"time_slot": 0, "population": 8200},
            {"time_slot": 1, "population": 4100},
            {"time_slot": 2, "population": 2300},
            {"time_slot": 3, "population": 1500},
            {"time_slot": 4, "population": 1200},
            {"time_slot": 5, "population": 2800},
            {"time_slot": 6, "population": 12400},
            {"time_slot": 7, "population": 28500},
            {"time_slot": 8, "population": 35200},
            {"time_slot": 9, "population": 32100},
            {"time_slot": 10, "population": 29800},
            {"time_slot": 11, "population": 38500},
            {"time_slot": 12, "population": 45200},
            {"time_slot": 13, "population": 41300},
            {"time_slot": 14, "population": 35800},
            {"time_slot": 15, "population": 33200},
            {"time_slot": 16, "population": 36100},
            {"time_slot": 17, "population": 48500},
            {"time_slot": 18, "population": 52300},
            {"time_slot": 19, "population": 45800},
            {"time_slot": 20, "population": 38200},
            {"time_slot": 21, "population": 28900},
            {"time_slot": 22, "population": 19500},
            {"time_slot": 23, "population": 12800},
        ],
        "gender": {"male_ratio": 52.3, "female_ratio": 47.7},
        "age_distribution": {
            "10대": 5.2,
            "20대": 28.5,
            "30대": 32.1,
            "40대": 18.7,
            "50대": 10.3,
            "60대 이상": 5.2,
        },
    },
    "D3002": {
        "district_code": "D3002",
        "quarter": MOCK_QUARTER,
        "daily_avg": 98700,
        "peak_hour": 20,
        "by_hour": [
            {"time_slot": 0, "population": 12500},
            {"time_slot": 1, "population": 8300},
            {"time_slot": 2, "population": 5100},
            {"time_slot": 3, "population": 2800},
            {"time_slot": 4, "population": 1500},
            {"time_slot": 5, "population": 2200},
            {"time_slot": 6, "population": 5800},
            {"time_slot": 7, "population": 10200},
            {"time_slot": 8, "population": 15600},
            {"time_slot": 9, "population": 18300},
            {"time_slot": 10, "population": 22500},
            {"time_slot": 11, "population": 28900},
            {"time_slot": 12, "population": 35200},
            {"time_slot": 13, "population": 38500},
            {"time_slot": 14, "population": 42100},
            {"time_slot": 15, "population": 45300},
            {"time_slot": 16, "population": 48200},
            {"time_slot": 17, "population": 52800},
            {"time_slot": 18, "population": 56200},
            {"time_slot": 19, "population": 58100},
            {"time_slot": 20, "population": 55800},
            {"time_slot": 21, "population": 42300},
            {"time_slot": 22, "population": 32100},
            {"time_slot": 23, "population": 18500},
        ],
        "gender": {"male_ratio": 45.8, "female_ratio": 54.2},
        "age_distribution": {
            "10대": 8.5,
            "20대": 42.3,
            "30대": 22.1,
            "40대": 14.2,
            "50대": 8.1,
            "60대 이상": 4.8,
        },
    },
    "D3003": {
        "district_code": "D3003",
        "quarter": MOCK_QUARTER,
        "daily_avg": 72500,
        "peak_hour": 19,
        "by_hour": [
            {"time_slot": 0, "population": 6800},
            {"time_slot": 1, "population": 4200},
            {"time_slot": 2, "population": 2800},
            {"time_slot": 3, "population": 1500},
            {"time_slot": 4, "population": 1200},
            {"time_slot": 5, "population": 2500},
            {"time_slot": 6, "population": 8200},
            {"time_slot": 7, "population": 15300},
            {"time_slot": 8, "population": 22100},
            {"time_slot": 9, "population": 24500},
            {"time_slot": 10, "population": 26200},
            {"time_slot": 11, "population": 32100},
            {"time_slot": 12, "population": 35800},
            {"time_slot": 13, "population": 33200},
            {"time_slot": 14, "population": 30100},
            {"time_slot": 15, "population": 28500},
            {"time_slot": 16, "population": 31200},
            {"time_slot": 17, "population": 38500},
            {"time_slot": 18, "population": 42100},
            {"time_slot": 19, "population": 43200},
            {"time_slot": 20, "population": 38500},
            {"time_slot": 21, "population": 28200},
            {"time_slot": 22, "population": 18500},
            {"time_slot": 23, "population": 10800},
        ],
        "gender": {"male_ratio": 48.5, "female_ratio": 51.5},
        "age_distribution": {
            "10대": 7.8,
            "20대": 38.2,
            "30대": 25.5,
            "40대": 15.3,
            "50대": 8.7,
            "60대 이상": 4.5,
        },
    },
    "D3004": {
        "district_code": "D3004",
        "quarter": MOCK_QUARTER,
        "daily_avg": 156200,
        "peak_hour": 14,
        "by_hour": [
            {"time_slot": 0, "population": 5200},
            {"time_slot": 1, "population": 2800},
            {"time_slot": 2, "population": 1500},
            {"time_slot": 3, "population": 800},
            {"time_slot": 4, "population": 600},
            {"time_slot": 5, "population": 3200},
            {"time_slot": 6, "population": 15800},
            {"time_slot": 7, "population": 32500},
            {"time_slot": 8, "population": 45200},
            {"time_slot": 9, "population": 52800},
            {"time_slot": 10, "population": 62300},
            {"time_slot": 11, "population": 72500},
            {"time_slot": 12, "population": 78200},
            {"time_slot": 13, "population": 75800},
            {"time_slot": 14, "population": 80100},
            {"time_slot": 15, "population": 72500},
            {"time_slot": 16, "population": 65200},
            {"time_slot": 17, "population": 58500},
            {"time_slot": 18, "population": 48200},
            {"time_slot": 19, "population": 35800},
            {"time_slot": 20, "population": 25200},
            {"time_slot": 21, "population": 18500},
            {"time_slot": 22, "population": 12800},
            {"time_slot": 23, "population": 8200},
        ],
        "gender": {"male_ratio": 44.2, "female_ratio": 55.8},
        "age_distribution": {
            "10대": 6.2,
            "20대": 32.5,
            "30대": 24.8,
            "40대": 18.5,
            "50대": 11.2,
            "60대 이상": 6.8,
        },
    },
    "D3005": {
        "district_code": "D3005",
        "quarter": MOCK_QUARTER,
        "daily_avg": 45800,
        "peak_hour": 8,
        "by_hour": [
            {"time_slot": 0, "population": 3200},
            {"time_slot": 1, "population": 2100},
            {"time_slot": 2, "population": 1500},
            {"time_slot": 3, "population": 1200},
            {"time_slot": 4, "population": 2500},
            {"time_slot": 5, "population": 5800},
            {"time_slot": 6, "population": 12500},
            {"time_slot": 7, "population": 22300},
            {"time_slot": 8, "population": 28500},
            {"time_slot": 9, "population": 25200},
            {"time_slot": 10, "population": 18500},
            {"time_slot": 11, "population": 15200},
            {"time_slot": 12, "population": 18800},
            {"time_slot": 13, "population": 16500},
            {"time_slot": 14, "population": 14200},
            {"time_slot": 15, "population": 13500},
            {"time_slot": 16, "population": 15800},
            {"time_slot": 17, "population": 22500},
            {"time_slot": 18, "population": 25200},
            {"time_slot": 19, "population": 18500},
            {"time_slot": 20, "population": 12800},
            {"time_slot": 21, "population": 8500},
            {"time_slot": 22, "population": 5800},
            {"time_slot": 23, "population": 4200},
        ],
        "gender": {"male_ratio": 56.2, "female_ratio": 43.8},
        "age_distribution": {
            "10대": 3.5,
            "20대": 18.2,
            "30대": 22.5,
            "40대": 25.8,
            "50대": 18.5,
            "60대 이상": 11.5,
        },
    },
}

# ---------------------------------------------------------------------------
# Estimated sales
# ---------------------------------------------------------------------------

ESTIMATED_SALES = {
    "D3001": {
        "district_code": "D3001",
        "quarter": MOCK_QUARTER,
        "total_monthly_sales": 8_520_000_000,
        "total_sales_count": 285_000,
        "weekday_sales": 5_680_000_000,
        "weekend_sales": 2_840_000_000,
        "gender_sales": {"male": 4_520_000_000, "female": 4_000_000_000},
        "age_sales": {
            "10대": 342_000_000,
            "20대": 2_130_000_000,
            "30대": 2_820_000_000,
            "40대": 1_705_000_000,
            "50대": 980_000_000,
            "60대 이상": 543_000_000,
        },
        "time_sales": {
            "00~06시": 425_000_000,
            "06~11시": 1_280_000_000,
            "11~14시": 2_130_000_000,
            "14~17시": 1_705_000_000,
            "17~21시": 2_340_000_000,
            "21~24시": 640_000_000,
        },
        "trend": "growing",
        "quarterly_sales": [
            {"quarter": "2024Q4", "monthly_sales": 7_800_000_000},
            {"quarter": "2025Q1", "monthly_sales": 7_950_000_000},
            {"quarter": "2025Q2", "monthly_sales": 8_200_000_000},
            {"quarter": "2025Q3", "monthly_sales": 8_520_000_000},
        ],
    },
    "D3002": {
        "district_code": "D3002",
        "quarter": MOCK_QUARTER,
        "total_monthly_sales": 6_350_000_000,
        "total_sales_count": 215_000,
        "weekday_sales": 3_175_000_000,
        "weekend_sales": 3_175_000_000,
        "gender_sales": {"male": 2_855_000_000, "female": 3_495_000_000},
        "age_sales": {
            "10대": 510_000_000,
            "20대": 2_730_000_000,
            "30대": 1_525_000_000,
            "40대": 890_000_000,
            "50대": 445_000_000,
            "60대 이상": 250_000_000,
        },
        "time_sales": {
            "00~06시": 635_000_000,
            "06~11시": 508_000_000,
            "11~14시": 1_270_000_000,
            "14~17시": 1_525_000_000,
            "17~21시": 1_905_000_000,
            "21~24시": 507_000_000,
        },
        "trend": "stable",
        "quarterly_sales": [
            {"quarter": "2024Q4", "monthly_sales": 6_200_000_000},
            {"quarter": "2025Q1", "monthly_sales": 6_280_000_000},
            {"quarter": "2025Q2", "monthly_sales": 6_320_000_000},
            {"quarter": "2025Q3", "monthly_sales": 6_350_000_000},
        ],
    },
    "D3003": {
        "district_code": "D3003",
        "quarter": MOCK_QUARTER,
        "total_monthly_sales": 4_280_000_000,
        "total_sales_count": 158_000,
        "weekday_sales": 2_355_000_000,
        "weekend_sales": 1_925_000_000,
        "gender_sales": {"male": 2_050_000_000, "female": 2_230_000_000},
        "age_sales": {
            "10대": 340_000_000,
            "20대": 1_670_000_000,
            "30대": 1_070_000_000,
            "40대": 640_000_000,
            "50대": 345_000_000,
            "60대 이상": 215_000_000,
        },
        "time_sales": {
            "00~06시": 342_000_000,
            "06~11시": 430_000_000,
            "11~14시": 1_070_000_000,
            "14~17시": 855_000_000,
            "17~21시": 1_285_000_000,
            "21~24시": 298_000_000,
        },
        "trend": "growing",
        "quarterly_sales": [
            {"quarter": "2024Q4", "monthly_sales": 3_800_000_000},
            {"quarter": "2025Q1", "monthly_sales": 3_950_000_000},
            {"quarter": "2025Q2", "monthly_sales": 4_100_000_000},
            {"quarter": "2025Q3", "monthly_sales": 4_280_000_000},
        ],
    },
    "D3004": {
        "district_code": "D3004",
        "quarter": MOCK_QUARTER,
        "total_monthly_sales": 12_500_000_000,
        "total_sales_count": 380_000,
        "weekday_sales": 6_875_000_000,
        "weekend_sales": 5_625_000_000,
        "gender_sales": {"male": 5_250_000_000, "female": 7_250_000_000},
        "age_sales": {
            "10대": 625_000_000,
            "20대": 3_375_000_000,
            "30대": 3_125_000_000,
            "40대": 2_625_000_000,
            "50대": 1_625_000_000,
            "60대 이상": 1_125_000_000,
        },
        "time_sales": {
            "00~06시": 375_000_000,
            "06~11시": 1_875_000_000,
            "11~14시": 3_750_000_000,
            "14~17시": 3_125_000_000,
            "17~21시": 2_625_000_000,
            "21~24시": 750_000_000,
        },
        "trend": "declining",
        "quarterly_sales": [
            {"quarter": "2024Q4", "monthly_sales": 14_200_000_000},
            {"quarter": "2025Q1", "monthly_sales": 13_500_000_000},
            {"quarter": "2025Q2", "monthly_sales": 13_000_000_000},
            {"quarter": "2025Q3", "monthly_sales": 12_500_000_000},
        ],
    },
    "D3005": {
        "district_code": "D3005",
        "quarter": MOCK_QUARTER,
        "total_monthly_sales": 2_150_000_000,
        "total_sales_count": 82_000,
        "weekday_sales": 1_505_000_000,
        "weekend_sales": 645_000_000,
        "gender_sales": {"male": 1_250_000_000, "female": 900_000_000},
        "age_sales": {
            "10대": 86_000_000,
            "20대": 365_000_000,
            "30대": 475_000_000,
            "40대": 560_000_000,
            "50대": 410_000_000,
            "60대 이상": 254_000_000,
        },
        "time_sales": {
            "00~06시": 108_000_000,
            "06~11시": 430_000_000,
            "11~14시": 538_000_000,
            "14~17시": 430_000_000,
            "17~21시": 475_000_000,
            "21~24시": 169_000_000,
        },
        "trend": "stable",
        "quarterly_sales": [
            {"quarter": "2024Q4", "monthly_sales": 2_100_000_000},
            {"quarter": "2025Q1", "monthly_sales": 2_120_000_000},
            {"quarter": "2025Q2", "monthly_sales": 2_130_000_000},
            {"quarter": "2025Q3", "monthly_sales": 2_150_000_000},
        ],
    },
}

# ---------------------------------------------------------------------------
# Store info
# ---------------------------------------------------------------------------

STORE_INFO = {
    "D3001": {
        "district_code": "D3001",
        "quarter": MOCK_QUARTER,
        "total_stores": 1_852,
        "open_count": 125,
        "close_count": 98,
        "close_rate": 5.3,
        "franchise_count": 412,
        "top_categories": [
            {"category_code": "CS100", "category_name": "한식", "store_count": 245, "open_count": 18, "close_count": 12},
            {"category_code": "CS200", "category_name": "커피/음료", "store_count": 198, "open_count": 22, "close_count": 15},
            {"category_code": "CS300", "category_name": "의류", "store_count": 165, "open_count": 8, "close_count": 14},
            {"category_code": "CS400", "category_name": "일식/중식", "store_count": 132, "open_count": 12, "close_count": 8},
            {"category_code": "CS500", "category_name": "미용/뷰티", "store_count": 118, "open_count": 10, "close_count": 6},
        ],
    },
    "D3002": {
        "district_code": "D3002",
        "quarter": MOCK_QUARTER,
        "total_stores": 1_425,
        "open_count": 142,
        "close_count": 118,
        "close_rate": 8.3,
        "franchise_count": 285,
        "top_categories": [
            {"category_code": "CS200", "category_name": "커피/음료", "store_count": 232, "open_count": 28, "close_count": 22},
            {"category_code": "CS600", "category_name": "주점", "store_count": 185, "open_count": 15, "close_count": 18},
            {"category_code": "CS100", "category_name": "한식", "store_count": 168, "open_count": 12, "close_count": 14},
            {"category_code": "CS300", "category_name": "의류", "store_count": 145, "open_count": 18, "close_count": 20},
            {"category_code": "CS700", "category_name": "패스트푸드", "store_count": 95, "open_count": 8, "close_count": 5},
        ],
    },
    "D3003": {
        "district_code": "D3003",
        "quarter": MOCK_QUARTER,
        "total_stores": 985,
        "open_count": 88,
        "close_count": 72,
        "close_rate": 7.3,
        "franchise_count": 215,
        "top_categories": [
            {"category_code": "CS200", "category_name": "커피/음료", "store_count": 165, "open_count": 18, "close_count": 12},
            {"category_code": "CS100", "category_name": "한식", "store_count": 142, "open_count": 10, "close_count": 8},
            {"category_code": "CS600", "category_name": "주점", "store_count": 112, "open_count": 8, "close_count": 12},
            {"category_code": "CS500", "category_name": "미용/뷰티", "store_count": 85, "open_count": 6, "close_count": 4},
            {"category_code": "CS800", "category_name": "편의점/슈퍼", "store_count": 72, "open_count": 5, "close_count": 3},
        ],
    },
    "D3004": {
        "district_code": "D3004",
        "quarter": MOCK_QUARTER,
        "total_stores": 2_450,
        "open_count": 85,
        "close_count": 165,
        "close_rate": 6.7,
        "franchise_count": 580,
        "top_categories": [
            {"category_code": "CS300", "category_name": "의류", "store_count": 425, "open_count": 10, "close_count": 35},
            {"category_code": "CS900", "category_name": "화장품", "store_count": 285, "open_count": 8, "close_count": 28},
            {"category_code": "CS200", "category_name": "커피/음료", "store_count": 220, "open_count": 12, "close_count": 18},
            {"category_code": "CS100", "category_name": "한식", "store_count": 195, "open_count": 8, "close_count": 12},
            {"category_code": "CS1000", "category_name": "잡화/액세서리", "store_count": 165, "open_count": 5, "close_count": 22},
        ],
    },
    "D3005": {
        "district_code": "D3005",
        "quarter": MOCK_QUARTER,
        "total_stores": 520,
        "open_count": 32,
        "close_count": 28,
        "close_rate": 5.4,
        "franchise_count": 125,
        "top_categories": [
            {"category_code": "CS100", "category_name": "한식", "store_count": 95, "open_count": 5, "close_count": 4},
            {"category_code": "CS200", "category_name": "커피/음료", "store_count": 68, "open_count": 6, "close_count": 3},
            {"category_code": "CS800", "category_name": "편의점/슈퍼", "store_count": 52, "open_count": 3, "close_count": 2},
            {"category_code": "CS400", "category_name": "일식/중식", "store_count": 45, "open_count": 4, "close_count": 3},
            {"category_code": "CS500", "category_name": "미용/뷰티", "store_count": 38, "open_count": 2, "close_count": 2},
        ],
    },
}

# ---------------------------------------------------------------------------
# Population info (resident + worker)
# ---------------------------------------------------------------------------

POPULATION_INFO = {
    "D3001": {
        "district_code": "D3001",
        "quarter": MOCK_QUARTER,
        "resident": {
            "total": 32_500,
            "age_distribution": {"10대": 2800, "20대": 8500, "30대": 9200, "40대": 6500, "50대": 3800, "60대 이상": 1700},
            "gender": {"male": 15_600, "female": 16_900, "male_ratio": 48.0, "female_ratio": 52.0},
        },
        "worker": {
            "total": 185_000,
            "age_distribution": {"10대": 1200, "20대": 42_000, "30대": 62_000, "40대": 45_000, "50대": 25_000, "60대 이상": 9800},
            "gender": {"male": 98_000, "female": 87_000, "male_ratio": 53.0, "female_ratio": 47.0},
        },
    },
    "D3002": {
        "district_code": "D3002",
        "quarter": MOCK_QUARTER,
        "resident": {
            "total": 45_200,
            "age_distribution": {"10대": 5200, "20대": 15_800, "30대": 10_500, "40대": 7200, "50대": 4500, "60대 이상": 2000},
            "gender": {"male": 21_500, "female": 23_700, "male_ratio": 47.6, "female_ratio": 52.4},
        },
        "worker": {
            "total": 68_000,
            "age_distribution": {"10대": 2500, "20대": 25_000, "30대": 18_500, "40대": 12_000, "50대": 6800, "60대 이상": 3200},
            "gender": {"male": 31_000, "female": 37_000, "male_ratio": 45.6, "female_ratio": 54.4},
        },
    },
    "D3003": {
        "district_code": "D3003",
        "quarter": MOCK_QUARTER,
        "resident": {
            "total": 38_500,
            "age_distribution": {"10대": 4200, "20대": 12_500, "30대": 8800, "40대": 6500, "50대": 4200, "60대 이상": 2300},
            "gender": {"male": 18_800, "female": 19_700, "male_ratio": 48.8, "female_ratio": 51.2},
        },
        "worker": {
            "total": 52_000,
            "age_distribution": {"10대": 1800, "20대": 18_200, "30대": 14_500, "40대": 9800, "50대": 5200, "60대 이상": 2500},
            "gender": {"male": 25_000, "female": 27_000, "male_ratio": 48.1, "female_ratio": 51.9},
        },
    },
    "D3004": {
        "district_code": "D3004",
        "quarter": MOCK_QUARTER,
        "resident": {
            "total": 18_200,
            "age_distribution": {"10대": 1200, "20대": 3800, "30대": 4200, "40대": 3800, "50대": 2800, "60대 이상": 2400},
            "gender": {"male": 8500, "female": 9700, "male_ratio": 46.7, "female_ratio": 53.3},
        },
        "worker": {
            "total": 225_000,
            "age_distribution": {"10대": 2500, "20대": 52_000, "30대": 68_000, "40대": 55_000, "50대": 32_000, "60대 이상": 15_500},
            "gender": {"male": 105_000, "female": 120_000, "male_ratio": 46.7, "female_ratio": 53.3},
        },
    },
    "D3005": {
        "district_code": "D3005",
        "quarter": MOCK_QUARTER,
        "resident": {
            "total": 12_500,
            "age_distribution": {"10대": 800, "20대": 2200, "30대": 2800, "40대": 3200, "50대": 2100, "60대 이상": 1400},
            "gender": {"male": 6500, "female": 6000, "male_ratio": 52.0, "female_ratio": 48.0},
        },
        "worker": {
            "total": 95_000,
            "age_distribution": {"10대": 1200, "20대": 18_000, "30대": 25_000, "40대": 28_000, "50대": 15_000, "60대 이상": 7800},
            "gender": {"male": 52_000, "female": 43_000, "male_ratio": 54.7, "female_ratio": 45.3},
        },
    },
}

# ---------------------------------------------------------------------------
# Store history / risk
# ---------------------------------------------------------------------------

STORE_HISTORY = {
    "D3001": {
        "district_code": "D3001",
        "stability": {
            "score": 72,
            "grade": "양호",
            "trend": {"direction": "slightly_decreasing", "adjustment": 5, "detail": "폐업이 소폭 감소 추세"},
            "quarters_analyzed": 4,
        },
        "survival_by_category": [
            {"category": "한식", "avg_months": 38.5, "sample_count": 85},
            {"category": "커피/음료", "avg_months": 28.2, "sample_count": 62},
            {"category": "의류", "avg_months": 22.8, "sample_count": 48},
            {"category": "일식/중식", "avg_months": 32.1, "sample_count": 35},
            {"category": "미용/뷰티", "avg_months": 42.5, "sample_count": 28},
        ],
        "risk_categories": [
            {"category": "의류", "close_rate": 8.5, "warning": "폐업률 높음"},
            {"category": "커피/음료", "close_rate": 7.6, "warning": "폐업률 높음"},
        ],
        "quarterly_trend": [
            {"quarter": "2024Q4", "store_count": 1820, "open": 105, "close": 95},
            {"quarter": "2025Q1", "store_count": 1835, "open": 115, "close": 100},
            {"quarter": "2025Q2", "store_count": 1842, "open": 120, "close": 102},
            {"quarter": "2025Q3", "store_count": 1852, "open": 125, "close": 98},
        ],
    },
    "D3002": {
        "district_code": "D3002",
        "stability": {
            "score": 52,
            "grade": "주의",
            "trend": {"direction": "slightly_increasing", "adjustment": -7, "detail": "폐업이 소폭 증가 추세"},
            "quarters_analyzed": 4,
        },
        "survival_by_category": [
            {"category": "한식", "avg_months": 32.5, "sample_count": 72},
            {"category": "커피/음료", "avg_months": 18.5, "sample_count": 95},
            {"category": "주점", "avg_months": 14.2, "sample_count": 68},
            {"category": "의류", "avg_months": 16.8, "sample_count": 55},
            {"category": "패스트푸드", "avg_months": 25.5, "sample_count": 22},
        ],
        "risk_categories": [
            {"category": "주점", "close_rate": 9.7, "warning": "폐업률 높음"},
            {"category": "의류", "close_rate": 13.8, "warning": "폐업률 높음"},
            {"category": "커피/음료", "close_rate": 9.5, "warning": "폐업률 높음"},
        ],
        "quarterly_trend": [
            {"quarter": "2024Q4", "store_count": 1380, "open": 128, "close": 105},
            {"quarter": "2025Q1", "store_count": 1395, "open": 135, "close": 110},
            {"quarter": "2025Q2", "store_count": 1410, "open": 138, "close": 115},
            {"quarter": "2025Q3", "store_count": 1425, "open": 142, "close": 118},
        ],
    },
    "D3003": {
        "district_code": "D3003",
        "stability": {
            "score": 65,
            "grade": "양호",
            "trend": {"direction": "stable", "adjustment": 0, "detail": "폐업 추세 보합"},
            "quarters_analyzed": 4,
        },
        "survival_by_category": [
            {"category": "한식", "avg_months": 35.2, "sample_count": 58},
            {"category": "커피/음료", "avg_months": 22.5, "sample_count": 52},
            {"category": "주점", "avg_months": 16.8, "sample_count": 42},
            {"category": "미용/뷰티", "avg_months": 38.2, "sample_count": 25},
            {"category": "편의점/슈퍼", "avg_months": 52.5, "sample_count": 18},
        ],
        "risk_categories": [
            {"category": "주점", "close_rate": 10.7, "warning": "폐업률 높음"},
        ],
        "quarterly_trend": [
            {"quarter": "2024Q4", "store_count": 960, "open": 82, "close": 70},
            {"quarter": "2025Q1", "store_count": 968, "open": 85, "close": 72},
            {"quarter": "2025Q2", "store_count": 975, "open": 86, "close": 71},
            {"quarter": "2025Q3", "store_count": 985, "open": 88, "close": 72},
        ],
    },
    "D3004": {
        "district_code": "D3004",
        "stability": {
            "score": 38,
            "grade": "위험",
            "trend": {"direction": "increasing", "adjustment": -15, "detail": "폐업이 분기당 18% 증가 추세"},
            "quarters_analyzed": 4,
        },
        "survival_by_category": [
            {"category": "한식", "avg_months": 28.5, "sample_count": 82},
            {"category": "커피/음료", "avg_months": 20.2, "sample_count": 65},
            {"category": "의류", "avg_months": 12.5, "sample_count": 120},
            {"category": "화장품", "avg_months": 15.8, "sample_count": 85},
            {"category": "잡화/액세서리", "avg_months": 10.2, "sample_count": 55},
        ],
        "risk_categories": [
            {"category": "잡화/액세서리", "close_rate": 13.3, "warning": "폐업률 높음"},
            {"category": "화장품", "close_rate": 9.8, "warning": "폐업률 높음"},
            {"category": "의류", "close_rate": 8.2, "warning": "폐업률 높음"},
            {"category": "커피/음료", "close_rate": 8.2, "warning": "폐업률 높음"},
        ],
        "quarterly_trend": [
            {"quarter": "2024Q4", "store_count": 2520, "open": 110, "close": 135},
            {"quarter": "2025Q1", "store_count": 2490, "open": 95, "close": 145},
            {"quarter": "2025Q2", "store_count": 2470, "open": 90, "close": 155},
            {"quarter": "2025Q3", "store_count": 2450, "open": 85, "close": 165},
        ],
    },
    "D3005": {
        "district_code": "D3005",
        "stability": {
            "score": 78,
            "grade": "양호",
            "trend": {"direction": "slightly_decreasing", "adjustment": 5, "detail": "폐업이 소폭 감소 추세"},
            "quarters_analyzed": 4,
        },
        "survival_by_category": [
            {"category": "한식", "avg_months": 42.5, "sample_count": 35},
            {"category": "커피/음료", "avg_months": 32.8, "sample_count": 22},
            {"category": "편의점/슈퍼", "avg_months": 58.2, "sample_count": 15},
            {"category": "일식/중식", "avg_months": 35.5, "sample_count": 12},
            {"category": "미용/뷰티", "avg_months": 45.2, "sample_count": 10},
        ],
        "risk_categories": [],
        "quarterly_trend": [
            {"quarter": "2024Q4", "store_count": 510, "open": 28, "close": 32},
            {"quarter": "2025Q1", "store_count": 512, "open": 30, "close": 30},
            {"quarter": "2025Q2", "store_count": 515, "open": 31, "close": 29},
            {"quarter": "2025Q3", "store_count": 520, "open": 32, "close": 28},
        ],
    },
}

# ---------------------------------------------------------------------------
# Compare districts helper
# ---------------------------------------------------------------------------


def get_compare_data(district_codes: list[str]) -> dict:
    """Build comparison result from mock data."""
    results = {}
    for code in district_codes:
        fp = FLOATING_POPULATION.get(code)
        si = STORE_INFO.get(code)
        es = ESTIMATED_SALES.get(code)
        d = DISTRICTS.get(code)

        if not d:
            results[code] = {"district_code": code, "error": "데이터 없음"}
            continue

        # Find main age group
        main_age = "-"
        if fp:
            age_dist = fp["age_distribution"]
            main_age = max(age_dist, key=age_dist.get)

        results[code] = {
            "district_code": code,
            "district_name": d["name"],
            "floating_pop": fp["daily_avg"] if fp else 0,
            "main_age": main_age,
            "store_count": si["total_stores"] if si else 0,
            "close_rate": si["close_rate"] if si else 0.0,
            "monthly_sales": es["total_monthly_sales"] if es else 0,
            "status": es["trend"] if es else "stable",
            "quarter": MOCK_QUARTER,
        }

    return {"districts": results, "district_codes": district_codes}


# ---------------------------------------------------------------------------
# Recommend business helper
# ---------------------------------------------------------------------------

MOCK_RECOMMENDATIONS = {
    "D3001": {
        "district_code": "D3001",
        "quarter": MOCK_QUARTER,
        "recommendations": [
            {
                "rank": 1,
                "category_name": "미용/뷰티",
                "category_code": "CS500",
                "score": 100.0,
                "per_store_sales": 5_850_000,
                "store_count": 118,
                "close_rate": 5.1,
                "age_match": 72.5,
                "monthly_sales": 690_300_000,
                "reasons": [
                    "점포당 월매출 585만원",
                    "타겟 고객 매칭률 73%",
                    "경쟁 점포 118개 (밀집도 6.4%)",
                    "폐업률 낮음 (5.1%)",
                ],
                "startup_cost": 5000,
            },
            {
                "rank": 2,
                "category_name": "일식/중식",
                "category_code": "CS400",
                "score": 85.2,
                "per_store_sales": 7_200_000,
                "store_count": 132,
                "close_rate": 6.1,
                "age_match": 65.3,
                "monthly_sales": 950_400_000,
                "reasons": [
                    "점포당 월매출 720만원",
                    "타겟 고객 매칭률 65%",
                    "경쟁 점포 132개 (밀집도 7.1%)",
                ],
                "startup_cost": 8000,
            },
            {
                "rank": 3,
                "category_name": "한식",
                "category_code": "CS100",
                "score": 78.5,
                "per_store_sales": 6_500_000,
                "store_count": 245,
                "close_rate": 4.9,
                "age_match": 68.2,
                "monthly_sales": 1_592_500_000,
                "reasons": [
                    "점포당 월매출 650만원",
                    "타겟 고객 매칭률 68%",
                    "경쟁 점포 245개 (밀집도 13.2%)",
                    "폐업률 낮음 (4.9%)",
                ],
                "startup_cost": 7000,
            },
            {
                "rank": 4,
                "category_name": "패스트푸드",
                "category_code": "CS700",
                "score": 65.8,
                "per_store_sales": 8_500_000,
                "store_count": 52,
                "close_rate": 3.8,
                "age_match": 58.5,
                "monthly_sales": 442_000_000,
                "reasons": [
                    "점포당 월매출 850만원",
                    "타겟 고객 매칭률 59%",
                    "경쟁 점포 52개 (밀집도 2.8%)",
                    "폐업률 낮음 (3.8%)",
                ],
                "startup_cost": 15000,
            },
            {
                "rank": 5,
                "category_name": "커피/음료",
                "category_code": "CS200",
                "score": 55.2,
                "per_store_sales": 4_200_000,
                "store_count": 198,
                "close_rate": 7.6,
                "age_match": 75.8,
                "monthly_sales": 831_600_000,
                "reasons": [
                    "점포당 월매출 420만원",
                    "타겟 고객 매칭률 76%",
                    "경쟁 점포 198개 (밀집도 10.7%)",
                    "폐업률 주의 (7.6%)",
                ],
                "startup_cost": 6000,
            },
        ],
        "total_categories_analyzed": 18,
    },
    "D3002": {
        "district_code": "D3002",
        "quarter": MOCK_QUARTER,
        "recommendations": [
            {
                "rank": 1,
                "category_name": "패스트푸드",
                "category_code": "CS700",
                "score": 100.0,
                "per_store_sales": 6_800_000,
                "store_count": 95,
                "close_rate": 5.3,
                "age_match": 82.5,
                "monthly_sales": 646_000_000,
                "reasons": [
                    "점포당 월매출 680만원",
                    "타겟 고객 매칭률 83%",
                    "경쟁 점포 95개 (밀집도 6.7%)",
                ],
                "startup_cost": 15000,
            },
            {
                "rank": 2,
                "category_name": "미용/뷰티",
                "category_code": "CS500",
                "score": 82.3,
                "per_store_sales": 4_850_000,
                "store_count": 78,
                "close_rate": 5.1,
                "age_match": 75.2,
                "monthly_sales": 378_300_000,
                "reasons": [
                    "점포당 월매출 485만원",
                    "타겟 고객 매칭률 75%",
                    "경쟁 점포 78개 (밀집도 5.5%)",
                    "폐업률 낮음 (5.1%)",
                ],
                "startup_cost": 5000,
            },
            {
                "rank": 3,
                "category_name": "한식",
                "category_code": "CS100",
                "score": 72.1,
                "per_store_sales": 5_200_000,
                "store_count": 168,
                "close_rate": 8.3,
                "age_match": 62.5,
                "monthly_sales": 873_600_000,
                "reasons": [
                    "점포당 월매출 520만원",
                    "타겟 고객 매칭률 63%",
                    "경쟁 점포 168개 (밀집도 11.8%)",
                    "폐업률 주의 (8.3%)",
                ],
                "startup_cost": 7000,
            },
            {
                "rank": 4,
                "category_name": "디저트/베이커리",
                "category_code": "CS1100",
                "score": 68.5,
                "per_store_sales": 3_800_000,
                "store_count": 65,
                "close_rate": 6.2,
                "age_match": 78.5,
                "monthly_sales": 247_000_000,
                "reasons": [
                    "점포당 월매출 380만원",
                    "타겟 고객 매칭률 79%",
                    "경쟁 점포 65개 (밀집도 4.6%)",
                ],
                "startup_cost": 5500,
            },
            {
                "rank": 5,
                "category_name": "커피/음료",
                "category_code": "CS200",
                "score": 45.8,
                "per_store_sales": 3_500_000,
                "store_count": 232,
                "close_rate": 9.5,
                "age_match": 80.2,
                "monthly_sales": 812_000_000,
                "reasons": [
                    "점포당 월매출 350만원",
                    "타겟 고객 매칭률 80%",
                    "경쟁 점포 232개 (밀집도 16.3%)",
                    "폐업률 주의 (9.5%)",
                ],
                "startup_cost": 6000,
            },
        ],
        "total_categories_analyzed": 22,
    },
}

# Default recommendations for districts without specific data
_DEFAULT_RECOMMENDATIONS = {
    "quarter": MOCK_QUARTER,
    "recommendations": [
        {
            "rank": 1,
            "category_name": "한식",
            "category_code": "CS100",
            "score": 100.0,
            "per_store_sales": 5_500_000,
            "store_count": 120,
            "close_rate": 5.5,
            "age_match": 68.0,
            "monthly_sales": 660_000_000,
            "reasons": ["점포당 월매출 550만원", "타겟 고객 매칭률 68%", "안정적인 폐업률"],
            "startup_cost": 7000,
        },
        {
            "rank": 2,
            "category_name": "커피/음료",
            "category_code": "CS200",
            "score": 82.5,
            "per_store_sales": 4_000_000,
            "store_count": 85,
            "close_rate": 7.2,
            "age_match": 72.5,
            "monthly_sales": 340_000_000,
            "reasons": ["점포당 월매출 400만원", "타겟 고객 매칭률 73%"],
            "startup_cost": 6000,
        },
        {
            "rank": 3,
            "category_name": "미용/뷰티",
            "category_code": "CS500",
            "score": 75.2,
            "per_store_sales": 4_800_000,
            "store_count": 55,
            "close_rate": 4.8,
            "age_match": 65.0,
            "monthly_sales": 264_000_000,
            "reasons": ["점포당 월매출 480만원", "폐업률 낮음 (4.8%)", "타겟 고객 매칭률 65%"],
            "startup_cost": 5000,
        },
        {
            "rank": 4,
            "category_name": "편의점/슈퍼",
            "category_code": "CS800",
            "score": 68.0,
            "per_store_sales": 6_200_000,
            "store_count": 45,
            "close_rate": 3.5,
            "age_match": 55.0,
            "monthly_sales": 279_000_000,
            "reasons": ["점포당 월매출 620만원", "폐업률 낮음 (3.5%)"],
            "startup_cost": 12000,
        },
        {
            "rank": 5,
            "category_name": "일식/중식",
            "category_code": "CS400",
            "score": 55.8,
            "per_store_sales": 5_800_000,
            "store_count": 38,
            "close_rate": 6.5,
            "age_match": 58.0,
            "monthly_sales": 220_400_000,
            "reasons": ["점포당 월매출 580만원", "타겟 고객 매칭률 58%"],
            "startup_cost": 8000,
        },
    ],
    "total_categories_analyzed": 15,
}


def get_recommendations(district_code: str, budget: int | None = None, preference: str | None = None) -> dict:
    """Return mock recommendations for a district."""
    if district_code in MOCK_RECOMMENDATIONS:
        result = {**MOCK_RECOMMENDATIONS[district_code]}
    else:
        result = {"district_code": district_code, **_DEFAULT_RECOMMENDATIONS}

    # Apply budget filter
    if budget:
        filtered = [r for r in result["recommendations"] if r.get("startup_cost", 0) <= budget]
        if filtered:
            for i, rec in enumerate(filtered, 1):
                rec["rank"] = i
            result["recommendations"] = filtered

    return result


# ---------------------------------------------------------------------------
# GeoJSON feature collection builder
# ---------------------------------------------------------------------------


def get_mock_geojson() -> dict:
    """Build GeoJSON FeatureCollection from mock districts."""
    features = []
    for code, d in DISTRICTS.items():
        coords = d["polygon"]
        feature = {
            "type": "Feature",
            "properties": {
                "district_code": code,
                "district_name": d["name"],
                "district_type": d["type"],
                "data_quarter": d["quarter"],
                "center": [d["center"]["lng"], d["center"]["lat"]],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def get_mock_district_list(search: str | None = None, district_type: str | None = None) -> list[dict]:
    """Return filtered list of mock districts."""
    results = []
    for code, d in DISTRICTS.items():
        if search and search.lower() not in d["name"].lower():
            continue
        if district_type and d["type"] != district_type:
            continue
        results.append({
            "district_code": code,
            "district_name": d["name"],
            "district_type": d["type"],
            "data_quarter": d["quarter"],
            "center_lng": d["center"]["lng"],
            "center_lat": d["center"]["lat"],
        })
    return results
