# F10. 리포트 저장 (PDF) Spec

> 분석 결과를 PDF로 내보내기

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 3 — **완료** (Phase 2 Tier 게이팅 대기) |
| Tier | **Premium** (현재 게이팅 없음) |
| 의존성 | F03 (기본 리포트) |
| 기술 | `@react-pdf/renderer` 4.3 + `html2canvas` 1.4 (Frontend) |
| 구현 | `useReportExport` 훅 + `ReportDocument` 컴포넌트 |
| 트리거 | 챗봇 `"PDF로 저장해줘"` (로컬 패턴 매칭) / ChatPanel 상단 버튼 |
| 용도 | 사업계획서 첨부, 지인 공유 |

## 2. PDF 포함 내용

| 섹션 | 내용 | 소스 |
|------|------|------|
| 표지 | 상권명, 분석 일시, 데이터 기준 분기 | districtStore |
| 상권 요약 | F03 기본 리포트 내용 | SummaryCard 데이터 |
| 대화 분석 내역 | 주요 질문-응답 (카드 포함) | chatStore |
| 차트 | 시간대별 유동인구, 매출 추이 등 | 차트 이미지 캡처 |
| 면책 조항 | 추정치 한계, 데이터 기준 시점 | 고정 텍스트 |

## 3. 생성 방식

### 3.1 Frontend PDF 생성 (권장 — MVP)

```typescript
// components/report/ReportExport.tsx
import { Document, Page, Text, View, Image } from '@react-pdf/renderer';

const ReportPDF = ({ district, summary, messages, charts }) => (
  <Document>
    <Page>
      <View>
        <Text>{district.name} 상권 분석 리포트</Text>
        <Text>분석일: {new Date().toLocaleDateString()}</Text>
        <Text>데이터 기준: {summary.dataQuarter}</Text>
      </View>
      {/* 요약 섹션 */}
      {/* 대화 내역 섹션 */}
      {/* 차트 이미지 섹션 */}
      {/* 면책 조항 */}
    </Page>
  </Document>
);
```

- 차트는 `html2canvas`로 캡처 → 이미지로 PDF에 삽입
- 클라이언트에서 생성 → 서버 부하 없음

### 3.2 Backend PDF 생성 (향후)

```
POST /api/reports/export
{
  "session_id": "uuid-...",
  "district_code": "3110032",
  "include_charts": true
}

Response: application/pdf (파일 다운로드)
```

- S3에 저장 후 다운로드 URL 반환
- 장점: 일관된 PDF 품질, 서버사이드 차트 렌더링

## 4. 트리거

| 방식 | 설명 |
|------|------|
| 챗봇 | "PDF로 저장해줘", "리포트 만들어줘" |
| UI 버튼 | ChatPanel 상단 또는 하단 [PDF 내보내기] 버튼 |

## 5. 수용 기준

- [x] "PDF로 저장" 요청 시 PDF 파일 다운로드 (`MarketScope_{district}_{date}.pdf`)
- [x] PDF 에 상권 요약, 대화 내역, 차트 포함
- [x] 데이터 기준 분기 + 면책 조항 명시
- [x] 한글 폰트 (Spoqa Han Sans Neo) 렌더링
- [ ] PDF 생성 5초 이내 (브라우저 성능 검증 필요)
