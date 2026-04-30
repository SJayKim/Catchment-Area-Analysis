'use client';

import { useEffect, useRef, useCallback, MutableRefObject } from 'react';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { fetchPolygons } from '@/lib/api';
import { PolygonFeature } from '@/lib/types';

interface DistrictLayerProps {
  mapInstance: MutableRefObject<any>;
}

// Style presets so selection-change updates stay in sync with creation.
const SELECTED_STYLE = {
  strokeWeight: 3,
  strokeColor: '#2563eb',
  strokeOpacity: 0.8,
  fillColor: '#3b82f6',
  fillOpacity: 0.4,
};
const DEFAULT_STYLE = {
  strokeWeight: 1,
  strokeColor: '#3b82f6',
  strokeOpacity: 0.8,
  fillColor: '#60a5fa',
  fillOpacity: 0.15,
};

// Compare-mode palette (slot 0/1/2 by compareList order). Slot 0 matches the
// single-select blue so toggling compare mode on/off is visually continuous.
const COMPARE_STYLES = [
  SELECTED_STYLE,
  {
    strokeWeight: 3,
    strokeColor: '#d97706',
    strokeOpacity: 0.85,
    fillColor: '#f59e0b',
    fillOpacity: 0.4,
  },
  {
    strokeWeight: 3,
    strokeColor: '#be185d',
    strokeOpacity: 0.85,
    fillColor: '#ec4899',
    fillOpacity: 0.4,
  },
];

