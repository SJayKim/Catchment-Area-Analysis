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

export default function DistrictLayer({ mapInstance }: DistrictLayerProps) {
  const polygonsRef = useRef<Map<string, any>>(new Map());
  const lastBoundsRef = useRef<string>('');
  const select = useDistrictStore((s) => s.select);
  const setHovered = useDistrictStore((s) => s.setHovered);
  const selectedCode = useDistrictStore((s) => s.selected?.code);
  const activeLayers = useMapStore((s) => s.activeLayers);

  // Mirror selectedCode in a ref so event listeners always see the latest
  // value without needing to re-create polygons (see P0-6).
  const selectedCodeRef = useRef<string | undefined>(selectedCode);
  useEffect(() => {
    selectedCodeRef.current = selectedCode;
  }, [selectedCode]);

  const renderPolygons = useCallback(
    (map: any, features: PolygonFeature[]) => {
      // Clear existing polygons
      polygonsRef.current.forEach((polygon) => polygon.setMap(null));
      polygonsRef.current.clear();

      if (!activeLayers.includes('polygon')) return;

      const currentSelected = selectedCodeRef.current;

      features.forEach((feature) => {
        const path = feature.coordinates.map(
          ([lng, lat]: number[]) => new window.kakao.maps.LatLng(lat, lng)
        );

        const isSelected = feature.code === currentSelected;
        const baseStyle = isSelected ? SELECTED_STYLE : DEFAULT_STYLE;

        const polygon = new window.kakao.maps.Polygon({
          map,
          path,
          ...baseStyle,
        });

        // Hover effects — read from ref so a selection change after mount
        // is still respected without re-creating listeners.
        window.kakao.maps.event.addListener(polygon, 'mouseover', () => {
          if (feature.code !== selectedCodeRef.current) {
            polygon.setOptions({
              fillOpacity: 0.3,
              strokeWeight: 2,
            });
          }
          setHovered(feature.code);
        });

        window.kakao.maps.event.addListener(polygon, 'mouseout', () => {
          if (feature.code !== selectedCodeRef.current) {
            polygon.setOptions({
              fillOpacity: DEFAULT_STYLE.fillOpacity,
              strokeWeight: DEFAULT_STYLE.strokeWeight,
            });
          }
          setHovered(null);
        });

        // Click to select (source: 'map' for auto-query via useMapSync)
        window.kakao.maps.event.addListener(polygon, 'click', () => {
          select(
            {
              code: feature.code,
              name: feature.name,
              type: feature.type,
              center: feature.center,
            },
            'map'
          );
        });

        polygonsRef.current.set(feature.code, polygon);
      });
    },
    [activeLayers, select, setHovered]
  );

  // On selection change: update polygon styles in-place without re-creating
  // them. Iterating ~1,650 polygons with setOptions is cheap (~1ms).
  useEffect(() => {
    polygonsRef.current.forEach((polygon, code) => {
      const style = code === selectedCode ? SELECTED_STYLE : DEFAULT_STYLE;
      polygon.setOptions(style);
    });
  }, [selectedCode]);

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
