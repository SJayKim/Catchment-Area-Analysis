'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import { useMapStore } from '@/stores/mapStore';
import DistrictLayer from './DistrictLayer';
import MapControls from './MapControls';
import TimeSlider from './TimeSlider';

const HeatmapLayer = dynamic(() => import('./HeatmapLayer'), { ssr: false });

export default function MapContainer() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const [mapReady, setMapReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { center, zoom, setCenter, setZoom } = useMapStore();

  // 카카오맵 SDK 프록시 로딩 (ORB 우회)
  useEffect(() => {
    if (window.kakao?.maps?.load) {
      window.kakao.maps.load(() => initMap());
      return;
    }

    // 1) SDK가 appkey를 찾을 수 있도록 더미 script src 삽입
    const dummy = document.createElement('script');
    dummy.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${process.env.NEXT_PUBLIC_KAKAO_MAP_KEY}&autoload=false`;
    dummy.type = 'text/placeholder';
    document.head.appendChild(dummy);

    // 2) 서버 프록시로 SDK 코드를 가져와 인라인 실행
    //    /_proxy/* 는 Next.js server route 네임스페이스 — /api/* 는 전부 backend로 감.
    fetch('/_proxy/kakao-sdk')
      .then((res) => {
        if (!res.ok) throw new Error(`SDK proxy ${res.status}`);
        return res.text();
      })
      .then((sdkCode) => {
        const script = document.createElement('script');
        script.textContent = sdkCode;
        document.head.appendChild(script);

        if (window.kakao?.maps?.load) {
          window.kakao.maps.load(() => initMap());
        } else {
          setLoadError('카카오맵 SDK 초기화 실패. 페이지를 새로고침해주세요.');
        }
      })
      .catch((err) => {
        console.error('[KakaoMap] SDK load failed:', err);
        setLoadError('카카오맵 SDK를 불러올 수 없습니다. 네트워크를 확인해주세요.');
      });

    return () => {
      if (dummy.parentNode) dummy.parentNode.removeChild(dummy);
    };
  }, []);

  function initMap() {
    if (!mapRef.current || mapInstanceRef.current) return;

    try {
      const map = new window.kakao.maps.Map(mapRef.current, {
        center: new window.kakao.maps.LatLng(center.lat, center.lng),
        level: 7,
      });

      mapInstanceRef.current = map;
      setMapReady(true);
      // [KakaoMap] Map initialized successfully');

      window.kakao.maps.event.addListener(map, 'center_changed', () => {
        const latlng = map.getCenter();
        setCenter({ lat: latlng.getLat(), lng: latlng.getLng() });
      });

      window.kakao.maps.event.addListener(map, 'zoom_changed', () => {
        setZoom(map.getLevel());
      });
    } catch (e) {
      console.error('[KakaoMap] init error:', e);
      setLoadError(`지도 초기화 실패: ${e}`);
    }
  }

  // Sync store → map: center
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    const map = mapInstanceRef.current;
    const cur = map.getCenter();
    if (
      Math.abs(cur.getLat() - center.lat) > 0.0001 ||
      Math.abs(cur.getLng() - center.lng) > 0.0001
    ) {
      map.setCenter(new window.kakao.maps.LatLng(center.lat, center.lng));
    }
  }, [center]);

  // Sync store → map: zoom
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    if (mapInstanceRef.current.getLevel() !== zoom) {
      mapInstanceRef.current.setLevel(zoom);
    }
  }, [zoom]);

  const handleZoomIn = useCallback(() => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.setLevel(mapInstanceRef.current.getLevel() - 1);
  }, []);

  const handleZoomOut = useCallback(() => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.setLevel(mapInstanceRef.current.getLevel() + 1);
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={mapRef} className="w-full h-full" />

      {/* 로딩 상태 */}
      {!mapReady && !loadError && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <div className="text-center">
            <div className="animate-spin w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-3" />
            <p className="text-sm text-gray-500">지도 로딩 중...</p>
          </div>
        </div>
      )}

      {/* 에러 상태 */}
      {loadError && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <div className="text-center px-6">
            <p className="text-red-500 text-sm font-medium mb-2">지도를 불러올 수 없습니다</p>
            <p className="text-xs text-gray-400 mb-3">{loadError}</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-1.5 text-xs bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              새로고침
            </button>
          </div>
        </div>
      )}

      {mapReady && <DistrictLayer mapInstance={mapInstanceRef} />}
      {mapReady && <HeatmapLayer mapInstance={mapInstanceRef} />}
      <MapControls onZoomIn={handleZoomIn} onZoomOut={handleZoomOut} />
      <TimeSlider />
    </div>
  );
}