export default function DistrictLayer({ mapInstance }: DistrictLayerProps) {
  const polygonsRef = useRef<Map<string, any>>(new Map());
  const lastBoundsRef = useRef<string>('');
  const select = useDistrictStore((s) => s.select);
  const setHovered = useDistrictStore((s) => s.setHovered);
  const addToCompare = useDistrictStore((s) => s.addToCompare);
  const removeFromCompare = useDistrictStore((s) => s.removeFromCompare);
  const deselect = useDistrictStore((s) => s.deselect);
  const selectedCode = useDistrictStore((s) => s.selected?.code);
  const isCompareMode = useDistrictStore((s) => s.isCompareMode);
  const compareList = useDistrictStore((s) => s.compareList);
  const activeLayers = useMapStore((s) => s.activeLayers);

  // Mirror state in refs so event listeners always see the latest value
  // without needing to re-create polygons (see P0-6).
  const selectedCodeRef = useRef<string | undefined>(selectedCode);
  const isCompareModeRef = useRef<boolean>(isCompareMode);
  const compareCodesRef = useRef<string[]>(compareList.map((d) => d.code));
  useEffect(() => {
    selectedCodeRef.current = selectedCode;
  }, [selectedCode]);
  useEffect(() => {
    isCompareModeRef.current = isCompareMode;
  }, [isCompareMode]);
  useEffect(() => {
    compareCodesRef.current = compareList.map((d) => d.code);
  }, [compareList]);

  // Pick style by current selection / compare-slot membership.
  const styleFor = useCallback(
    (code: string) => {
      if (isCompareModeRef.current && compareCodesRef.current.length > 0) {
        const idx = compareCodesRef.current.indexOf(code);
        if (idx >= 0) return COMPARE_STYLES[idx] ?? SELECTED_STYLE;
        return DEFAULT_STYLE;
      }
      return code === selectedCodeRef.current ? SELECTED_STYLE : DEFAULT_STYLE;
    },
    []
  );

  const renderPolygons = useCallback(
    (map: any, features: PolygonFeature[]) => {
      // Clear existing polygons
      polygonsRef.current.forEach((polygon) => polygon.setMap(null));
      polygonsRef.current.clear();

      if (!activeLayers.includes('polygon')) return;

      const isActive = (code: string) =>
        isCompareModeRef.current && compareCodesRef.current.length > 0
          ? compareCodesRef.current.includes(code)
          : code === selectedCodeRef.current;

      features.forEach((feature) => {
        const path = feature.coordinates.map(
          ([lng, lat]: number[]) => new window.kakao.maps.LatLng(lat, lng)
        );

        const polygon = new window.kakao.maps.Polygon({
          map,
          path,
          ...styleFor(feature.code),
        });

        // Hover effects — read from refs so a selection change after mount
        // is still respected without re-creating listeners.
        window.kakao.maps.event.addListener(polygon, 'mouseover', () => {
          if (!isActive(feature.code)) {
            polygon.setOptions({
              fillOpacity: 0.3,
              strokeWeight: 2,
            });
          }
          setHovered(feature.code);
        });

        window.kakao.maps.event.addListener(polygon, 'mouseout', () => {
          // D.10 — 항상 styleFor 로 재계산해서 compare 슬롯 색 race 방지.
          // hover 중 compareList / selected 가 바뀌어도 stale DEFAULT 로 덮이지
          // 않도록 selected/compare/default 분기를 일관 적용.
          polygon.setOptions(styleFor(feature.code));
          setHovered(null);
        });

        // Click: in compare mode add to compareList (up to 3) and also sync
        // the "current" selection so chat context / StatusBar follow along.
        // 같은 상권 재클릭 (B.1): 비교 모드 OFF → deselect, ON → 비교 슬롯 제거.
        window.kakao.maps.event.addListener(polygon, 'click', () => {
          const district = {
            code: feature.code,
            name: feature.name,
            type: feature.type,
            center: feature.center,
          };
          if (isCompareModeRef.current) {
            const inCompare = compareCodesRef.current.includes(feature.code);
            if (inCompare) {
              removeFromCompare(feature.code);
              if (selectedCodeRef.current === feature.code) {
                deselect();
              }
              return;
            }
            addToCompare(district);
            select(district, 'map');
            return;
          }
          if (selectedCodeRef.current === feature.code) {
            deselect();
            return;
          }
          select(district, 'map');
        });

        polygonsRef.current.set(feature.code, polygon);
      });
    },
    [activeLayers, select, deselect, setHovered, addToCompare, removeFromCompare, styleFor]
  );

  // On selection / compare-mode / compareList change: update polygon styles
  // in-place without re-creating them. Iterating ~1,650 polygons with
  // setOptions is cheap (~1ms).
  useEffect(() => {
    polygonsRef.current.forEach((polygon, code) => {
      polygon.setOptions(styleFor(code));
    });
  }, [selectedCode, isCompareMode, compareList, styleFor]);

  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !window.kakao) return;

    const loadPolygons = async () => {
      try {
        const bounds = map.getBounds();
        const sw = bounds.getSouthWest();
        const ne = bounds.getNorthEast();

        // Round coordinates to 3 decimal places (~111m) to deduplicate
        const boundsKey = [
          sw.getLat().toFixed(3),
          sw.getLng().toFixed(3),
          ne.getLat().toFixed(3),
          ne.getLng().toFixed(3),
        ].join(',');

        if (boundsKey === lastBoundsRef.current) return;
        lastBoundsRef.current = boundsKey;

        const features = await fetchPolygons({
          sw_lat: sw.getLat(),
          sw_lng: sw.getLng(),
          ne_lat: ne.getLat(),
          ne_lng: ne.getLng(),
        });

        renderPolygons(map, features);
      } catch (err) {
        console.warn('[DistrictLayer] Failed to load polygons:', err);
      }
    };

    // Load initially and on map idle
    const timer = setTimeout(loadPolygons, 500);
    window.kakao.maps.event.addListener(map, 'idle', loadPolygons);

    return () => {
      clearTimeout(timer);
      if (map && window.kakao) {
        window.kakao.maps.event.removeListener(map, 'idle', loadPolygons);
      }
      // Clean up polygons on unmount
      polygonsRef.current.forEach((polygon) => polygon.setMap(null));
      polygonsRef.current.clear();
    };
  }, [renderPolygons]);

  return null; // This component only manages map overlays
}
