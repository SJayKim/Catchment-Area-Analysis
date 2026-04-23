import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

// root env 자동 로드.
// 우선순위: 환경변수(Docker/CI) > frontend/.env.local > root/.env.dev > root/.env
// .env 는 prod 배포용, .env.dev 는 로컬 개발용 (config.py 관례와 동일).
const __dirname = dirname(fileURLToPath(import.meta.url));
const devEnvPath = resolve(__dirname, '..', '.env.dev');
const prodEnvPath = resolve(__dirname, '..', '.env');
const envPath = existsSync(devEnvPath) ? devEnvPath : prodEnvPath;
if (existsSync(envPath)) {
  config({ path: envPath, override: false }); // 기존 값 유지
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone', // Docker production 빌드용
  // root .env에서 읽은 NEXT_PUBLIC_* 를 클라이언트에 노출
  env: {
    NEXT_PUBLIC_KAKAO_MAP_KEY: process.env.NEXT_PUBLIC_KAKAO_MAP_KEY || '',
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '',
  },
  async rewrites() {
    // Next.js 서버(컨테이너 내부)에서 백엔드로 프록시할 때 쓰는 URL.
    // 브라우저 fetch용 NEXT_PUBLIC_API_URL(예: http://localhost:8000)과 달리
    // 도커 내부 네트워크 호스트명(backend:8000)이어야 하므로 별도 변수를 사용.
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:8002';
    // kakao-sdk 프록시는 /proxy/kakao-sdk (Next.js server route)로 이동됨.
    // /proxy/* 는 rewrite 대상이 아니므로 /api/* 전체를 backend로 보내도 무방.
    // (underscore prefix `_proxy/` 는 Next.js private folder 로 라우트 제외되므로 사용 금지)
    return {
      fallback: [
        {
          source: '/api/:path*',
          destination: `${backendUrl}/api/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
