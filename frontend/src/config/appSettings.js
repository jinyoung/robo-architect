/**
 * appSettings.js
 * 애플리케이션 전역 설정
 * 
 * 사용자가 커스터마이징할 수 있는 설정값을 관리합니다.
 * 설정값은 localStorage에 저장됩니다.
 */

// ============================================================================
// 설정 키 상수
// ============================================================================

const STORAGE_KEYS = {
  APP_TITLE: 'appTitle',
}

// ============================================================================
// 기본값
// ============================================================================

export const DEFAULT_APP_TITLE = 'Robo Architect'

// ============================================================================
// 설정 관리 함수
// ============================================================================

/**
 * 앱 타이틀 가져오기
 */
export function getAppTitle() {
  try {
    const saved = localStorage.getItem(STORAGE_KEYS.APP_TITLE)
    return saved || DEFAULT_APP_TITLE
  } catch (e) {
    console.warn('localStorage 접근 실패:', e)
    return DEFAULT_APP_TITLE
  }
}

/**
 * 앱 타이틀 설정하기
 */
export function setAppTitle(title) {
  try {
    localStorage.setItem(STORAGE_KEYS.APP_TITLE, title)
    // document.title도 함께 업데이트
    document.title = title
    // 이벤트 발생 (다른 컴포넌트에서 감지 가능)
    window.dispatchEvent(new CustomEvent('appTitleChange', { detail: title }))
  } catch (e) {
    console.warn('localStorage 저장 실패:', e)
  }
}

/**
 * 앱 타이틀 초기화 (기본값으로)
 */
export function resetAppTitle() {
  setAppTitle(DEFAULT_APP_TITLE)
}

/**
 * 초기화 - document.title을 저장된 설정으로 설정
 */
export function initializeAppSettings() {
  const title = getAppTitle()
  document.title = title
}

