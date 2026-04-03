declare namespace kakao.maps {
  class Map {
    constructor(container: HTMLElement, options: { center: LatLng; level: number });
    getCenter(): LatLng;
    setCenter(latlng: LatLng): void;
    getLevel(): number;
    setLevel(level: number): void;
  }

  class LatLng {
    constructor(lat: number, lng: number);
    getLat(): number;
    getLng(): number;
  }

  class Polygon {
    constructor(options: {
      map?: Map;
      path: LatLng[];
      strokeWeight?: number;
      strokeColor?: string;
      strokeOpacity?: number;
      fillColor?: string;
      fillOpacity?: number;
    });
    setMap(map: Map | null): void;
    setOptions(options: {
      strokeWeight?: number;
      strokeColor?: string;
      strokeOpacity?: number;
      fillColor?: string;
      fillOpacity?: number;
    }): void;
  }

  namespace event {
    function addListener(target: Map | Polygon, type: string, handler: (...args: any[]) => void): void;
    function removeListener(target: Map | Polygon, type: string, handler: (...args: any[]) => void): void;
  }

  function load(callback: () => void): void;
}

interface Window {
  kakao: {
    maps: typeof kakao.maps & {
      load: (callback: () => void) => void;
      Map: typeof kakao.maps.Map;
      LatLng: typeof kakao.maps.LatLng;
      Polygon: typeof kakao.maps.Polygon;
      event: typeof kakao.maps.event;
    };
  };
}
