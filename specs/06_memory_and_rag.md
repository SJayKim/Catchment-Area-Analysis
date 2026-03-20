# 06. MarketScope AI 메모리 시스템 및 LightRAG 지식 그래프 명세

> **버전**: 1.1
> **최종 수정일**: 2026-03-20
> **상태**: Draft

## Phase 1 포함 여부 결정

| 컴포넌트 | Phase 1 | Phase 2 | 사유 |
|---------|---------|---------|------|
| **LightRAG 지식 그래프** | ❌ 제외 | ✅ 포함 | MVP 범위 초과. 에이전트는 MCP 직접 호출로 충분. ChromaDB·NetworkX 인프라 추가 불필요 |
| **ReMe 세션 메모리** | ❌ 제외 | ✅ 포함 | Phase 1은 세션 단위 분석만 제공. LangGraph 체크포인터가 State 영속성 담당 |
| **Redis 캐싱** | ✅ 포함 | ✅ 포함 | MCP 서버에서 이미 사용. 별도 추가 작업 없음 |
| **ChromaDB (벡터 DB)** | ❌ 제외 | ✅ 포함 | LightRAG 의존 컴포넌트 |

> **결론**: Phase 1에서 이 파일의 컴포넌트는 Redis 캐싱을 제외하고 **모두 비활성**이다.
> Redis 캐싱은 `05_mcp_servers.md`에서 별도 명세됨 — 이 파일에서 중복 정의하지 않는다.
> 아래 명세는 Phase 2 구현을 위한 설계 문서로 유지한다.

---

## 목차

