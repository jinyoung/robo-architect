/**
 * API Configuration
 * API Gateway를 통한 마이크로서비스 연결 설정
 */

// API Gateway URL - 모든 마이크로서비스 요청의 단일 진입점
export const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL ?? 'http://localhost:9000'

// 각 서비스별 Base URL
export const ARCHITECT_API_BASE = `${API_GATEWAY_URL}/architect/api`

/**
 * API URL 생성 헬퍼
 * @param {string} path - API 경로 (예: '/contexts', '/user-stories')
 * @returns {string} 완전한 API URL
 */
export function apiUrl(path) {
  // /api로 시작하면 그대로 유지, 아니면 추가
  const normalizedPath = path.startsWith('/api') ? path.slice(4) : path
  return `${ARCHITECT_API_BASE}${normalizedPath}`
}

/**
 * 기존 상대 경로 호환용 - window.API_BASE에 등록
 * 컴포넌트에서 import 없이 사용 가능하도록
 */
if (typeof window !== 'undefined') {
  window.API_BASE = ARCHITECT_API_BASE
}

export default {
  API_GATEWAY_URL,
  ARCHITECT_API_BASE,
  apiUrl
}

