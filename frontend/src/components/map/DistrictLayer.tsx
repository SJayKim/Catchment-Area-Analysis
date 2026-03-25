'use client';

import { useEffect, useRef, MutableRefObject } from 'react';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { fetchPolygons } from '@/lib/api';
import { PolygonFeature } from '@/lib/types';

interface DistrictLayerProps {
  mapInstance: MutableRefObject<any>;
}

export default function DistrictLayer({ mapInstance }: DistrictLayerProps) {
  const polygonsRef = useRef<Map<string, any>>(new Map());
  const select = useDistrictStore((s) => s.select);
  const setHovered = useDistrictStore((s) => s.setHovered);
  const selectedCode = useDistrictStore((s) => s.selected?.code);
  const activeLayers = useMapStore((s) => s.activeLayers);

  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !window.kakao) return;

    const loadPolygons = async () => {
      try {
        const bounds = map.getBounds();
        const sw = bounds.getSouthWest();
        const ne = bounds.getNorthEast();

        const features = await fetchPolygons({
          sw_lat: sw.getLat(),
          sw_lng: sw.getLng(),
          ne_lat: ne.getLat(),
          ne_lng: ne.getLng(),
        });

        renderPolygons(map, features);
      } catch {
        // API not available yet - silent fail
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
    };
  }, [mapInstance.current]);

  const renderPolygons = (map: any, features: PolygonFeature[]) => {
    // Clear existing polygons
    polygonsRef.current.forEach((polygon) => polygon.setMap(null));
    polygonsRef.current.clear();

    if (!activeLayers.includes('polygon')) return;

    features.forEach((feature) => {
      const path = feature.coordinates.map(
        ([lng, lat]) => new window.kakao.maps.LatLng(lat, lng)
      );

      const isSelected = feature.code === selectedCode;

      const polygon = new window.kakao.maps.Polygon({
        map,
        path,
        strokeWeight: isSelected ? 3 : 1,
        strokeColor: isSelected ? '#2563eb' : '#3b82f6',
        strokeOpacity: 0.8,
        fillColor: isSelected ? '#3b82f6' : '#60a5fa',
        fillOpacity: isSelected ? 0.4 : 0.15,
      });

      // Hover effects
      window.kakao.maps.event.addListener(polygon, 'mouseover', () => {
        if (feature.code !== selectedCode) {
          polygon.setOptions({
            fillOpacity: 0.3,
            strokeWeight: 2,
          });
        }
        setHovered(feature.code);
      });

      window.kakao.maps.event.addListener(polygon, 'mouseout', () => {
        if (feature.code !== selectedCode) {
          polygon.setOptions({
            fillOpacity: 0.15,
            strokeWeight: 1,
          });
        }
        setHovered(null);
      });

      // Click to select
      window.kakao.maps.event.addListener(polygon, 'click', () => {
        select({
          code: feature.code,
          name: feature.name,
          type: feature.type,
          center: feature.center,
        });
      });

      polygonsRef.current.set(feature.code, polygon);
    });
  };

  return null; // This component only manages map overlays
}
