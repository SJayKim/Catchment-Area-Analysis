import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

// root .env 자동 로드 — 어떤 환경에서든 단일 .env로 동작
// 우선순위: 환경변수(Docker/CI) > frontend/.env.local > root/.env
const __dirname = dirname(fileURLToPath(import.meta.url));
const rootEnvPath = resolve(__dirname, '..', '.env');
if (existsSync(rootEnvPath)) {
  config({ path: rootEnvPath, override: false }); // 기존 값 유지
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
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002';
    return {
      beforeFiles: [
        // kakao-sdk 프록시는 Next.js API route가 직접 처리 (ORB 우회)
        {
          source: '/api/kakao-sdk',
          destination: '/api/kakao-sdk',
        },
      ],
      fallback: [
        // 나머지 /api/* 는 백엔드로 프록시
        {
          source: '/api/:path*',
          destination: `${backendUrl}/api/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