- [Part 1: LightRAG 지식 그래프](#part-1-lightrag-지식-그래프)
  - [1. 아키텍처](#1-아키텍처)
  - [2. 엔티티-관계 모델](#2-엔티티-관계-모델)
  - [3. 데이터 로딩 전략](#3-데이터-로딩-전략)
  - [4. 쿼리 패턴](#4-쿼리-패턴)
  - [5. 한국어 최적화](#5-한국어-최적화)
- [Part 2: ReMe 메모리 시스템](#part-2-reme-메모리-시스템)
  - [6. 메모리 유형](#6-메모리-유형)
  - [7. ReMe 통합 아키텍처](#7-reme-통합-아키텍처)
- [Part 3: 공유 인프라](#part-3-공유-인프라)
  - [8. ChromaDB 구성](#8-chromadb-구성)
  - [9. Redis 캐싱 레이어](#9-redis-캐싱-레이어)
  - [10. 데이터 흐름도](#10-데이터-흐름도)

---

# Part 1: LightRAG 지식 그래프

## 1. 아키텍처

### 1.1 시스템 개요

LightRAG는 상권 분석에 필요한 구조화/비구조화 지식을 그래프 형태로 저장하고, 에이전트가 자연어 질의를 통해 관련 지식을 검색할 수 있게 하는 핵심 지식 기반이다.

```
┌─────────────────────────────────────────────────────────┐
│                    LightRAG 인스턴스                       │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────┐ │
│  │  Gemini 2.5  │   │   bge-m3     │   │  NetworkX   │ │
│  │    Flash     │   │  Embedding   │   │   Graph     │ │
│  │ (엔티티추출) │   │ (1024 dim)   │   │  Storage    │ │
│  └──────┬───────┘   └──────┬───────┘   └──────┬──────┘ │
│         │                  │                   │        │
│         └──────────┬───────┘                   │        │
│                    │                           │        │
│              ┌─────▼─────┐              ┌──────▼──────┐ │
│              │  ChromaDB  │              │  Graph DB   │ │
│              │  (Vector)  │              │ (Relations) │ │
│              └────────────┘              └─────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 1.2 LightRAG 인스턴스 구성

```python
# config/lightrag_config.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GraphStorageType(Enum):
    NETWORKX = "NetworkXStorage"       # Phase 1
    NEO4J = "Neo4JStorage"             # Phase 2+


class VectorStorageType(Enum):
    CHROMADB = "ChromaDBStorage"


@dataclass
class LightRAGConfig:
    """LightRAG 인스턴스 설정"""

    # 작업 디렉토리
    working_dir: str = "./data/lightrag"

    # LLM 설정 (엔티티 추출용)
    llm_model: str = "gemini-2.5-flash"
    llm_provider: str = "google"
    llm_api_key: str = ""  # 환경변수에서 로드
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.0  # 엔티티 추출은 결정적이어야 함

    # 임베딩 설정
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_max_token_size: int = 8192
    embedding_batch_size: int = 32

    # 그래프 스토리지 설정
    graph_storage: str = GraphStorageType.NETWORKX.value  # Phase 1
    neo4j_uri: Optional[str] = None      # Phase 2+
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None

    # 벡터 스토리지 설정
    vector_storage: str = VectorStorageType.CHROMADB.value
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000
    chromadb_collection: str = "marketscope_kg"

    # 청크 설정
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # 엔티티 추출 설정
    entity_extract_max_gleaning: int = 3  # 추출 반복 횟수
    max_entities_per_chunk: int = 20
    max_relations_per_chunk: int = 30

    # 한국어 최적화
    language: str = "Korean"
    enable_korean_tokenizer: bool = True
```

```python
# services/lightrag_service.py

import os
from lightrag import LightRAG, QueryParam
from lightrag.llm.google import google_complete, google_embedding
from lightrag.kg.shared import GRAPH_FIELD_SEP
from config.lightrag_config import LightRAGConfig


class MarketScopeLightRAG:
    """MarketScope 상권 분석용 LightRAG 서비스"""

    def __init__(self, config: LightRAGConfig):
        self.config = config
        self._instance: Optional[LightRAG] = None

    async def initialize(self) -> None:
        """LightRAG 인스턴스 초기화"""
        os.makedirs(self.config.working_dir, exist_ok=True)

        self._instance = LightRAG(
            working_dir=self.config.working_dir,

            # LLM 설정
            llm_model_func=google_complete,
            llm_model_name=self.config.llm_model,
            llm_model_max_async=16,
            llm_model_max_token_size=self.config.llm_max_tokens,
            llm_model_kwargs={
                "temperature": self.config.llm_temperature,
                "api_key": self.config.llm_api_key or os.getenv("GOOGLE_API_KEY"),
            },

            # 임베딩 설정
            embedding_func=EmbeddingFunc(
                embedding_dim=self.config.embedding_dim,
                max_token_size=self.config.embedding_max_token_size,
                func=self._bge_m3_embedding,
            ),

            # 스토리지 설정
            graph_storage=self.config.graph_storage,
            vector_storage=self.config.vector_storage,

            # 청크 설정
            chunk_token_size=self.config.chunk_size,
            chunk_overlap_token_size=self.config.chunk_overlap,

            # 엔티티 추출 설정
            entity_extract_max_gleaning=self.config.entity_extract_max_gleaning,

            # 한국어 엔티티 추출 프롬프트 (섹션 5에서 상세 정의)
            entity_extraction_prompt=KOREAN_ENTITY_EXTRACTION_PROMPT,
        )

    async def _bge_m3_embedding(self, texts: list[str]) -> list[list[float]]:
        """bge-m3 임베딩 함수 (한국어 최적화)"""
        from FlagEmbedding import BGEM3FlagModel

        if not hasattr(self, "_embed_model"):
            self._embed_model = BGEM3FlagModel(
                "BAAI/bge-m3",
                use_fp16=True,
                device="cuda" if torch.cuda.is_available() else "cpu",
            )

        embeddings = self._embed_model.encode(
            texts,
            batch_size=self.config.embedding_batch_size,
            max_length=self.config.embedding_max_token_size,
        )["dense_vecs"]

        return embeddings.tolist()

    async def insert(self, text: str, metadata: dict = None) -> None:
        """문서 삽입"""
        await self._instance.ainsert(text)

    async def query(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> str:
        """지식 그래프 질의"""
        result = await self._instance.aquery(
            question,
            param=QueryParam(
                mode=mode,
                top_k=top_k,
                max_token_for_text_unit=4000,
                max_token_for_global_context=4000,
                max_token_for_local_context=4000,
            ),
        )
        return result

    async def batch_insert(self, texts: list[str], batch_size: int = 10) -> None:
        """배치 문서 삽입"""
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for text in batch:
                await self._instance.ainsert(text)

    async def delete_entity(self, entity_name: str) -> None:
        """특정 엔티티 삭제 (업데이트 시 사용)"""
        await self._instance.adelete_by_entity(entity_name)
```

### 1.3 Phase별 그래프 스토리지 전환 계획

| Phase | 스토리지 | 대상 규모 | 특징 |
|-------|---------|----------|------|
| **Phase 1** | NetworkX (인메모리) | 상권 100개 이하 | 빠른 프로토타이핑, 재시작 시 파일에서 복원 |
| **Phase 2** | Neo4j | 상권 1,000개+ | 영속 스토리지, 복잡한 그래프 순회 쿼리 |
| **Phase 3** | Neo4j Cluster | 전국 상권 | 고가용성, 샤딩 |

```python
# Phase 2 전환 시 Neo4j 설정
NEO4J_CONFIG = {
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "${NEO4J_PASSWORD}",
    "database": "marketscope",
    "max_connection_pool_size": 50,
    "connection_acquisition_timeout": 30,
}
```

---

## 2. 엔티티-관계 모델

### 2.1 엔티티 타입 정의

상권 분석 도메인에 특화된 10개 엔티티 타입을 정의한다.

```python
# models/knowledge_graph_schema.py

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class EntityType(Enum):
    """상권 분석 도메인 엔티티 타입"""

    COMMERCIAL_DISTRICT = "상권"
    ADMINISTRATIVE_AREA = "행정구역"
    BUSINESS_CATEGORY = "업종"
    BRAND = "브랜드"
    FACILITY = "시설"
    TRANSPORTATION = "교통"
    DEVELOPMENT_PROJECT = "개발사업"
    REGULATION = "규제"
    TREND = "트렌드"
    RISK = "리스크"


# 엔티티별 상세 스키마
ENTITY_SCHEMAS = {
    EntityType.COMMERCIAL_DISTRICT: {
        "description": "특정 지역의 상업 활동이 집중된 구역",
        "attributes": [
            "상권명",           # e.g., "강남역 상권", "홍대 상권"
            "상권_코드",        # 소상공인진흥공단 상권 코드
            "상권_유형",        # 골목상권, 발달상권, 전통시장, 관광특구
            "중심_좌표",        # (위도, 경도)
            "면적_m2",          # 상권 면적
            "등급",             # A/B/C/D/E 등급
            "활성화_지수",      # 0~100
        ],
        "examples": ["강남역 상권", "홍대입구 상권", "이태원 상권", "명동 상권"],
    },

    EntityType.ADMINISTRATIVE_AREA: {
        "description": "법정동/행정동 등 행정 구역 단위",
        "attributes": [
            "구역명",
            "구역_코드",        # 법정동 코드
            "구역_유형",        # 시/도, 시/군/구, 읍/면/동
            "인구수",
            "세대수",
            "면적_km2",
        ],
        "examples": ["서초구 서초동", "마포구 서교동", "강남구 역삼동"],
    },

    EntityType.BUSINESS_CATEGORY: {
        "description": "상업 활동의 업종 분류",
        "attributes": [
            "업종명",
            "업종_코드",        # 표준산업분류 코드
            "대분류",           # 음식, 소매, 서비스, 여가 등
            "중분류",
            "소분류",
            "평균_영업기간_월",
            "폐업률",
        ],
        "examples": ["한식음식점", "커피전문점", "편의점", "미용실", "부동산중개"],
    },

    EntityType.BRAND: {
        "description": "프랜차이즈 및 개인 브랜드",
        "attributes": [
            "브랜드명",
            "본사",
            "가맹점_수",
            "평균_매출",
            "업종",
            "타겟_고객층",
        ],
        "examples": ["스타벅스", "이디야커피", "맥도날드", "올리브영"],
    },

    EntityType.FACILITY: {
        "description": "상권에 영향을 미치는 주요 시설",
        "attributes": [
            "시설명",
            "시설_유형",        # 대학교, 병원, 관공서, 쇼핑몰, 공원 등
            "규모",
            "일평균_이용자수",
            "좌표",
        ],
        "examples": ["코엑스", "서울대학교", "삼성서울병원", "CGV 강남"],
    },

    EntityType.TRANSPORTATION: {
        "description": "교통 인프라 (지하철역, 버스정류장 등)",
        "attributes": [
            "교통시설명",
            "교통_유형",        # 지하철, 버스, KTX, 공항 등
            "노선",
            "일평균_승하차수",
            "환승_가능_노선",
        ],
        "examples": ["강남역 (2호선)", "홍대입구역 (2호선/경의중앙선/공항철도)", "서울역"],
    },

    EntityType.DEVELOPMENT_PROJECT: {
        "description": "상권에 영향을 미치는 개발 사업",
        "attributes": [
            "사업명",
            "사업_유형",        # 재개발, 재건축, 도시재생, 신규개발
            "시행자",
            "사업_기간",
            "예상_영향_범위_m",
            "현재_진행_단계",
            "예상_완료일",
        ],
        "examples": ["영동대로 복합환승센터", "세운상가 도시재생", "위례신도시 개발"],
    },

    EntityType.REGULATION: {
        "description": "상권 활동에 영향을 주는 법령 및 규제",
        "attributes": [
            "규제명",
            "규제_유형",        # 영업시간, 허가, 위생, 건축, 세금
            "관련_법령",
            "적용_지역",
            "시행일",
            "영향_업종",
        ],
        "examples": [
            "심야영업 제한 (주거지역)",
            "대규모점포 영업시간 규제",
            "전통시장 보호구역 지정",
        ],
    },

    EntityType.TREND: {
        "description": "소비 트렌드 및 시장 동향",
        "attributes": [
            "트렌드명",
            "트렌드_유형",      # 소비패턴, 기술, 문화, 경제
            "시작_시점",
            "영향_업종",
            "성장_단계",        # 도입기, 성장기, 성숙기, 쇠퇴기
            "관련_키워드",
        ],
        "examples": [
            "1인 가구 증가",
            "배달/테이크아웃 확대",
            "MZ세대 소비 트렌드",
            "ESG 경영",
        ],
    },

    EntityType.RISK: {
        "description": "상권 운영 관련 위험 요소",
        "attributes": [
            "리스크명",
            "리스크_유형",      # 경제, 규제, 경쟁, 입지, 사회
            "영향도",           # 상/중/하
            "발생_확률",        # 상/중/하
            "영향_상권",
            "완화_전략",
        ],
        "examples": [
            "임대료 급등",
            "대형마트 입점",
            "인구 감소",
            "공실률 증가",
            "젠트리피케이션",
        ],
    },
}
```

### 2.2 관계 타입 정의

```python
class RelationType(Enum):
    """상권 분석 도메인 관계 타입 (24종)"""

    # === 공간적 관계 (Spatial) ===
    LOCATED_IN = "위치함"
    # 상권 → 행정구역: "강남역 상권은 서초구 서초동에 위치함"

    ADJACENT_TO = "인접함"
    # 상권 → 상권: "강남역 상권은 역삼역 상권에 인접함"

    WITHIN_RADIUS = "영향권_내"
    # 시설/교통 → 상권: "강남역은 강남역 상권의 영향권 내에 있음"

    # === 산업적 관계 (Industry) ===
    BELONGS_TO_CATEGORY = "업종_분류"
    # 브랜드 → 업종: "스타벅스는 커피전문점 업종에 속함"

    OPERATES_IN = "영업_중"
    # 브랜드 → 상권: "스타벅스가 강남역 상권에서 영업 중"

    COMPETES_WITH = "경쟁_관계"
    # 브랜드 → 브랜드: "스타벅스와 이디야커피는 경쟁 관계"

    DOMINANT_CATEGORY = "주요_업종"
    # 업종 → 상권: "커피전문점이 홍대 상권의 주요 업종"

    SUBSTITUTES = "대체_관계"
    # 업종 → 업종: "편의점 도시락이 한식음식점의 대체재"

    # === 영향 관계 (Impact) ===
    INCREASES_TRAFFIC = "유동인구_증가_요인"
    # 시설/교통/개발사업 → 상권: "코엑스가 삼성역 상권 유동인구 증가 요인"

    DECREASES_TRAFFIC = "유동인구_감소_요인"
    # 개발사업/리스크 → 상권: "재개발 공사가 유동인구 감소 요인"

    INCREASES_REVENUE = "매출_증가_요인"
    # 트렌드/시설 → 업종/상권

    DECREASES_REVENUE = "매출_감소_요인"
    # 트렌드/규제/리스크 → 업종/상권

    INCREASES_RENT = "임대료_상승_요인"
    # 개발사업/트렌드 → 상권

    DECREASES_RENT = "임대료_하락_요인"
    # 리스크 → 상권

    # === 규제 관계 (Regulatory) ===
    REGULATED_BY = "규제_적용"
    # 상권/업종 → 규제: "강남역 상권은 심야영업 제한 규제 적용"

    EXEMPTED_FROM = "규제_면제"
    # 상권/업종 → 규제

    # === 시간적 관계 (Temporal) ===
    DEVELOPED_INTO = "발전됨"
    # 상권 → 상권: "신사동 가로수길이 세로수길로 발전됨"

    PRECEDED_BY = "선행_사건"
    # 트렌드 → 트렌드: "코로나 팬데믹이 비대면 소비 트렌드에 선행"

    TRIGGERS = "유발"
    # 개발사업/트렌드/리스크 → 리스크/트렌드

    # === 인과적 관계 (Causal) ===
    CAUSES_RISK = "리스크_유발"
    # 개발사업/트렌드 → 리스크: "대규모 재개발이 젠트리피케이션 리스크 유발"

    MITIGATES_RISK = "리스크_완화"
    # 규제/시설 → 리스크: "상가임대차보호법이 임대료 급등 리스크 완화"

    # === 연관 관계 (Association) ===
    SYNERGY_WITH = "시너지"
    # 업종 → 업종: "커피전문점과 디저트카페 시너지"

    SEASONAL_PATTERN = "계절성"
    # 업종/상권 → 트렌드: "아이스크림 업종의 여름 계절성"

    TARGETS_DEMOGRAPHIC = "타겟_고객"
    # 브랜드/업종 → 트렌드: "올리브영이 MZ세대를 타겟으로 함"


# 관계별 상세 정의 (source → target 타입 제약)
RELATION_CONSTRAINTS = {
    RelationType.LOCATED_IN: {
        "source_types": [EntityType.COMMERCIAL_DISTRICT, EntityType.FACILITY, EntityType.TRANSPORTATION],
        "target_types": [EntityType.ADMINISTRATIVE_AREA],
        "description": "엔티티가 특정 행정구역 내에 물리적으로 위치함",
        "weight_range": (0.8, 1.0),  # 확실한 관계
    },
    RelationType.ADJACENT_TO: {
        "source_types": [EntityType.COMMERCIAL_DISTRICT],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "두 상권이 지리적으로 인접하여 상호 영향을 미침",
        "weight_range": (0.3, 0.9),  # 거리에 따라 가중치 변동
    },
    RelationType.WITHIN_RADIUS: {
        "source_types": [EntityType.FACILITY, EntityType.TRANSPORTATION],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "시설/교통이 상권의 도보 영향권(500m) 내에 존재",
        "weight_range": (0.5, 1.0),
    },
    RelationType.BELONGS_TO_CATEGORY: {
        "source_types": [EntityType.BRAND],
        "target_types": [EntityType.BUSINESS_CATEGORY],
        "description": "브랜드가 특정 업종 카테고리에 분류됨",
        "weight_range": (0.9, 1.0),
    },
    RelationType.OPERATES_IN: {
        "source_types": [EntityType.BRAND],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "브랜드가 특정 상권에서 실제 영업 중",
        "weight_range": (0.9, 1.0),
    },
    RelationType.COMPETES_WITH: {
        "source_types": [EntityType.BRAND],
        "target_types": [EntityType.BRAND],
        "description": "동일 업종 내에서 직접 경쟁 관계",
        "weight_range": (0.3, 1.0),
    },
    RelationType.DOMINANT_CATEGORY: {
        "source_types": [EntityType.BUSINESS_CATEGORY],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "해당 업종이 상권 내 점포 수/매출 비중 상위",
        "weight_range": (0.5, 1.0),
    },
    RelationType.SUBSTITUTES: {
        "source_types": [EntityType.BUSINESS_CATEGORY],
        "target_types": [EntityType.BUSINESS_CATEGORY],
        "description": "고객 관점에서 대체 가능한 업종 관계",
        "weight_range": (0.2, 0.8),
    },
    RelationType.INCREASES_TRAFFIC: {
        "source_types": [EntityType.FACILITY, EntityType.TRANSPORTATION, EntityType.DEVELOPMENT_PROJECT],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "해당 요소가 상권 유동인구 증가에 기여",
        "weight_range": (0.3, 1.0),
    },
    RelationType.DECREASES_TRAFFIC: {
        "source_types": [EntityType.DEVELOPMENT_PROJECT, EntityType.RISK],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "해당 요소가 상권 유동인구 감소를 유발",
        "weight_range": (0.3, 1.0),
    },
    RelationType.INCREASES_REVENUE: {
        "source_types": [EntityType.TREND, EntityType.FACILITY],
        "target_types": [EntityType.BUSINESS_CATEGORY, EntityType.COMMERCIAL_DISTRICT],
        "description": "해당 요소가 매출 증가에 기여",
        "weight_range": (0.2, 0.9),
    },
    RelationType.DECREASES_REVENUE: {
        "source_types": [EntityType.TREND, EntityType.REGULATION, EntityType.RISK],
        "target_types": [EntityType.BUSINESS_CATEGORY, EntityType.COMMERCIAL_DISTRICT],
        "description": "해당 요소가 매출 감소를 유발",
        "weight_range": (0.2, 0.9),
    },
    RelationType.INCREASES_RENT: {
        "source_types": [EntityType.DEVELOPMENT_PROJECT, EntityType.TREND],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "해당 요소가 상권 임대료 상승에 기여",
        "weight_range": (0.3, 0.9),
    },
    RelationType.DECREASES_RENT: {
        "source_types": [EntityType.RISK],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "해당 요소가 상권 임대료 하락을 유발",
        "weight_range": (0.3, 0.9),
    },
    RelationType.REGULATED_BY: {
        "source_types": [EntityType.COMMERCIAL_DISTRICT, EntityType.BUSINESS_CATEGORY],
        "target_types": [EntityType.REGULATION],
        "description": "상권/업종이 특정 규제의 적용을 받음",
        "weight_range": (0.7, 1.0),
    },
    RelationType.EXEMPTED_FROM: {
        "source_types": [EntityType.COMMERCIAL_DISTRICT, EntityType.BUSINESS_CATEGORY],
        "target_types": [EntityType.REGULATION],
        "description": "상권/업종이 특정 규제에서 면제됨",
        "weight_range": (0.7, 1.0),
    },
    RelationType.DEVELOPED_INTO: {
        "source_types": [EntityType.COMMERCIAL_DISTRICT],
        "target_types": [EntityType.COMMERCIAL_DISTRICT],
        "description": "상권이 시간 경과에 따라 다른 형태로 발전/변화",
        "weight_range": (0.5, 1.0),
    },
    RelationType.PRECEDED_BY: {
        "source_types": [EntityType.TREND],
        "target_types": [EntityType.TREND],
        "description": "한 트렌드가 다른 트렌드에 시간적으로 선행",
        "weight_range": (0.3, 0.8),
    },
    RelationType.TRIGGERS: {
        "source_types": [EntityType.DEVELOPMENT_PROJECT, EntityType.TREND, EntityType.RISK],
        "target_types": [EntityType.RISK, EntityType.TREND],
        "description": "한 요소가 다른 요소를 연쇄적으로 유발",
        "weight_range": (0.3, 0.9),
    },
    RelationType.CAUSES_RISK: {
        "source_types": [EntityType.DEVELOPMENT_PROJECT, EntityType.TREND],
        "target_types": [EntityType.RISK],
        "description": "개발사업/트렌드가 리스크를 직접적으로 유발",
        "weight_range": (0.4, 1.0),
    },
    RelationType.MITIGATES_RISK: {
        "source_types": [EntityType.REGULATION, EntityType.FACILITY],
        "target_types": [EntityType.RISK],
        "description": "규제/시설이 리스크를 완화하는 효과",
        "weight_range": (0.3, 0.9),
    },
    RelationType.SYNERGY_WITH: {
        "source_types": [EntityType.BUSINESS_CATEGORY],
        "target_types": [EntityType.BUSINESS_CATEGORY],
        "description": "두 업종이 동반 입점 시 시너지 효과 발생",
        "weight_range": (0.3, 0.9),
    },
    RelationType.SEASONAL_PATTERN: {
        "source_types": [EntityType.BUSINESS_CATEGORY, EntityType.COMMERCIAL_DISTRICT],
        "target_types": [EntityType.TREND],
        "description": "업종/상권이 특정 계절적 패턴을 보임",
        "weight_range": (0.5, 0.9),
    },
    RelationType.TARGETS_DEMOGRAPHIC: {
        "source_types": [EntityType.BRAND, EntityType.BUSINESS_CATEGORY],
        "target_types": [EntityType.TREND],
        "description": "브랜드/업종이 특정 인구통계적 트렌드를 타겟팅",
        "weight_range": (0.4, 0.9),
    },
}
```

---

## 3. 데이터 로딩 전략

### 3.1 로딩 대상 데이터

| 데이터 분류 | 소스 | 로딩 빈도 | 우선순위 |
|------------|------|----------|---------|
| **상권 프로필** | 소상공인진흥공단 API, 서울열린데이터 | 분기별 | P0 (필수) |
| **업종 통계** | 통계청, 국세청 | 분기별 | P0 |
| **뉴스 기사** | 네이버 뉴스 API, 크롤링 | 주간 | P1 |
| **법령/규제** | 국가법령정보센터 | 월간 | P1 |
| **개발사업 정보** | 국토교통부, 서울시 도시계획 | 월간 | P1 |
| **분석 교훈** | 자체 분석 결과 (ReMe → LightRAG) | 수시 (분석 완료 시) | P2 |
| **트렌드 보고서** | 한국은행, 트렌드 리포트 | 월간 | P2 |

### 3.2 구조화 데이터 → 자연어 변환 텍스트 템플릿

LightRAG의 엔티티 추출은 자연어 텍스트에서 이루어지므로 구조화된 데이터를 자연어 문장으로 변환해야 한다.

```python
# loaders/text_templates.py

from typing import Any


class DistrictTextTemplate:
    """상권 프로필 데이터를 자연어 텍스트로 변환"""

    @staticmethod
    def render_district_profile(data: dict[str, Any]) -> str:
        """상권 기본 프로필 텍스트 생성"""
        return f"""## {data['상권명']} 상권 프로필

{data['상권명']}은(는) {data['행정구역']}에 위치한 {data['상권유형']} 상권이다.
해당 상권의 면적은 약 {data['면적_m2']:,}m²이며, 상권 활성화 등급은 {data['등급']}등급이다.

### 유동인구
{data['상권명']} 상권의 일평균 유동인구는 약 {data['일평균_유동인구']:,}명이다.
주중 유동인구는 약 {data['주중_유동인구']:,}명, 주말 유동인구는 약 {data['주말_유동인구']:,}명이다.
주요 유동인구 시간대는 {data['피크_시간대']}이며, {data['주요_연령대']} 연령대가 가장 많다.
성별 비율은 남성 {data['남성_비율']}%, 여성 {data['여성_비율']}%이다.

### 주요 업종 구성
{data['상권명']} 상권의 총 점포 수는 {data['총_점포수']:,}개이다.
상위 업종은 다음과 같다:
{chr(10).join(f"- {item['업종명']}: {item['점포수']}개 ({item['비율']}%)" for item in data['상위_업종'])}

### 매출 현황
{data['상권명']} 상권의 분기 총 매출액은 약 {data['분기_총매출']:,}만원이다.
점포당 평균 월매출은 약 {data['점포당_월평균매출']:,}만원이다.
전분기 대비 매출 증감률은 {data['매출_증감률']}%이다.

### 교통 접근성
{data['상권명']} 상권의 주요 교통시설:
{chr(10).join(f"- {item['시설명']} ({item['유형']}): 도보 {item['도보_거리_분']}분, 일평균 이용객 {item['일평균_이용객']:,}명" for item in data['교통시설'])}

### 주변 시설
{chr(10).join(f"- {item['시설명']} ({item['유형']}): {item['거리_m']}m" for item in data['주변시설'])}

### 임대료 현황
{data['상권명']} 상권의 1층 평균 임대료는 m²당 월 {data['평균_임대료_m2']:,}원이다.
전년 대비 임대료 변동률은 {data['임대료_변동률']}%이다.
평균 보증금은 {data['평균_보증금']:,}만원이다.

### 개폐업 현황
최근 1년간 개업 점포 수는 {data['개업_점포수']}개, 폐업 점포 수는 {data['폐업_점포수']}개이다.
폐업률은 {data['폐업률']}%이며, 전년 대비 {'증가' if data['폐업률_변동'] > 0 else '감소'}하였다.
"""

    @staticmethod
    def render_industry_analysis(data: dict[str, Any]) -> str:
        """업종 분석 텍스트 생성"""
        return f"""## {data['업종명']} 업종 분석 ({data['상권명']} 상권)

{data['상권명']} 상권 내 {data['업종명']}의 점포 수는 {data['점포수']}개이며,
이는 전체 점포 대비 {data['점포_비율']}%를 차지한다.

### 매출 분석
{data['업종명']}의 월평균 매출은 약 {data['월평균_매출']:,}만원이다.
객단가는 약 {data['객단가']:,}원이며, 일평균 거래건수는 {data['일평균_거래건수']}건이다.
요일별 매출 비중: 월 {data['월_비중']}%, 화 {data['화_비중']}%, 수 {data['수_비중']}%, 목 {data['목_비중']}%, 금 {data['금_비중']}%, 토 {data['토_비중']}%, 일 {data['일_비중']}%
시간대별 피크: {data['매출_피크_시간대']}

### 경쟁 현황
동일 업종 경쟁 점포 수: {data['경쟁_점포수']}개
100m 반경 내 동일 업종: {data['근접_경쟁_점포수']}개
주요 경쟁 브랜드: {', '.join(data['주요_경쟁_브랜드'])}
프랜차이즈 비율: {data['프랜차이즈_비율']}%

### 트렌드
전년 대비 매출 증감: {data['yoy_매출_증감']}%
전년 대비 점포 수 증감: {data['yoy_점포_증감']}%
해당 업종의 전국 평균 대비 성과: {'상위' if data['전국_대비'] > 0 else '하위'} {abs(data['전국_대비'])}%
"""

    @staticmethod
    def render_news_article(data: dict[str, Any]) -> str:
        """뉴스 기사 텍스트 생성"""
        return f"""## 뉴스: {data['제목']}

발행일: {data['발행일']}
출처: {data['출처']}
관련 상권: {', '.join(data.get('관련_상권', []))}
관련 업종: {', '.join(data.get('관련_업종', []))}

{data['본문']}

핵심 키워드: {', '.join(data.get('키워드', []))}
"""

    @staticmethod
    def render_regulation(data: dict[str, Any]) -> str:
        """법령/규제 텍스트 생성"""
        return f"""## 규제: {data['규제명']}

법령: {data['관련_법령']}
시행일: {data['시행일']}
적용 지역: {', '.join(data.get('적용_지역', ['전국']))}
영향 업종: {', '.join(data.get('영향_업종', []))}

### 규제 내용
{data['내용']}

### 상권 영향
{data.get('영향_분석', '분석 미수행')}
"""

    @staticmethod
    def render_development_project(data: dict[str, Any]) -> str:
        """개발사업 텍스트 생성"""
        return f"""## 개발사업: {data['사업명']}

사업 유형: {data['사업_유형']}
시행자: {data['시행자']}
사업 기간: {data['착공일']} ~ {data['완료_예정일']}
현재 단계: {data['현재_단계']}
위치: {data['위치']}
영향 상권: {', '.join(data.get('영향_상권', []))}

### 사업 개요
{data['개요']}

### 상권 영향 전망
예상 영향 범위: 반경 {data['영향_범위_m']}m
유동인구 영향: {data.get('유동인구_영향', '미분석')}
임대료 영향: {data.get('임대료_영향', '미분석')}
"""

    @staticmethod
    def render_analysis_lesson(data: dict[str, Any]) -> str:
        """분석 교훈 텍스트 생성 (ReMe → LightRAG 전달용)"""
        return f"""## 분석 교훈: {data['제목']}

분석 일자: {data['분석일']}
대상 상권: {data['상권명']}
대상 업종: {data.get('업종명', '전체')}
교훈 유형: {data['유형']}

### 교훈 내용
{data['내용']}

### 발견 맥락
{data['맥락']}

### 적용 조건
이 교훈은 다음 조건에서 참고해야 한다:
{chr(10).join(f"- {condition}" for condition in data.get('적용_조건', []))}

신뢰도: {data.get('신뢰도', 'N/A')}
"""
```

### 3.3 로딩 빈도 및 스케줄

```python
# loaders/loading_schedule.py

from enum import Enum
from dataclasses import dataclass


class LoadingFrequency(Enum):
    QUARTERLY = "quarterly"    # 분기별 (1, 4, 7, 10월)
    MONTHLY = "monthly"        # 월간
    WEEKLY = "weekly"          # 주간 (매주 월요일)
    ON_DEMAND = "on_demand"    # 수시 (이벤트 발생 시)


LOADING_SCHEDULE = {
    "district_profiles": {
        "frequency": LoadingFrequency.QUARTERLY,
        "description": "상권 프로필 전체 갱신",
        "cron": "0 2 1 1,4,7,10 *",  # 분기 첫날 새벽 2시
        "source": ["소상공인진흥공단_API", "서울열린데이터"],
        "estimated_records": 3000,
        "estimated_duration_min": 120,
        "strategy": "full_replace",  # 전체 교체
    },
    "industry_statistics": {
        "frequency": LoadingFrequency.QUARTERLY,
        "description": "업종별 통계 갱신",
        "cron": "0 4 1 1,4,7,10 *",
        "source": ["통계청", "국세청"],
        "estimated_records": 500,
        "estimated_duration_min": 60,
        "strategy": "full_replace",
    },
    "news_articles": {
        "frequency": LoadingFrequency.WEEKLY,
        "description": "상권 관련 뉴스 수집 및 로딩",
        "cron": "0 6 * * 1",  # 매주 월요일 새벽 6시
        "source": ["네이버뉴스_API"],
        "estimated_records": 200,
        "estimated_duration_min": 30,
        "strategy": "incremental_append",  # 추가만
    },
    "regulations": {
        "frequency": LoadingFrequency.MONTHLY,
        "description": "법령/규제 변경 사항 반영",
        "cron": "0 3 1 * *",  # 매월 1일 새벽 3시
        "source": ["국가법령정보센터"],
        "estimated_records": 20,
        "estimated_duration_min": 15,
        "strategy": "incremental_upsert",  # 변경분만 반영
    },
    "development_projects": {
        "frequency": LoadingFrequency.MONTHLY,
        "description": "개발사업 진행 현황 갱신",
        "cron": "0 3 15 * *",  # 매월 15일 새벽 3시
        "source": ["국토교통부", "서울시_도시계획"],
        "estimated_records": 50,
        "estimated_duration_min": 20,
        "strategy": "incremental_upsert",
    },
    "analysis_lessons": {
        "frequency": LoadingFrequency.ON_DEMAND,
        "description": "에이전트 분석 교훈 반영",
        "trigger": "analysis_complete_event",
        "source": ["ReMe_TaskMemory"],
        "estimated_records": 1,
        "estimated_duration_min": 1,
        "strategy": "incremental_append",
    },
}
```

### 3.4 배치 로딩 파이프라인

```python
# loaders/batch_loader.py

import asyncio
import logging
from datetime import datetime
from typing import Any

from services.lightrag_service import MarketScopeLightRAG
from loaders.text_templates import DistrictTextTemplate

logger = logging.getLogger(__name__)


class BatchLoadingPipeline:
    """LightRAG 배치 데이터 로딩 파이프라인"""

    def __init__(self, lightrag: MarketScopeLightRAG):
        self.lightrag = lightrag
        self.template = DistrictTextTemplate()
        self.stats = {"loaded": 0, "failed": 0, "skipped": 0}

    async def run_quarterly_load(self) -> dict:
        """분기별 전체 로딩 실행"""
        logger.info("=== 분기별 전체 로딩 시작 ===")
        self.stats = {"loaded": 0, "failed": 0, "skipped": 0}

        # 1단계: 상권 프로필 로딩
        await self._load_district_profiles()

        # 2단계: 업종 통계 로딩
        await self._load_industry_statistics()

        # 3단계: 교통 데이터 로딩
        await self._load_transportation_data()

        logger.info(f"=== 분기별 로딩 완료: {self.stats} ===")
        return self.stats

    async def run_weekly_load(self) -> dict:
        """주간 증분 로딩 실행"""
        logger.info("=== 주간 증분 로딩 시작 ===")
        self.stats = {"loaded": 0, "failed": 0, "skipped": 0}

        await self._load_news_articles()

        logger.info(f"=== 주간 로딩 완료: {self.stats} ===")
        return self.stats

    async def run_on_demand_load(self, data_type: str, data: dict) -> dict:
        """수시 로딩 (분석 교훈 등)"""
        logger.info(f"=== 수시 로딩: {data_type} ===")

        if data_type == "analysis_lesson":
            text = self.template.render_analysis_lesson(data)
            await self.lightrag.insert(text, metadata={"type": "lesson", "date": datetime.now().isoformat()})
            self.stats["loaded"] += 1

        return self.stats

    async def _load_district_profiles(self) -> None:
        """상권 프로필 로딩"""
        from data_sources.semas_api import SemaAPIClient  # 소상공인진흥공단

        client = SemaAPIClient()
        districts = await client.fetch_all_districts()

        texts = []
        for district in districts:
            try:
                text = self.template.render_district_profile(district)
                texts.append(text)
            except Exception as e:
                logger.error(f"상권 프로필 변환 실패: {district.get('상권명')}: {e}")
                self.stats["failed"] += 1

        # 배치 삽입 (10개씩)
        await self.lightrag.batch_insert(texts, batch_size=10)
        self.stats["loaded"] += len(texts)

    async def _load_industry_statistics(self) -> None:
        """업종 통계 로딩"""
        from data_sources.statistics_api import StatisticsAPIClient

        client = StatisticsAPIClient()
        industries = await client.fetch_industry_stats()

        texts = []
        for industry in industries:
            try:
                text = self.template.render_industry_analysis(industry)
                texts.append(text)
            except Exception as e:
                logger.error(f"업종 통계 변환 실패: {e}")
                self.stats["failed"] += 1

        await self.lightrag.batch_insert(texts, batch_size=10)
        self.stats["loaded"] += len(texts)

    async def _load_transportation_data(self) -> None:
        """교통 데이터 로딩 (상권 프로필에 포함되지 않는 상세 데이터)"""
        pass  # 구현 예정

    async def _load_news_articles(self) -> None:
        """뉴스 기사 증분 로딩"""
        from data_sources.news_api import NewsAPIClient

        client = NewsAPIClient()
        articles = await client.fetch_recent_articles(
            keywords=["상권", "창업", "폐업", "임대료", "재개발", "유동인구"],
            days=7,
        )

        texts = []
        for article in articles:
            try:
                text = self.template.render_news_article(article)
                texts.append(text)
            except Exception as e:
                logger.error(f"뉴스 기사 변환 실패: {e}")
                self.stats["failed"] += 1

        await self.lightrag.batch_insert(texts, batch_size=5)
        self.stats["loaded"] += len(texts)
```

### 3.5 증분 업데이트 전략

```python
# loaders/incremental_updater.py

import hashlib
from datetime import datetime
from typing import Optional

from services.lightrag_service import MarketScopeLightRAG
from db.postgres import PostgresClient


class IncrementalUpdater:
    """LightRAG 증분 업데이트 관리"""

    def __init__(self, lightrag: MarketScopeLightRAG, db: PostgresClient):
        self.lightrag = lightrag
        self.db = db

    async def upsert_district(self, district_data: dict) -> bool:
        """상권 프로필 업데이트 (변경 시에만)

        전략:
        1. 데이터 해시를 비교하여 변경 여부 확인
        2. 변경된 경우 기존 엔티티 삭제 후 재삽입
        3. 해시 테이블에 새 해시값 기록
        """
        district_name = district_data["상권명"]
        data_hash = self._compute_hash(district_data)

        # 이전 해시와 비교
        prev_hash = await self.db.fetch_one(
            "SELECT data_hash FROM lightrag_load_log WHERE entity_name = $1 AND entity_type = '상권'",
            district_name,
        )

        if prev_hash and prev_hash["data_hash"] == data_hash:
            return False  # 변경 없음, 스킵

        # 기존 엔티티 삭제
        await self.lightrag.delete_entity(district_name)

        # 새 데이터 삽입
        from loaders.text_templates import DistrictTextTemplate
        text = DistrictTextTemplate.render_district_profile(district_data)
        await self.lightrag.insert(text)

        # 로그 기록
        await self.db.execute(
            """
            INSERT INTO lightrag_load_log (entity_name, entity_type, data_hash, loaded_at)
            VALUES ($1, '상권', $2, $3)
            ON CONFLICT (entity_name, entity_type)
            DO UPDATE SET data_hash = $2, loaded_at = $3
            """,
            district_name, data_hash, datetime.now(),
        )
        return True

    def _compute_hash(self, data: dict) -> str:
        """데이터 변경 감지용 해시 계산"""
        import json
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode()).hexdigest()


# PostgreSQL 로드 이력 테이블 DDL
LOAD_LOG_DDL = """
CREATE TABLE IF NOT EXISTS lightrag_load_log (
    id              SERIAL PRIMARY KEY,
    entity_name     VARCHAR(255) NOT NULL,
    entity_type     VARCHAR(50) NOT NULL,
    data_hash       VARCHAR(64) NOT NULL,
    loaded_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (entity_name, entity_type)
);

CREATE INDEX idx_load_log_type ON lightrag_load_log(entity_type);
CREATE INDEX idx_load_log_loaded_at ON lightrag_load_log(loaded_at);
"""
```

---

## 4. 쿼리 패턴

### 4.1 에이전트별 LightRAG 쿼리 패턴

각 에이전트는 분석 수행 전 LightRAG에서 관련 배경 지식을 검색하여 컨텍스트를 보강한다.

```python
# agents/lightrag_queries.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentQuery:
    """에이전트 LightRAG 쿼리 정의"""
    agent_name: str
    query_template: str
    query_mode: str            # naive, local, global, hybrid
    top_k: int
    fallback_mode: Optional[str] = None  # 결과 부족 시 대체 모드


AGENT_QUERY_PATTERNS = {

    # ─────────────────────────────────────────────
    # 1. 유동인구 분석 에이전트 (PopulationAgent)
    # ─────────────────────────────────────────────
    "population_agent": [
        AgentQuery(
            agent_name="PopulationAgent",
            query_template="{district_name} 상권의 유동인구 특성과 주변 교통 환경은 어떠한가?",
            query_mode="local",   # 특정 상권의 로컬 컨텍스트 필요
            top_k=10,
            fallback_mode="hybrid",
        ),
        AgentQuery(
            agent_name="PopulationAgent",
            query_template="{district_name} 상권 유동인구에 영향을 미치는 시설과 개발사업은 무엇인가?",
            query_mode="local",
            top_k=8,
        ),
        AgentQuery(
            agent_name="PopulationAgent",
            query_template="{district_name} 인근 유동인구 변화 트렌드와 계절적 특성은?",
            query_mode="hybrid",
            top_k=8,
        ),
    ],

    # ─────────────────────────────────────────────
    # 2. 매출 분석 에이전트 (RevenueAgent)
    # ─────────────────────────────────────────────
    "revenue_agent": [
        AgentQuery(
            agent_name="RevenueAgent",
            query_template="{industry_name} 업종의 매출 트렌드와 객단가 특성은 어떠한가?",
            query_mode="local",
            top_k=10,
            fallback_mode="hybrid",
        ),
        AgentQuery(
            agent_name="RevenueAgent",
            query_template="{district_name} 상권에서 {industry_name} 업종의 매출에 영향을 미치는 요인은?",
            query_mode="hybrid",
            top_k=10,
        ),
        AgentQuery(
            agent_name="RevenueAgent",
            query_template="{industry_name} 업종의 시간대별, 요일별 매출 패턴과 시너지 업종은?",
            query_mode="local",
            top_k=8,
        ),
    ],

    # ─────────────────────────────────────────────
    # 3. 경쟁 분석 에이전트 (CompetitionAgent)
    # ─────────────────────────────────────────────
    "competition_agent": [
        AgentQuery(
            agent_name="CompetitionAgent",
            query_template="{district_name} 상권의 {industry_name} 업종 경쟁 환경과 차별화 요소는?",
            query_mode="local",
            top_k=10,
            fallback_mode="hybrid",
        ),
        AgentQuery(
            agent_name="CompetitionAgent",
            query_template="{district_name} 상권에서 경쟁 관계에 있는 브랜드와 대체 업종은?",
            query_mode="local",
            top_k=10,
        ),
        AgentQuery(
            agent_name="CompetitionAgent",
            query_template="{industry_name} 업종의 프랜차이즈 대비 개인사업자 경쟁력은?",
            query_mode="global",  # 전국적 트렌드 비교 필요
            top_k=8,
        ),
    ],

    # ─────────────────────────────────────────────
    # 4. 임대료 분석 에이전트 (RentAgent)
    # ─────────────────────────────────────────────
    "rent_agent": [
        AgentQuery(
            agent_name="RentAgent",
            query_template="{district_name} 상권의 임대료 현황과 변동 추이는?",
            query_mode="local",
            top_k=8,
        ),
        AgentQuery(
            agent_name="RentAgent",
            query_template="{district_name} 상권 임대료에 영향을 미치는 개발사업과 트렌드는?",
            query_mode="hybrid",
            top_k=10,
            fallback_mode="global",
        ),
        AgentQuery(
            agent_name="RentAgent",
            query_template="{district_name} 상권의 젠트리피케이션 리스크와 임대차 보호 규제는?",
            query_mode="hybrid",
            top_k=8,
        ),
    ],

    # ─────────────────────────────────────────────
    # 5. 입지 분석 에이전트 (LocationAgent)
    # ─────────────────────────────────────────────
    "location_agent": [
        AgentQuery(
            agent_name="LocationAgent",
            query_template="{district_name} 상권의 입지 특성, 접근성, 가시성은 어떠한가?",
            query_mode="local",
            top_k=10,
        ),
        AgentQuery(
            agent_name="LocationAgent",
            query_template="{district_name} 인접 상권과의 관계 및 상호 영향은?",
            query_mode="local",
            top_k=8,
        ),
        AgentQuery(
            agent_name="LocationAgent",
            query_template="{district_name} 상권 주변 시설 배치와 동선 특성은?",
            query_mode="local",
            top_k=8,
        ),
    ],

    # ─────────────────────────────────────────────
    # 6. 규제/법령 분석 에이전트 (RegulatoryAgent)
    # ─────────────────────────────────────────────
    "regulatory_agent": [
        AgentQuery(
            agent_name="RegulatoryAgent",
            query_template="{district_name} 상권에 적용되는 규제와 법령은 무엇인가?",
            query_mode="hybrid",
            top_k=10,
        ),
        AgentQuery(
            agent_name="RegulatoryAgent",
            query_template="{industry_name} 업종에 영향을 미치는 최신 규제 변경은?",
            query_mode="global",  # 전국 단위 규제 정보 필요
            top_k=10,
        ),
        AgentQuery(
            agent_name="RegulatoryAgent",
            query_template="{district_name} 상권의 영업 허가, 위생, 건축 관련 규제 현황은?",
            query_mode="hybrid",
            top_k=8,
        ),
    ],

    # ─────────────────────────────────────────────
    # 7. 트렌드 분석 에이전트 (TrendAgent)
    # ─────────────────────────────────────────────
    "trend_agent": [
        AgentQuery(
            agent_name="TrendAgent",
            query_template="{industry_name} 업종에 영향을 미치는 최신 소비 트렌드와 기술 변화는?",
            query_mode="global",  # 전체적 트렌드 파악 필요
            top_k=15,
        ),
        AgentQuery(
            agent_name="TrendAgent",
            query_template="{district_name} 상권의 인구통계적 변화와 소비 패턴 변화는?",
            query_mode="hybrid",
            top_k=10,
        ),
        AgentQuery(
            agent_name="TrendAgent",
            query_template="최근 1년간 상권/창업 관련 주요 뉴스와 이슈는?",
            query_mode="global",
            top_k=15,
        ),
    ],

    # ─────────────────────────────────────────────
    # 8. 리스크 분석 에이전트 (RiskAgent)
    # ─────────────────────────────────────────────
    "risk_agent": [
        AgentQuery(
            agent_name="RiskAgent",
            query_template="{district_name} 상권의 알려진 리스크 요인과 과거 사례는?",
            query_mode="local",
            top_k=10,
            fallback_mode="hybrid",
        ),
        AgentQuery(
            agent_name="RiskAgent",
            query_template="{district_name} 상권에 영향을 줄 수 있는 개발사업과 규제 변화는?",
            query_mode="hybrid",
            top_k=10,
        ),
        AgentQuery(
            agent_name="RiskAgent",
            query_template="{industry_name} 업종의 폐업률 추이와 주요 폐업 원인은?",
            query_mode="global",
            top_k=10,
        ),
    ],

    # ─────────────────────────────────────────────
    # 9. 종합 판단 에이전트 (CommanderAgent)
    # ─────────────────────────────────────────────
    "commander_agent": [
        AgentQuery(
            agent_name="CommanderAgent",
            query_template="{district_name} 상권의 전반적인 특성과 핵심 성공/실패 요인은?",
            query_mode="hybrid",
            top_k=15,
        ),
        AgentQuery(
            agent_name="CommanderAgent",
            query_template="{district_name} 상권에서 과거 분석 시 발견된 교훈과 주의사항은?",
            query_mode="local",
            top_k=10,
        ),
    ],
}
```

### 4.2 쿼리 모드 선택 로직

```python
# services/query_mode_selector.py

from enum import Enum


class QueryMode(Enum):
    NAIVE = "naive"      # 단순 벡터 유사도 검색
    LOCAL = "local"      # 로컬 그래프 탐색 (특정 엔티티 중심)
    GLOBAL = "global"    # 글로벌 커뮤니티 요약 검색
    HYBRID = "hybrid"    # local + global 결합


class QueryModeSelector:
    """쿼리 특성에 따른 최적 모드 자동 선택

    선택 기준:
    ┌─────────────────────────────────────────────────────────┐
    │ 쿼리 특성             │ 추천 모드  │ 이유              │
    ├───────────────────────┼───────────┼──────────────────┤
    │ 특정 상권/엔티티 지정  │ local     │ 해당 엔티티 중심   │
    │                       │           │ 그래프 탐색        │
    ├───────────────────────┼───────────┼──────────────────┤
    │ 업종 전체 트렌드      │ global    │ 커뮤니티 단위       │
    │                       │           │ 요약 검색          │
    ├───────────────────────┼───────────┼──────────────────┤
    │ 상권+업종 조합        │ hybrid    │ 로컬 상세 +        │
    │                       │           │ 글로벌 맥락        │
    ├───────────────────────┼───────────┼──────────────────┤
    │ 단순 사실 질문        │ naive     │ 벡터 검색으로 충분  │
    └─────────────────────────────────────────────────────────┘
    """

    @staticmethod
    def select_mode(
        query: str,
        has_specific_district: bool = False,
        has_specific_industry: bool = False,
        requires_trend_analysis: bool = False,
        requires_comparison: bool = False,
    ) -> QueryMode:

        # 특정 상권 + 특정 업종 조합 → hybrid
        if has_specific_district and has_specific_industry:
            return QueryMode.HYBRID

        # 특정 상권만 지정 → local
        if has_specific_district and not requires_trend_analysis:
            return QueryMode.LOCAL

        # 트렌드/비교 분석 → global
        if requires_trend_analysis or requires_comparison:
            return QueryMode.GLOBAL

        # 특정 업종의 전국 트렌드 → global
        if has_specific_industry and not has_specific_district:
            return QueryMode.GLOBAL

        # 기본값 → hybrid (가장 범용적)
        return QueryMode.HYBRID
```

### 4.3 에이전트 쿼리 실행 흐름

```python
# agents/base_agent.py (LightRAG 연동 부분)

class BaseAnalysisAgent:
    """에이전트 기본 클래스의 LightRAG 연동"""

    async def retrieve_knowledge(
        self,
        district_name: str = "",
        industry_name: str = "",
    ) -> str:
        """분석 시작 전 LightRAG에서 배경 지식 검색

        Returns:
            검색된 지식 컨텍스트 문자열
        """
        agent_key = self.__class__.__name__.lower().replace("agent", "_agent")
        query_patterns = AGENT_QUERY_PATTERNS.get(agent_key, [])

        contexts = []
        for pattern in query_patterns:
            query = pattern.query_template.format(
                district_name=district_name,
                industry_name=industry_name,
            )

            try:
                result = await self.lightrag.query(
                    question=query,
                    mode=pattern.query_mode,
                    top_k=pattern.top_k,
                )

                # 결과가 빈약하면 fallback 모드로 재시도
                if len(result.strip()) < 50 and pattern.fallback_mode:
                    result = await self.lightrag.query(
                        question=query,
                        mode=pattern.fallback_mode,
                        top_k=pattern.top_k,
                    )

                if result.strip():
                    contexts.append(f"### {query}\n{result}")

            except Exception as e:
                logger.warning(f"LightRAG 쿼리 실패: {query}: {e}")

        return "\n\n".join(contexts)
```

---

## 5. 한국어 최적화

### 5.1 한국어 엔티티 추출 프롬프트

```python
# prompts/korean_entity_extraction.py

KOREAN_ENTITY_EXTRACTION_PROMPT = """
-목표-
주어진 텍스트에서 상권 분석 도메인의 엔티티와 관계를 추출하시오.

-단계-
1. 다음 엔티티 타입에 해당하는 모든 엔티티를 식별하시오:
   - 상권: 상업 활동이 집중된 특정 구역 (예: "강남역 상권", "홍대 상권")
   - 행정구역: 법정동/행정동/시군구 등 행정 단위 (예: "서초구 서초동", "마포구")
   - 업종: 사업의 종류나 분류 (예: "커피전문점", "한식음식점", "편의점")
   - 브랜드: 프랜차이즈 또는 특정 사업체 이름 (예: "스타벅스", "올리브영")
   - 시설: 상권에 영향을 미치는 건물이나 시설 (예: "코엑스", "서울대학교")
   - 교통: 교통 인프라 (예: "강남역 2호선", "서울역")
   - 개발사업: 진행 중이거나 계획된 개발 프로젝트 (예: "영동대로 복합환승센터")
   - 규제: 관련 법령이나 규제 (예: "심야영업 제한", "대규모점포 영업시간 규제")
   - 트렌드: 소비/시장 트렌드 (예: "1인 가구 증가", "배달 확대")
   - 리스크: 위험 요소 (예: "임대료 급등", "젠트리피케이션")

2. 각 엔티티에 대해 다음 정보를 추출하시오:
   - entity_name: 엔티티의 정식 한국어 명칭
   - entity_type: 위 10개 타입 중 하나
   - description: 텍스트에서 파악할 수 있는 엔티티 설명 (한국어)

3. 엔티티 간 관계를 식별하시오. 관계 타입:
   위치함, 인접함, 영향권_내, 업종_분류, 영업_중, 경쟁_관계,
   주요_업종, 대체_관계, 유동인구_증가_요인, 유동인구_감소_요인,
   매출_증가_요인, 매출_감소_요인, 임대료_상승_요인, 임대료_하락_요인,
   규제_적용, 규제_면제, 발전됨, 선행_사건, 유발, 리스크_유발,
   리스크_완화, 시너지, 계절성, 타겟_고객

4. 각 관계에 대해 다음 정보를 추출하시오:
   - source_entity: 관계의 출발 엔티티
   - target_entity: 관계의 도착 엔티티
   - relationship: 위 관계 타입 중 하나
   - relationship_description: 관계에 대한 구체적 설명 (한국어)
   - relationship_strength: 관계 강도 (0.0~1.0)

-주의사항-
- 한국어 고유명사(상권명, 행정동명, 브랜드명)는 원문 그대로 사용하시오.
- "OO역 상권"과 "OO역" 형태가 동시에 존재할 경우, 상권과 교통을 각각 별도 엔티티로 추출하시오.
- 복합 명칭(예: "강남역 2호선")은 분리하지 말고 하나의 엔티티로 유지하시오.
- 숫자 정보(매출액, 유동인구 수 등)는 엔티티 description에 포함시키시오.
- 암묵적 관계도 추출하시오 (예: "강남역 근처 커피전문점이 많다" → 커피전문점 -주요_업종→ 강남역 상권).

-출력 형식-
("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<description>)
("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship>{tuple_delimiter}<description>{tuple_delimiter}<strength>)
"""
```

### 5.2 bge-m3 한국어 구성

```python
# config/embedding_config.py

BGE_M3_CONFIG = {
    # 모델 기본 설정
    "model_name": "BAAI/bge-m3",
    "embedding_dim": 1024,
    "max_length": 8192,

    # 한국어 최적화 설정
    "use_fp16": True,                # GPU 메모리 절약
    "normalize_embeddings": True,     # 코사인 유사도를 위한 정규화
    "batch_size": 32,

    # bge-m3는 다국어(multilingual) 지원 모델로
    # 한국어에 대해 별도 토크나이저 설정 불필요.
    # XLM-RoBERTa 기반으로 한국어 토큰화를 내장 지원한다.
    #
    # 특장점:
    # - 1024차원 dense embedding (충분한 표현력)
    # - 한국어 조사, 어미 변화에 대한 자연스러운 처리
    # - 다국어 cross-lingual 검색 지원 (한국어 쿼리 → 영어 문서 매칭 가능)
}


class BGEm3EmbeddingService:
    """bge-m3 임베딩 서비스 (한국어 최적화)"""

    def __init__(self):
        self._model = None

    def _load_model(self):
        """모델 지연 로딩"""
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel
            import torch

            self._model = BGEM3FlagModel(
                BGE_M3_CONFIG["model_name"],
                use_fp16=BGE_M3_CONFIG["use_fp16"],
                device="cuda" if torch.cuda.is_available() else "cpu",
            )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 임베딩 생성"""
        model = self._load_model()

        embeddings = model.encode(
            texts,
            batch_size=BGE_M3_CONFIG["batch_size"],
            max_length=BGE_M3_CONFIG["max_length"],
        )["dense_vecs"]

        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """단일 쿼리 임베딩 (검색 시 사용)

        bge-m3는 쿼리에 "Represent this sentence for searching relevant passages:"
        prefix를 추가하면 검색 품질이 향상된다.
        단, 한국어 쿼리의 경우 prefix 없이도 충분한 성능을 보인다.
        """
        return self.embed([query])[0]
```

### 5.3 한국어 고유명사 처리

```python
# utils/korean_ner.py

import re
from typing import Optional


class KoreanProperNounHandler:
    """한국어 고유명사 정규화 및 처리

    상권명, 행정동명 등 한국어 고유명사의 일관된 처리를 위한 유틸리티.
    """

    # 상권명 정규화 패턴
    DISTRICT_PATTERNS = [
        # "강남역 상권" / "강남역상권" → "강남역 상권"
        (r"(\S+역)\s*상권", r"\1 상권"),
        # "OO동 상권" / "OO동상권" → "OO동 상권"
        (r"(\S+동)\s*상권", r"\1 상권"),
        # "홍대입구" / "홍대 입구" → "홍대입구"
        (r"홍대\s*입구", "홍대입구"),
    ]

    # 행정구역 정규화
    ADMIN_AREA_SUFFIXES = ["시", "도", "구", "군", "동", "읍", "면", "리"]

    # 지하철 노선 정규화
    SUBWAY_LINE_PATTERNS = {
        r"(\d)호선": r"\1호선",
        r"경의중앙": "경의중앙선",
        r"공항철도": "공항철도",
        r"신분당": "신분당선",
    }

    @classmethod
    def normalize_district_name(cls, name: str) -> str:
        """상권명 정규화"""
        result = name.strip()
        for pattern, replacement in cls.DISTRICT_PATTERNS:
            result = re.sub(pattern, replacement, result)

        # "상권" 접미어가 없으면 추가
        if not result.endswith("상권"):
            result = f"{result} 상권"

        return result

    @classmethod
    def normalize_admin_area(cls, name: str) -> str:
        """행정구역명 정규화"""
        result = name.strip()
        # 공백 정규화: "서초 구 서초 동" → "서초구 서초동"
        for suffix in cls.ADMIN_AREA_SUFFIXES:
            result = re.sub(rf"\s+({suffix})\b", rf"\1", result)
        return result

    @classmethod
    def extract_station_and_line(cls, text: str) -> list[dict]:
        """지하철역명과 노선 추출

        예: "강남역(2호선)" → [{"station": "강남역", "line": "2호선"}]
        예: "홍대입구역(2호선, 경의중앙선)" → [{"station": "홍대입구역", "line": "2호선"}, ...]
        """
        results = []
        pattern = r"(\S+역)\s*\(([^)]+)\)"
        for match in re.finditer(pattern, text):
            station = match.group(1)
            lines = [line.strip() for line in match.group(2).split(",")]
            for line in lines:
                results.append({"station": station, "line": line})
        return results

    @classmethod
    def is_korean_proper_noun(cls, text: str) -> bool:
        """한국어 고유명사 여부 판별 (간이)"""
        # 한글이 포함되어 있고, 2글자 이상이면 고유명사 후보
        if re.search(r"[가-힣]", text) and len(text) >= 2:
            return True
        return False

    @classmethod
    def deduplicate_entities(cls, entities: list[dict]) -> list[dict]:
        """동일 엔티티 중복 제거 (정규화 후 비교)

        예: "강남역상권"과 "강남역 상권"은 동일 엔티티로 병합
        """
        normalized_map = {}
        for entity in entities:
            name = entity.get("name", "")
            entity_type = entity.get("type", "")

            if entity_type == "상권":
                key = cls.normalize_district_name(name)
            elif entity_type == "행정구역":
                key = cls.normalize_admin_area(name)
            else:
                key = name.strip()

            full_key = f"{entity_type}::{key}"
            if full_key not in normalized_map:
                entity["name"] = key  # 정규화된 이름으로 교체
                normalized_map[full_key] = entity
            else:
                # 기존 엔티티의 description 보강
                existing = normalized_map[full_key]
                if len(entity.get("description", "")) > len(existing.get("description", "")):
                    existing["description"] = entity["description"]

        return list(normalized_map.values())
```

---

# Part 2: ReMe 메모리 시스템

## 6. 메모리 유형

### 6.1 개요

ReMe(Reflective Memory)는 에이전트가 분석 경험을 축적하고, 사용자 선호를 기억하며, API 호출을 최적화하기 위한 커스텀 메모리 서버이다.

```
┌──────────────────────────────────────────────┐
│                ReMe 메모리 서버                │
│                                              │
│  ┌─────────────┐ ┌──────────────┐ ┌────────┐ │
│  │ TaskMemory  │ │PersonalMemory│ │  Tool  │ │
│  │ (분석 교훈) │ │ (사용자 선호)│ │ Memory │ │
│  │             │ │              │ │(API캐시)│ │
│  └──────┬──────┘ └──────┬───────┘ └───┬────┘ │
│         │               │             │      │
│         └───────┬───────┘             │      │
│                 │                     │      │
│          ┌──────▼──────┐       ┌──────▼────┐ │
│          │   ChromaDB  │       │   Redis   │ │
│          │  (벡터검색) │       │  (TTL캐시)│ │
│          └─────────────┘       └───────────┘ │
└──────────────────────────────────────────────┘
```

### 6.2 TaskMemory - 분석 교훈 메모리

에이전트가 분석 과정에서 학습한 교훈을 저장하고, 유사한 분석 시 참고하는 메모리.

```python
# memory/task_memory.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class LessonType(Enum):
    """교훈 유형"""
    OVERESTIMATION = "과대평가"       # 특정 지표를 과대평가했던 경험
    UNDERESTIMATION = "과소평가"       # 특정 지표를 과소평가했던 경험
    DATA_TRAP = "데이터_함정"          # 데이터 해석 시 주의할 점
    DEBATE_INSIGHT = "토론_인사이트"   # 토론에서 결론이 바뀐 경험
    PATTERN_DISCOVERY = "패턴_발견"    # 새로운 패턴 발견
    METHODOLOGY = "방법론"             # 분석 방법론 개선


@dataclass
class TaskMemoryEntry:
    """TaskMemory 스키마"""

    # 필수 필드
    workspace_id: str              # 프로젝트/워크스페이스 식별자
    when_to_use: str               # 이 교훈을 언제 참고해야 하는지 (검색 키)
    content: str                   # 교훈 내용 (상세)
    score: float                   # 교훈 신뢰도/중요도 (0.0~1.0)

    # 메타데이터
    metadata: dict = field(default_factory=dict)
    # metadata 포함 항목:
    #   - district_name: str        # 관련 상권명
    #   - industry_name: str        # 관련 업종명
    #   - lesson_type: LessonType   # 교훈 유형
    #   - agent_name: str           # 교훈을 생성한 에이전트
    #   - analysis_id: str          # 원본 분석 ID
    #   - created_at: datetime      # 생성 시점
    #   - applied_count: int        # 참고된 횟수
    #   - last_applied_at: datetime # 마지막 참고 시점


# ===== 교훈 저장 예시 =====

TASK_MEMORY_EXAMPLES = [
    TaskMemoryEntry(
        workspace_id="ws_marketscope_prod",
        when_to_use="강남역 이면도로 상권 매출을 분석할 때",
        content=(
            "강남역 이면도로 상권의 매출을 분석할 때, 대로변 매출 데이터와 이면도로 매출 데이터를 "
            "구분하지 않으면 이면도로 매출을 20~30% 과대평가하게 된다. "
            "소상공인진흥공단 API의 상권 경계가 대로변을 포함하는 경우가 많으므로, "
            "실제 이면도로만의 매출을 추정하려면 대로변 점포를 필터링해야 한다."
        ),
        score=0.85,
        metadata={
            "district_name": "강남역 상권",
            "industry_name": "전체",
            "lesson_type": "과대평가",
            "agent_name": "RevenueAgent",
            "analysis_id": "analysis_20260115_001",
            "created_at": "2026-01-15T14:30:00",
            "applied_count": 3,
            "last_applied_at": "2026-03-01T10:00:00",
        },
    ),
    TaskMemoryEntry(
        workspace_id="ws_marketscope_prod",
        when_to_use="재개발 지역 주변 상권의 유동인구를 분석할 때",
        content=(
            "재개발 공사 중인 지역(예: 둔촌주공, 은마아파트 주변)의 유동인구 데이터에는 함정이 있다. "
            "공사 인부 유동인구가 포함되어 낮 시간대 유동인구가 실제 소비 유동인구보다 "
            "15~25% 과대 집계된다. 성별(남성 편향)과 연령대(30~50대 편향)를 함께 확인하여 "
            "공사 인부 유동인구를 보정해야 한다."
        ),
        score=0.90,
        metadata={
            "district_name": "",  # 범용 교훈
            "industry_name": "전체",
            "lesson_type": "데이터_함정",
            "agent_name": "PopulationAgent",
            "analysis_id": "analysis_20260210_003",
            "created_at": "2026-02-10T16:45:00",
            "applied_count": 5,
            "last_applied_at": "2026-03-10T09:30:00",
        },
    ),
    TaskMemoryEntry(
        workspace_id="ws_marketscope_prod",
        when_to_use="커피전문점 업종의 경쟁 분석을 할 때",
        content=(
            "커피전문점 경쟁 분석 시, 단순 점포 수 비교만으로는 경쟁 강도를 정확히 판단할 수 없다. "
            "토론에서 CompetitionAgent가 점포 수 기반으로 '과밀'이라 판단했으나, "
            "RevenueAgent의 반론으로 매출 데이터를 함께 보니 높은 매출을 유지하는 상권도 있었다. "
            "점포 수와 함께 점포당 매출, 폐업률, 영업 기간을 종합적으로 봐야 한다."
        ),
        score=0.88,
        metadata={
            "district_name": "",
            "industry_name": "커피전문점",
            "lesson_type": "토론_인사이트",
            "agent_name": "CommanderAgent",
            "analysis_id": "analysis_20260305_007",
            "created_at": "2026-03-05T11:20:00",
            "applied_count": 1,
            "last_applied_at": "2026-03-15T14:00:00",
        },
    ),
]
```

**저장 시점 (Trigger Conditions)**:

| 트리거 | 설명 | 자동/수동 |
|--------|------|----------|
| 분석 완료 후 회고 | 매 분석 종료 시 CommanderAgent가 교훈 추출 | 자동 |
| 토론에서 결론 변경 | 에이전트 간 토론에서 초기 판단이 뒤집힌 경우 | 자동 |
| 데이터 불일치 발견 | API 데이터와 실제 결과 간 큰 괴리 발견 시 | 자동 |
| 사용자 피드백 | 사용자가 분석 결과에 대해 수정 피드백을 준 경우 | 수동 |

**검색 방법 (Retrieval)**:

```python
# memory/task_memory_retrieval.py

class TaskMemoryRetrieval:
    """분석 시작 전 관련 교훈 검색"""

    def __init__(self, reme_client: ReMeClient):
        self.reme = reme_client

    async def retrieve_lessons(
        self,
        workspace_id: str,
        district_name: str = "",
        industry_name: str = "",
        analysis_type: str = "",
        top_k: int = 5,
    ) -> list[TaskMemoryEntry]:
        """관련 교훈 검색

        검색 전략:
        1. when_to_use 필드를 대상으로 시맨틱 검색
        2. metadata 필터링 (상권, 업종)
        3. score × recency 가중 정렬
        """
        # 쿼리 구성
        query = f"{district_name} {industry_name} {analysis_type} 분석 시 주의사항"

        # ReMe 검색 호출
        results = await self.reme.search_task_memory(
            workspace_id=workspace_id,
            query=query,
            filters={
                "district_name": district_name,
                "industry_name": industry_name,
            },
            top_k=top_k,
        )

        # 점수 기반 필터링 (score 0.5 이상만)
        filtered = [r for r in results if r.score >= 0.5]

        return filtered
```

### 6.3 PersonalMemory - 사용자 선호 메모리

```python
# memory/personal_memory.py

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PersonalMemoryEntry:
    """PersonalMemory 스키마"""

    # 필수 필드
    workspace_id: str              # 워크스페이스 식별자
    when_to_use: str               # 이 선호를 언제 적용해야 하는지
    content: str                   # 선호 내용
    target: str                    # 적용 대상 (user_id 또는 그룹)

    # 메타데이터
    metadata: dict = field(default_factory=dict)
    # metadata 포함 항목:
    #   - preference_type: str     # budget, industry, risk, format, region
    #   - created_at: datetime
    #   - updated_at: datetime
    #   - source: str              # user_explicit, inferred, feedback


# ===== 사용자 선호 유형 및 예시 =====

PREFERENCE_TYPES = {
    "budget": {
        "description": "예산 관련 선호",
        "examples": [
            PersonalMemoryEntry(
                workspace_id="ws_user_001",
                when_to_use="사용자의 투자 예산 범위를 고려할 때",
                content="사용자는 보증금 5천만원, 월세 300만원 이하의 점포를 선호한다. 강남/서초 지역은 예외적으로 월세 500만원까지 수용 가능하다.",
                target="user_001",
                metadata={"preference_type": "budget", "source": "user_explicit"},
            ),
        ],
    },
    "industry": {
        "description": "관심 업종 선호",
        "examples": [
            PersonalMemoryEntry(
                workspace_id="ws_user_001",
                when_to_use="업종 추천이나 업종 분석 우선순위를 정할 때",
                content="사용자는 F&B 업종(카페, 베이커리, 브런치)에 관심이 높으며, 주류 업종은 기피한다. 특히 디저트 카페에 대한 관심이 가장 높다.",
                target="user_001",
                metadata={"preference_type": "industry", "source": "inferred"},
            ),
        ],
    },
    "risk_tolerance": {
        "description": "리스크 허용도",
        "examples": [
            PersonalMemoryEntry(
                workspace_id="ws_user_001",
                when_to_use="리스크 평가 및 추천 시 가중치 결정할 때",
                content="사용자는 보수적 투자 성향이다. 폐업률 10% 이상인 상권은 경고를 표시해야 하며, 재개발 예정 지역은 추천에서 제외해야 한다.",
                target="user_001",
                metadata={"preference_type": "risk_tolerance", "source": "user_explicit"},
            ),
        ],
    },
    "report_format": {
        "description": "보고서 형식 선호",
        "examples": [
            PersonalMemoryEntry(
                workspace_id="ws_user_001",
                when_to_use="분석 결과를 사용자에게 제시할 때",
                content="사용자는 데이터 시각화(차트, 지도)를 선호하며, 숫자 요약보다 인사이트 중심의 설명을 원한다. 보고서 길이는 A4 3페이지 이내를 선호한다.",
                target="user_001",
                metadata={"preference_type": "format", "source": "feedback"},
            ),
        ],
    },
    "region": {
        "description": "관심 지역 선호",
        "examples": [
            PersonalMemoryEntry(
                workspace_id="ws_user_001",
                when_to_use="분석 대상 지역을 선정하거나 비교 지역을 추천할 때",
                content="사용자는 서울 강남권(강남구, 서초구, 송파구)을 주요 관심 지역으로 두고 있다. 비교 분석 시 성수동, 한남동도 관심 있다.",
                target="user_001",
                metadata={"preference_type": "region", "source": "inferred"},
            ),
        ],
    },
}


class PersonalMemoryManager:
    """사용자 선호 메모리 관리"""

    def __init__(self, reme_client):
        self.reme = reme_client

    async def save_preference(self, entry: PersonalMemoryEntry) -> None:
        """사용자 선호 저장"""
        await self.reme.save_personal_memory(
            workspace_id=entry.workspace_id,
            when_to_use=entry.when_to_use,
            content=entry.content,
            target=entry.target,
            metadata=entry.metadata,
        )

    async def get_user_context(self, workspace_id: str, user_id: str) -> str:
        """사용자의 전체 선호 컨텍스트를 문자열로 반환

        CommanderAgent가 분석 계획 수립 시 이 컨텍스트를 포함한다.
        """
        preferences = await self.reme.search_personal_memory(
            workspace_id=workspace_id,
            target=user_id,
            top_k=20,
        )

        if not preferences:
            return "사용자 선호 정보 없음 (기본 설정 사용)"

        sections = []
        for pref in preferences:
            sections.append(f"- [{pref.metadata.get('preference_type', 'general')}] {pref.content}")

        return "### 사용자 선호 정보\n" + "\n".join(sections)

    async def infer_and_save(
        self,
        workspace_id: str,
        user_id: str,
        interaction_log: str,
    ) -> Optional[PersonalMemoryEntry]:
        """사용자 상호작용에서 선호를 추론하여 저장

        분석 요청이나 피드백에서 암묵적 선호를 추출한다.
        예: "강남역 근처 카페 창업 분석해줘" → 지역: 강남역, 업종: 카페
        """
        # LLM을 사용하여 선호 추론 (별도 프롬프트)
        # 추론 결과가 기존 선호와 충돌하면 최신 것을 우선
        pass  # 구현 예정
```

### 6.4 ToolMemory - API 호출 최적화

```python
# memory/tool_memory.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
import hashlib
import json


@dataclass
class ToolMemoryEntry:
    """ToolMemory 스키마"""

    # 필수 필드
    when_to_use: str                # 이 캐시를 언제 사용해야 하는지
    tool_call_results: dict         # API 호출 결과

    # 메타데이터
    metadata: dict = field(default_factory=dict)
    # metadata 포함 항목:
    #   - tool_name: str            # API/Tool 이름
    #   - call_params_hash: str     # 호출 파라미터 해시
    #   - district_name: str
    #   - industry_name: str
    #   - quarter: str              # "2026Q1" 형태
    #   - cached_at: datetime
    #   - expires_at: datetime
    #   - data_freshness: str       # fresh, stale, expired


# ===== 캐싱 로직 =====

class ToolMemoryCache:
    """API 호출 결과 캐싱 (ReMe ToolMemory 기반)"""

    # 데이터 유형별 유효 기간
    FRESHNESS_RULES = {
        "district_profile": timedelta(days=90),     # 상권 프로필: 분기
        "population_data": timedelta(days=90),       # 유동인구: 분기
        "revenue_data": timedelta(days=90),          # 매출 데이터: 분기
        "competition_data": timedelta(days=30),      # 경쟁 데이터: 월간
        "rent_data": timedelta(days=90),             # 임대료: 분기
        "news_data": timedelta(days=7),              # 뉴스: 주간
        "trend_data": timedelta(days=30),            # 트렌드: 월간
        "regulation_data": timedelta(days=90),       # 규제: 분기
        "geocoding": timedelta(days=365),            # 지오코딩: 연간
        "poi_data": timedelta(days=30),              # POI: 월간
    }

    def __init__(self, reme_client):
        self.reme = reme_client

    def _make_cache_key(self, tool_name: str, params: dict) -> str:
        """캐시 키 생성

        동일 상권 + 동일 업종 + 동일 분기 → 동일 캐시 키
        """
        # 분기 정보 추가
        current_quarter = self._get_current_quarter()
        key_data = {
            "tool": tool_name,
            "params": params,
            "quarter": current_quarter,
        }
        serialized = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _get_current_quarter(self) -> str:
        """현재 분기 문자열 반환"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}Q{quarter}"

    async def get_or_call(
        self,
        tool_name: str,
        params: dict,
        api_call_func,
        data_type: str = "district_profile",
    ) -> dict:
        """캐시에서 조회하고, 없거나 만료 시 API 호출

        Args:
            tool_name: 도구/API 이름
            params: 호출 파라미터
            api_call_func: 실제 API 호출 함수
            data_type: 데이터 유형 (유효기간 결정에 사용)

        Returns:
            API 호출 결과 (캐시 또는 신규)
        """
        cache_key = self._make_cache_key(tool_name, params)

        # 1. 캐시 조회
        cached = await self.reme.search_tool_memory(
            when_to_use=cache_key,
            top_k=1,
        )

        if cached:
            entry = cached[0]
            freshness = self._check_freshness(entry, data_type)

            if freshness == "fresh":
                return entry.tool_call_results

            if freshness == "stale":
                # 사용 가능하지만 백그라운드에서 갱신 예약
                self._schedule_refresh(tool_name, params, api_call_func, data_type)
                return entry.tool_call_results

            # expired: 새로 호출 필요

        # 2. API 호출
        result = await api_call_func(**params)

        # 3. 캐시 저장
        freshness_duration = self.FRESHNESS_RULES.get(data_type, timedelta(days=30))
        await self.reme.save_tool_memory(
            when_to_use=cache_key,
            tool_call_results=result,
            metadata={
                "tool_name": tool_name,
                "call_params_hash": cache_key,
                "district_name": params.get("district_name", ""),
                "industry_name": params.get("industry_name", ""),
                "quarter": self._get_current_quarter(),
                "cached_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + freshness_duration).isoformat(),
                "data_freshness": "fresh",
            },
        )

        return result

    def _check_freshness(self, entry: ToolMemoryEntry, data_type: str) -> str:
        """데이터 신선도 판별

        Returns:
            "fresh": 유효기간 내
            "stale": 유효기간 50%~100% (사용 가능하지만 갱신 권장)
            "expired": 유효기간 초과 (재호출 필요)
        """
        cached_at = datetime.fromisoformat(entry.metadata.get("cached_at", ""))
        freshness_duration = self.FRESHNESS_RULES.get(data_type, timedelta(days=30))
        age = datetime.now() - cached_at

        if age < freshness_duration * 0.5:
            return "fresh"
        elif age < freshness_duration:
            return "stale"
        else:
            return "expired"

    def _schedule_refresh(self, tool_name, params, api_call_func, data_type):
        """백그라운드 갱신 예약 (비동기)"""
        import asyncio
        asyncio.create_task(
            self.get_or_call(tool_name, params, api_call_func, data_type)
        )
```

---

## 7. ReMe 통합 아키텍처

### 7.1 ReMe HTTP API 엔드포인트

```python
# ReMe 서버는 별도 프로세스로 실행되며 HTTP API를 통해 통신

REME_API_ENDPOINTS = {
    "base_url": "http://localhost:8100",

    # ── TaskMemory ──
    "POST /task-memory": {
        "description": "분석 교훈 저장",
        "request_body": {
            "workspace_id": "string (required)",
            "when_to_use": "string (required) - 검색 키",
            "content": "string (required) - 교훈 내용",
            "score": "float (0.0~1.0)",
            "metadata": "object (optional)",
        },
        "response": {"id": "string", "status": "created"},
    },
    "POST /task-memory/search": {
        "description": "관련 교훈 검색",
        "request_body": {
            "workspace_id": "string (required)",
            "query": "string (required) - 시맨틱 검색 쿼리",
            "filters": "object (optional) - 메타데이터 필터",
            "top_k": "int (default: 5)",
        },
        "response": [
            {
                "id": "string",
                "when_to_use": "string",
                "content": "string",
                "score": "float",
                "similarity": "float - 쿼리와의 유사도",
                "metadata": "object",
            }
        ],
    },
    "PATCH /task-memory/{id}": {
        "description": "교훈 업데이트 (점수 조정, 적용 횟수 증가 등)",
        "request_body": {
            "score": "float (optional)",
            "metadata": "object (optional) - 병합됨",
        },
    },
    "DELETE /task-memory/{id}": {
        "description": "교훈 삭제 (더 이상 유효하지 않은 경우)",
    },

    # ── PersonalMemory ──
    "POST /personal-memory": {
        "description": "사용자 선호 저장",
        "request_body": {
            "workspace_id": "string (required)",
            "when_to_use": "string (required)",
            "content": "string (required)",
            "target": "string (required) - user_id",
            "metadata": "object (optional)",
        },
    },
    "POST /personal-memory/search": {
        "description": "사용자 선호 검색",
        "request_body": {
            "workspace_id": "string (required)",
            "target": "string (required) - user_id",
            "query": "string (optional) - 특정 상황에 맞는 선호 검색",
            "top_k": "int (default: 10)",
        },
    },

    # ── ToolMemory ──
    "POST /tool-memory": {
        "description": "API 호출 결과 캐싱",
        "request_body": {
            "when_to_use": "string (required) - 캐시 키",
            "tool_call_results": "object (required) - API 응답",
            "metadata": "object (optional)",
        },
    },
    "POST /tool-memory/search": {
        "description": "캐시된 API 결과 검색",
        "request_body": {
            "when_to_use": "string (required) - 캐시 키",
            "top_k": "int (default: 1)",
        },
    },
    "DELETE /tool-memory/{id}": {
        "description": "캐시 무효화",
    },
}
```

### 7.2 ReMe 클라이언트

```python
# clients/reme_client.py

import httpx
from typing import Any, Optional


class ReMeClient:
    """ReMe 메모리 서버 HTTP 클라이언트"""

    def __init__(self, base_url: str = "http://localhost:8100"):
        self.base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    # ── TaskMemory ──

    async def save_task_memory(
        self,
        workspace_id: str,
        when_to_use: str,
        content: str,
        score: float = 0.7,
        metadata: dict = None,
    ) -> dict:
        """분석 교훈 저장"""
        response = await self._client.post(
            "/task-memory",
            json={
                "workspace_id": workspace_id,
                "when_to_use": when_to_use,
                "content": content,
                "score": score,
                "metadata": metadata or {},
            },
        )
        response.raise_for_status()
        return response.json()

    async def search_task_memory(
        self,
        workspace_id: str,
        query: str,
        filters: dict = None,
        top_k: int = 5,
    ) -> list[dict]:
        """관련 교훈 검색"""
        response = await self._client.post(
            "/task-memory/search",
            json={
                "workspace_id": workspace_id,
                "query": query,
                "filters": filters or {},
                "top_k": top_k,
            },
        )
        response.raise_for_status()
        return response.json()

    async def update_task_memory(self, memory_id: str, **kwargs) -> dict:
        """교훈 업데이트"""
        response = await self._client.patch(
            f"/task-memory/{memory_id}",
            json=kwargs,
        )
        response.raise_for_status()
        return response.json()

    # ── PersonalMemory ──

    async def save_personal_memory(
        self,
        workspace_id: str,
        when_to_use: str,
        content: str,
        target: str,
        metadata: dict = None,
    ) -> dict:
        """사용자 선호 저장"""
        response = await self._client.post(
            "/personal-memory",
            json={
                "workspace_id": workspace_id,
                "when_to_use": when_to_use,
                "content": content,
                "target": target,
                "metadata": metadata or {},
            },
        )
        response.raise_for_status()
        return response.json()

    async def search_personal_memory(
        self,
        workspace_id: str,
        target: str,
        query: str = "",
        top_k: int = 10,
    ) -> list[dict]:
        """사용자 선호 검색"""
        response = await self._client.post(
            "/personal-memory/search",
            json={
                "workspace_id": workspace_id,
                "target": target,
                "query": query,
                "top_k": top_k,
            },
        )
        response.raise_for_status()
        return response.json()

    # ── ToolMemory ──

    async def save_tool_memory(
        self,
        when_to_use: str,
        tool_call_results: dict,
        metadata: dict = None,
    ) -> dict:
        """API 호출 결과 캐싱"""
        response = await self._client.post(
            "/tool-memory",
            json={
                "when_to_use": when_to_use,
                "tool_call_results": tool_call_results,
                "metadata": metadata or {},
            },
        )
        response.raise_for_status()
        return response.json()

    async def search_tool_memory(
        self,
        when_to_use: str,
        top_k: int = 1,
    ) -> list[dict]:
        """캐시된 API 결과 검색"""
        response = await self._client.post(
            "/tool-memory/search",
            json={
                "when_to_use": when_to_use,
                "top_k": top_k,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """클라이언트 종료"""
        await self._client.aclose()
```

### 7.3 에이전트 워크플로우 내 메모리 통합

```python
# agents/memory_aware_agent.py

class MemoryAwareAnalysisAgent(BaseAnalysisAgent):
    """메모리 시스템이 통합된 분석 에이전트 기본 클래스

    에이전트 실행 흐름:
    1. [사전 검색] ReMe TaskMemory에서 관련 교훈 검색
    2. [사전 검색] LightRAG에서 배경 지식 검색
    3. [사전 검색] ReMe PersonalMemory에서 사용자 선호 검색 (Commander만)
    4. [분석 실행] 검색된 컨텍스트를 포함하여 분석 수행
    5. [결과 캐싱] ReMe ToolMemory에 API 호출 결과 캐싱
    6. [교훈 저장] 분석 결과에서 교훈 추출 후 TaskMemory에 저장
    7. [지식 동기화] 중요한 교훈은 LightRAG에도 반영
    """

    async def run_analysis(
        self,
        district_name: str,
        industry_name: str,
        user_id: str = "",
    ) -> dict:
        # ── Phase 1: 컨텍스트 수집 ──

        # 1. 관련 교훈 검색
        lessons = await self.task_memory_retrieval.retrieve_lessons(
            workspace_id=self.workspace_id,
            district_name=district_name,
            industry_name=industry_name,
            analysis_type=self.agent_type,
        )
        lesson_context = self._format_lessons(lessons)

        # 2. 배경 지식 검색 (LightRAG)
        knowledge_context = await self.retrieve_knowledge(
            district_name=district_name,
            industry_name=industry_name,
        )

        # ── Phase 2: 분석 실행 ──

        analysis_result = await self._execute_analysis(
            district_name=district_name,
            industry_name=industry_name,
            extra_context=f"{lesson_context}\n\n{knowledge_context}",
        )

        # ── Phase 3: 사후 처리 ──

        # 3. 교훈 추출 및 저장
        await self._extract_and_save_lessons(analysis_result)

        return analysis_result

    def _format_lessons(self, lessons: list) -> str:
        """검색된 교훈을 프롬프트 컨텍스트 형태로 포맷"""
        if not lessons:
            return ""

        lines = ["### 과거 분석 교훈 (참고)"]
        for i, lesson in enumerate(lessons, 1):
            lines.append(
                f"{i}. [신뢰도 {lesson.score:.0%}] {lesson.content}"
            )
        return "\n".join(lines)

    async def _extract_and_save_lessons(self, analysis_result: dict) -> None:
        """분석 결과에서 교훈 추출 및 저장"""
        # LLM을 사용하여 분석 결과에서 교훈 추출
        # 교훈이 있으면 TaskMemory에 저장
        # 중요도가 높은 교훈(score >= 0.8)은 LightRAG에도 반영
        pass  # 구현 예정
```

---

# Part 3: 공유 인프라

## 8. ChromaDB 구성

### 8.1 컬렉션 설계

```python
# config/chromadb_config.py

import chromadb
from chromadb.config import Settings


CHROMADB_CONFIG = {
    "host": "localhost",
    "port": 8000,
    "settings": Settings(
        anonymized_telemetry=False,
        allow_reset=False,
        is_persistent=True,
        persist_directory="./data/chromadb",
    ),
}


# 컬렉션 정의
COLLECTIONS = {
    "district_knowledge": {
        "description": "상권 프로필 및 분석 데이터 (LightRAG 벡터 스토어)",
        "embedding_model": "BAAI/bge-m3",
        "embedding_dim": 1024,
        "distance_metric": "cosine",
        "metadata_schema": {
            "source": "string",           # 데이터 소스 (semas, seoul_data, etc.)
            "district_name": "string",     # 상권명
            "district_code": "string",     # 상권 코드
            "data_type": "string",         # profile, industry, transport
            "quarter": "string",           # 2026Q1
            "loaded_at": "string",         # ISO 8601
        },
        "estimated_docs": 50000,
    },

    "news_articles": {
        "description": "상권 관련 뉴스 기사",
        "embedding_model": "BAAI/bge-m3",
        "embedding_dim": 1024,
        "distance_metric": "cosine",
        "metadata_schema": {
            "source": "string",            # 뉴스 출처
            "published_at": "string",      # 발행일
            "districts": "string",         # 관련 상권 (comma separated)
            "industries": "string",        # 관련 업종 (comma separated)
            "keywords": "string",          # 키워드 (comma separated)
            "sentiment": "string",         # positive, negative, neutral
        },
        "estimated_docs": 100000,
    },

    "legal_texts": {
        "description": "법령 및 규제 문서",
        "embedding_model": "BAAI/bge-m3",
        "embedding_dim": 1024,
        "distance_metric": "cosine",
        "metadata_schema": {
            "law_name": "string",          # 법령명
            "regulation_type": "string",   # 영업시간, 허가, 위생, 건축, 세금
            "effective_date": "string",    # 시행일
            "target_industries": "string", # 적용 업종
            "target_regions": "string",    # 적용 지역
        },
        "estimated_docs": 5000,
    },

    "analysis_lessons": {
        "description": "분석 교훈 (ReMe TaskMemory 미러링)",
        "embedding_model": "BAAI/bge-m3",
        "embedding_dim": 1024,
        "distance_metric": "cosine",
        "metadata_schema": {
            "workspace_id": "string",
            "lesson_type": "string",       # 교훈 유형
            "district_name": "string",
            "industry_name": "string",
            "agent_name": "string",
            "score": "float",
            "created_at": "string",
        },
        "estimated_docs": 10000,
    },
}


class ChromaDBService:
    """ChromaDB 서비스 (컬렉션 관리)"""

    def __init__(self):
        self.client = chromadb.HttpClient(
            host=CHROMADB_CONFIG["host"],
            port=CHROMADB_CONFIG["port"],
            settings=CHROMADB_CONFIG["settings"],
        )
        self._collections = {}

    def get_collection(self, name: str):
        """컬렉션 인스턴스 반환 (없으면 생성)"""
        if name not in self._collections:
            collection_config = COLLECTIONS.get(name)
            if not collection_config:
                raise ValueError(f"Unknown collection: {name}")

            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={
                    "hnsw:space": collection_config["distance_metric"],
                    "hnsw:M": 16,                # HNSW 그래프 연결 수
                    "hnsw:construction_ef": 200,  # 구축 시 탐색 범위
                    "hnsw:search_ef": 100,        # 검색 시 탐색 범위
                },
            )
        return self._collections[name]
```

### 8.2 메타데이터 필터링 패턴

```python
# services/chromadb_query_patterns.py

class ChromaDBQueryPatterns:
    """ChromaDB 메타데이터 필터링 패턴"""

    @staticmethod
    def filter_by_district(district_name: str) -> dict:
        """특정 상권 필터"""
        return {"district_name": {"$eq": district_name}}

    @staticmethod
    def filter_by_district_and_quarter(district_name: str, quarter: str) -> dict:
        """상권 + 분기 필터"""
        return {
            "$and": [
                {"district_name": {"$eq": district_name}},
                {"quarter": {"$eq": quarter}},
            ]
        }

    @staticmethod
    def filter_recent_news(district_name: str, days: int = 30) -> dict:
        """최근 N일간 뉴스 필터"""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return {
            "$and": [
                {"districts": {"$contains": district_name}},
                {"published_at": {"$gte": cutoff}},
            ]
        }

    @staticmethod
    def filter_by_regulation_type(regulation_type: str, industry: str = "") -> dict:
        """규제 유형 필터"""
        conditions = [{"regulation_type": {"$eq": regulation_type}}]
        if industry:
            conditions.append({"target_industries": {"$contains": industry}})
        return {"$and": conditions} if len(conditions) > 1 else conditions[0]

    @staticmethod
    def filter_high_score_lessons(min_score: float = 0.7) -> dict:
        """고점수 교훈 필터"""
        return {"score": {"$gte": min_score}}
```

---

## 9. Redis 캐싱 레이어

### 9.1 캐시 키 패턴

```python
# config/redis_config.py

import redis.asyncio as redis
from typing import Optional
from datetime import timedelta


REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": None,  # 환경변수에서 로드
    "decode_responses": True,
    "max_connections": 20,
}


# 캐시 키 패턴 및 TTL 전략
CACHE_KEY_PATTERNS = {
    # ── 지오코딩 캐시 ──
    "geocoding": {
        "pattern": "geo:{address_hash}",
        "ttl": timedelta(days=30),
        "description": "주소 → 좌표 변환 결과",
        "example": "geo:sha256_of_서울시_강남구_역삼동_123",
    },

    # ── POI (Point of Interest) 캐시 ──
    "poi": {
        "pattern": "poi:{district_code}:{category}",
        "ttl": timedelta(days=7),
        "description": "상권 내 주요 시설/교통 POI 목록",
        "example": "poi:A_12345:교통",
    },

    # ── 뉴스 캐시 ──
    "news": {
        "pattern": "news:{keyword_hash}:{date}",
        "ttl": timedelta(hours=24),
        "description": "키워드 기반 뉴스 검색 결과",
        "example": "news:sha256_of_강남역_상권:20260319",
    },

    # ── 트렌드 캐시 ──
    "trends": {
        "pattern": "trend:{industry_code}:{region_code}",
        "ttl": timedelta(hours=24),
        "description": "업종별 트렌드 데이터",
        "example": "trend:Q12101:11680",
    },

    # ── 법령/규제 캐시 ──
    "legal": {
        "pattern": "legal:{law_code}:{version}",
        "ttl": timedelta(days=30),
        "description": "법령 조문 내용",
        "example": "legal:1234567:20260101",
    },

    # ── 상권 프로필 캐시 ──
    "district_profile": {
        "pattern": "district:{district_code}:{quarter}",
        "ttl": timedelta(days=90),
        "description": "상권 프로필 전체 데이터",
        "example": "district:A_12345:2026Q1",
    },

    # ── 유동인구 캐시 ──
    "population": {
        "pattern": "pop:{district_code}:{quarter}",
        "ttl": timedelta(days=90),
        "description": "유동인구 상세 데이터",
        "example": "pop:A_12345:2026Q1",
    },

    # ── 매출 캐시 ──
    "revenue": {
        "pattern": "rev:{district_code}:{industry_code}:{quarter}",
        "ttl": timedelta(days=90),
        "description": "업종별 매출 데이터",
        "example": "rev:A_12345:Q12101:2026Q1",
    },

    # ── LightRAG 쿼리 캐시 ──
    "lightrag_query": {
        "pattern": "lrag:{query_hash}:{mode}",
        "ttl": timedelta(hours=6),
        "description": "LightRAG 쿼리 결과 캐시 (동일 쿼리 반복 방지)",
        "example": "lrag:sha256_of_query:hybrid",
    },

    # ── 분석 결과 캐시 ──
    "analysis_result": {
        "pattern": "analysis:{analysis_id}",
        "ttl": timedelta(days=7),
        "description": "완료된 분석 결과 전체",
        "example": "analysis:analysis_20260319_001",
    },
}
```

### 9.2 TTL 전략 요약

| 데이터 유형 | TTL | 근거 |
|------------|-----|------|
| **지오코딩** | 30일 | 주소/좌표 데이터는 거의 변하지 않음 |
| **POI** | 7일 | 점포 개폐업으로 변동 가능 |
| **뉴스** | 24시간 | 뉴스의 시의성, 매일 새 기사 발행 |
| **트렌드** | 24시간 | 실시간 트렌드 반영 필요 |
| **법령** | 30일 | 법령 개정은 드물지만 중요 |
| **상권 프로필** | 90일 | 분기별 데이터 갱신 주기에 맞춤 |
| **유동인구** | 90일 | 분기별 공공 데이터 갱신 주기 |
| **매출** | 90일 | 분기별 공공 데이터 갱신 주기 |
| **LightRAG 쿼리** | 6시간 | 지식 그래프 갱신 빈도 대비 적절한 캐시 |
| **분석 결과** | 7일 | 동일 분석 재요청 시 재활용 |

### 9.3 캐시 무효화 트리거

```python
# services/cache_invalidation.py

class CacheInvalidationService:
    """캐시 무효화 관리"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def invalidate_by_pattern(self, pattern: str) -> int:
        """패턴 기반 캐시 무효화

        예: "district:A_12345:*" → 특정 상권의 모든 분기 캐시 삭제
        """
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            await self.redis.delete(*keys)
        return len(keys)

    async def invalidate_on_data_load(self, data_type: str, district_code: str = "") -> None:
        """데이터 로딩 완료 시 관련 캐시 무효화"""
        invalidation_map = {
            "district_profiles": [
                f"district:{district_code}:*" if district_code else "district:*",
                f"pop:{district_code}:*" if district_code else "pop:*",
                f"rev:{district_code}:*" if district_code else "rev:*",
                "lrag:*",  # LightRAG 쿼리 캐시도 무효화
            ],
            "news_articles": [
                "news:*",
                "lrag:*",
            ],
            "regulations": [
                "legal:*",
                "lrag:*",
            ],
        }

        patterns = invalidation_map.get(data_type, [])
        for pattern in patterns:
            await self.invalidate_by_pattern(pattern)

    async def invalidate_on_quarter_change(self) -> None:
        """분기 변경 시 전체 분기 관련 캐시 무효화"""
        patterns = ["district:*", "pop:*", "rev:*", "trend:*"]
        for pattern in patterns:
            await self.invalidate_by_pattern(pattern)
```

---

## 10. 데이터 흐름도

### 10.1 전체 데이터 흐름

```
┌─────────────────────────────────────────────────────────────────────┐
│                        에이전트 분석 요청                             │
│  "강남역 상권에서 커피전문점 창업 분석해줘"                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CommanderAgent (총괄)                            │
│                                                                     │
│  1. 사용자 선호 조회 (ReMe PersonalMemory)                            │
│  2. 분석 계획 수립                                                    │
│  3. 하위 에이전트 분석 요청 배분                                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
       PopulationAgent  RevenueAgent  CompetitionAgent  ... (9개)
              │              │              │
              │              │              │
              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    데이터 조회 흐름 (각 에이전트 공통)                   │
│                                                                     │
│  ┌─────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐ │
│  │ Step 1  │    │  Step 2    │    │  Step 3    │    │  Step 4    │ │
│  │ Redis   │───▶│ LightRAG   │───▶│ PostgreSQL │───▶│ MCP/API    │ │
│  │ Cache   │    │ Knowledge  │    │ Database   │    │ External   │ │
│  │ Check   │    │ Graph      │    │ Query      │    │ Call       │ │
│  └────┬────┘    └─────┬──────┘    └─────┬──────┘    └─────┬──────┘ │
│       │               │                 │                  │        │
│  Hit? │          검색결과           기존 데이터          신규 데이터   │
│   │   │               │                 │                  │        │
│   │   ▼               ▼                 ▼                  │        │
│   │  캐시 반환    컨텍스트 보강       데이터 반환            │        │
│   │                                                        │        │
│   │  Miss?                                                 │        │
│   │   │                                                    │        │
│   │   ▼                                                    ▼        │
│   │  다음 단계로 진행                                  ┌──────────┐ │
│   │                                                    │ Step 5   │ │
│   │                                                    │ Cache    │ │
│   │◀───────────────────────────────────────────────────│ Write    │ │
│   │                                                    │(Redis +  │ │
│   │                                                    │ ReMe TM) │ │
│   │                                                    └──────────┘ │
└───┼─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ReMe TaskMemory 조회                           │
│                                                                     │
│  분석 시작 전: "강남역 커피전문점 분석 시 주의사항" 검색                 │
│  → "강남역 이면도로 매출 과대평가 경험" 교훈 반환                       │
│  → 분석 컨텍스트에 포함                                               │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        분석 실행 및 토론                              │
│                                                                     │
│  각 에이전트가 수집된 데이터 + 지식 + 교훈을 기반으로 분석 수행          │
│  → 에이전트 간 토론 (다중 관점 검증)                                    │
│  → 결론 도출                                                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        사후 처리                                     │
│                                                                     │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────────────┐ │
│  │교훈 추출   │  │ ToolMemory   │  │ LightRAG 교훈 동기화         │ │
│  │→ ReMe TM   │  │ 캐싱 갱신     │  │ (score >= 0.8인 교훈만)     │ │
│  │저장         │  │              │  │                             │ │
│  └────────────┘  └──────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 단계별 상세 흐름

```
[에이전트 쿼리 발생]
        │
        ▼
   ┌─────────┐
   │ Redis   │──── Hit ───▶ 캐시된 결과 반환 (최대 성능)
   │ Cache   │
   └────┬────┘
        │ Miss
        ▼
   ┌──────────┐
   │ ReMe     │──── 캐시 Hit ───▶ ToolMemory 결과 반환
   │ ToolMem  │     (freshness check)
   └────┬─────┘
        │ Miss or Expired
        ▼
   ┌──────────┐
   │ LightRAG │──── 지식 그래프 검색 ───▶ 관련 엔티티/관계 컨텍스트
   │ Query    │     (hybrid mode)
   └────┬─────┘
        │ 데이터가 부족하면
        ▼
   ┌───────────┐
   │PostgreSQL │──── 구조화 데이터 조회 ───▶ 기존 저장된 정형 데이터
   │  Query    │
   └────┬──────┘
        │ 데이터가 없으면
        ▼
   ┌──────────┐
   │ MCP API  │──── 외부 API 호출 ───▶ 신규 데이터 획득
   │ Call     │     (소상공인진흥공단, 서울열린데이터 등)
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │ Cache    │──── Redis에 캐싱 (TTL 적용)
   │ Write    │──── ReMe ToolMemory에 저장
   └────┬─────┘
        │
        ▼
   [에이전트에 결과 반환]
```

### 10.3 메모리 시스템 간 데이터 동기화

```
┌──────────────────────────────────────────────────────────┐
│                  데이터 동기화 흐름                         │
│                                                          │
│  ReMe TaskMemory ─── score >= 0.8 ──▶ LightRAG          │
│  (분석 교훈)          교훈 반영          (지식 그래프)       │
│                                                          │
│  LightRAG ────── 증분 업데이트 ──▶ ChromaDB               │
│  (엔티티 추출)    벡터 저장            (벡터 인덱스)         │
│                                                          │
│  외부 API ────── 로딩 파이프라인 ──▶ LightRAG + PostgreSQL │
│  (공공데이터)     텍스트 변환          (지식 + 정형)         │
│                                                          │
│  Redis ◀──────── TTL 만료 ──────── 자동 삭제              │
│  (캐시)                                                   │
│                                                          │
│  ReMe ToolMem ── freshness ──▶ 만료 시 API 재호출          │
│  (API 캐시)       체크                                     │
└──────────────────────────────────────────────────────────┘
```

---

## 부록 A: 환경 변수

```bash
# .env.example

# ── LightRAG ──
GOOGLE_API_KEY=your_gemini_api_key
LIGHTRAG_WORKING_DIR=./data/lightrag

# ── ChromaDB ──
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# ── Neo4j (Phase 2+) ──
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# ── Redis ──
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# ── ReMe ──
REME_BASE_URL=http://localhost:8100

# ── PostgreSQL ──
DATABASE_URL=postgresql://user:password@localhost:5432/marketscope

# ── Embedding Model ──
BGE_M3_DEVICE=cuda  # or cpu
BGE_M3_CACHE_DIR=./models/bge-m3
```

## 부록 B: 의존성

```
# requirements-memory.txt

lightrag-hku>=0.1.0
chromadb>=0.5.0
FlagEmbedding>=1.2.0
redis[asyncio]>=5.0.0
httpx>=0.27.0
networkx>=3.3
torch>=2.0.0
google-generativeai>=0.8.0
psycopg[binary]>=3.1.0
```

## 부록 C: 마이그레이션 체크리스트

### Phase 1 → Phase 2 (NetworkX → Neo4j)

- [ ] Neo4j 서버 설치 및 구성
- [ ] LightRAG 설정에서 `graph_storage`를 `Neo4JStorage`로 변경
- [ ] NetworkX 그래프 데이터를 Neo4j로 마이그레이션하는 스크립트 작성
- [ ] Neo4j 인덱스 생성 (엔티티명, 관계타입)
- [ ] 성능 벤치마크 (쿼리 응답 시간 비교)
- [ ] 기존 에이전트 쿼리 호환성 확인
- [ ] 장애 시 NetworkX 폴백 로직 구현
