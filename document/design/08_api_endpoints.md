# Phase 1: API Endpoints Checklist

- [ ] `app/main.py` - FastAPI 앱, lifespan, 미들웨어
- [ ] `app/api/routes/analysis.py` - POST /analysis, GET /analysis/{id}, GET /analysis/{id}/stream
- [ ] `app/api/routes/health.py` - GET /health
- [ ] `app/api/deps.py` - 의존성 주입
- [ ] `app/services/analysis_service.py` - LangGraph 실행 오케스트레이션
- [ ] SSE 스트리밍 엔드포인트
