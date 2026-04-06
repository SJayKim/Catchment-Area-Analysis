/* eslint-disable jsx-a11y/alt-text */
'use client';

import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Font,
  Image,
} from '@react-pdf/renderer';
import type { ChatMessage } from '@/lib/types';

// Register Korean fonts
Font.register({
  family: 'SpoqaHanSans',
  fonts: [
    { src: '/fonts/SpoqaHanSansNeo-Regular.ttf', fontWeight: 'normal' },
    { src: '/fonts/SpoqaHanSansNeo-Bold.ttf', fontWeight: 'bold' },
  ],
});

const styles = StyleSheet.create({
  page: {
    fontFamily: 'SpoqaHanSans',
    padding: 40,
    fontSize: 10,
    color: '#1e293b',
  },
  // Cover page
  coverPage: {
    fontFamily: 'SpoqaHanSans',
    padding: 60,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
  },
  coverTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#3b82f6',
    marginBottom: 8,
  },
  coverSubtitle: {
    fontSize: 14,
    color: '#64748b',
    marginBottom: 40,
  },
  coverDistrictName: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#1e293b',
    marginBottom: 12,
  },
  coverMeta: {
    fontSize: 11,
    color: '#94a3b8',
    marginBottom: 4,
  },
  // Section
  sectionTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#3b82f6',
    marginBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    paddingBottom: 4,
  },
  // Conversation
  userMsg: {
    backgroundColor: '#eff6ff',
    padding: 8,
    borderRadius: 6,
    marginBottom: 6,
  },
  assistantMsg: {
    backgroundColor: '#f8fafc',
    padding: 8,
    borderRadius: 6,
    marginBottom: 6,
    borderLeftWidth: 3,
    borderLeftColor: '#3b82f6',
  },
  msgRole: {
    fontSize: 8,
    color: '#94a3b8',
    marginBottom: 2,
  },
  msgText: {
    fontSize: 9,
    lineHeight: 1.5,
  },
  // Chart image
  chartImage: {
    width: '100%',
    marginVertical: 8,
  },
  // Disclaimer
  disclaimer: {
    marginTop: 20,
    padding: 10,
    backgroundColor: '#fef2f2',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  disclaimerText: {
    fontSize: 8,
    color: '#991b1b',
    lineHeight: 1.4,
  },
  // Footer
  footer: {
    position: 'absolute',
    bottom: 20,
    left: 40,
    right: 40,
    textAlign: 'center',
    fontSize: 8,
    color: '#94a3b8',
  },
});

interface ReportDocumentProps {
  districtName: string;
  dataQuarter: string;
  messages: ChatMessage[];
  chartImages: string[]; // base64 PNG strings
  generatedAt: string;
}

export default function ReportDocument({
  districtName,
  dataQuarter,
  messages,
  chartImages,
  generatedAt,
}: ReportDocumentProps) {
  // Filter to meaningful messages (max 20 turns)
  const textMessages = messages
    .filter((m) => m.role !== 'system' && (m.type === 'text' || !m.type) && m.content.trim())
    .slice(-40); // last 40 entries → 20 turns

  return (
    <Document>
      {/* Cover Page */}
      <Page size="A4" style={styles.coverPage}>
        <Text style={styles.coverTitle}>MarketScope AI</Text>
        <Text style={styles.coverSubtitle}>상권분석 리포트</Text>
        <Text style={styles.coverDistrictName}>{districtName || '상권 분석'}</Text>
        <Text style={styles.coverMeta}>분석일: {generatedAt}</Text>
        <Text style={styles.coverMeta}>데이터 기준: {dataQuarter || '-'}</Text>
        <Text style={styles.footer}>
          MarketScope AI — 본 리포트는 AI가 생성한 참고 자료입니다.
        </Text>
      </Page>

      {/* Conversation + Charts */}
      <Page size="A4" style={styles.page}>
        <Text style={styles.sectionTitle}>분석 대화 이력</Text>

        {textMessages.length === 0 && (
          <Text style={styles.msgText}>대화 이력이 없습니다.</Text>
        )}

        {textMessages.map((msg) => (
          <View
            key={msg.id}
            style={msg.role === 'user' ? styles.userMsg : styles.assistantMsg}
          >
            <Text style={styles.msgRole}>
              {msg.role === 'user' ? '사용자' : 'AI 분석'}
            </Text>
            <Text style={styles.msgText}>{msg.content.slice(0, 1000)}</Text>
          </View>
        ))}

        {/* Chart images */}
        {chartImages.length > 0 && (
          <>
            <Text style={{ ...styles.sectionTitle, marginTop: 16 }}>차트</Text>
            {chartImages.map((src, i) => (
              <Image key={i} src={src} style={styles.chartImage} />
            ))}
          </>
        )}

        {/* Disclaimer */}
        <View style={styles.disclaimer}>
          <Text style={styles.disclaimerText}>
            ⚠ 본 리포트는 카드매출 기반 추정치 및 AI 분석 결과를 포함하고 있으며, 실제 상권
            현황과 다를 수 있습니다. 투자, 창업 등 중요한 의사결정 시 반드시 현장 조사 및 전문가
            상담을 병행하시기 바랍니다. 데이터 기준 시점: {dataQuarter || '-'}
          </Text>
        </View>

        <Text style={styles.footer}>
          MarketScope AI — {generatedAt}
        </Text>
      </Page>
    </Document>
  );
}
