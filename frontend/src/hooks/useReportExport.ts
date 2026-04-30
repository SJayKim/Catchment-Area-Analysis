'use client';

import { useState, useCallback } from 'react';
import type { ChatMessage } from '@/lib/types';
import { useToastStore } from '@/stores/toastStore';

interface UseReportExportOptions {
  districtName: string;
  dataQuarter: string;
  messages: ChatMessage[];
}

export function useReportExport({ districtName, dataQuarter, messages }: UseReportExportOptions) {
  const [isGenerating, setIsGenerating] = useState(false);

  const generatePDF = useCallback(async () => {
    if (isGenerating) return;
    setIsGenerating(true);

    try {
      // Dynamic imports to avoid SSR issues
      const { pdf } = await import('@react-pdf/renderer');
      const { default: html2canvas } = await import('html2canvas');
      const { default: ReportDocument } = await import(
        '@/components/report/ReportDocument'
      );
      const React = await import('react');

      // Capture chart images from DOM
      const chartImages: string[] = [];
      const chartElements = document.querySelectorAll('[data-chart-capture]');
      for (const el of Array.from(chartElements)) {
        try {
          const canvas = await html2canvas(el as HTMLElement, {
            backgroundColor: '#1e293b',
            scale: 2,
            logging: false,
          });
          chartImages.push(canvas.toDataURL('image/png'));
        } catch {
          // Skip failed captures
        }
      }

      const generatedAt = new Date().toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });

      const doc = React.createElement(ReportDocument, {
        districtName,
        dataQuarter,
        messages,
        chartImages,
        generatedAt,
      });

      const blob = await pdf(doc as Parameters<typeof pdf>[0]).toBlob();

      // Trigger download
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `MarketScope_${districtName || '상권분석'}_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('[PDF] Generation failed:', err);
      // Surface a user-visible toast with manual retry. Auto-retry is
      // intentionally off (user-trigger only) to prevent infinite loops on
      // deterministic failures (e.g. Recharts CSS3 paint exception).
      useToastStore.getState().show(
        'PDF 생성에 실패했어요. 다시 시도해 주세요.',
        'error',
        {
          actionLabel: '재시도',
          onAction: () => {
            void generatePDF();
          },
        }
      );
    } finally {
      setIsGenerating(false);
    }
  }, [isGenerating, districtName, dataQuarter, messages]);

  return { generatePDF, isGenerating };
}
