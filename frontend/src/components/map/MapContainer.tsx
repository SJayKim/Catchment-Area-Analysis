'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useMapStore } from '@/stores/mapStore';
import DistrictLayer from './DistrictLayer';
import MapControls from './MapControls';

declare global {
  interface Window {
    kakao: any;
  }
}

export default function MapContainer() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const { center, zoom, setCenter, setZoom } = useMapStore();
  const initializedRef = useRef(false);

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const script = document.createElement('script');
    script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${process.env.NEXT_PUBLIC_KAKAO_MAP_KEY}&autoload=false`;
    script.onload = () => {
      window.kakao.maps.load(() => {
        if (!mapRef.current) return;

        const map = new window.kakao.maps.Map(mapRef.current, {
          center: new window.kakao.maps.LatLng(center.lat, center.lng),
          level: 7,
        });

        mapInstanceRef.current = map;

        // Sync map events to store
        window.kakao.maps.event.addListener(map, 'center_changed', () => {
          const latlng = map.getCenter();
          setCenter({ lat: latlng.getLat(), lng: latlng.getLng() });
        });

        window.kakao.maps.event.addListener(map, 'zoom_changed', () => {
          setZoom(map.getLevel());
        });
      });
    };
    document.head.appendChild(script);
  }, []);

  // Sync store changes back to map
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    const map = mapInstanceRef.current;
    const currentCenter = map.getCenter();
    if (
      Math.abs(currentCenter.getLat() - center.lat) > 0.0001 ||
      Math.abs(currentCenter.getLng() - center.lng) > 0.0001
    ) {
      map.setCenter(new window.kakao.maps.LatLng(center.lat, center.lng));
    }
  }, [center]);

  useEffect(() => {
    if (!mapInstanceRef.current) return;
    if (mapInstanceRef.current.getLevel() !== zoom) {
      mapInstanceRef.current.setLevel(zoom);
    }
  }, [zoom]);

  const handleZoomIn = useCallback(() => {
    if (!mapInstanceRef.current) return;
    const current = mapInstanceRef.current.getLevel();
    mapInstanceRef.current.setLevel(current - 1);
  }, []);

  const handleZoomOut = useCallback(() => {
    if (!mapInstanceRef.current) return;
    const current = mapInstanceRef.current.getLevel();
    mapInstanceRef.current.setLevel(current + 1);
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={mapRef} className="w-full h-full" />
      <DistrictLayer mapInstance={mapInstanceRef} />
      <MapControls onZoomIn={handleZoomIn} onZoomOut={handleZoomOut} />
    </div>
  );
}
