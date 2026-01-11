<script setup>
/**
 * SettingsModal.vue
 * 설정 모달 컴포넌트
 */

import { ref, watch } from 'vue'
import { getAppTitle, setAppTitle, DEFAULT_APP_TITLE } from '../config/appSettings'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close'])

const tempAppTitle = ref(DEFAULT_APP_TITLE)

// 모달이 열릴 때 현재 설정값 로드
watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    tempAppTitle.value = getAppTitle()
  }
})

function handleClose() {
  emit('close')
}

function handleSave() {
  setAppTitle(tempAppTitle.value || DEFAULT_APP_TITLE)
  emit('close')
}

function handleOverlayClick(e) {
  if (e.target === e.currentTarget) {
    handleClose()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click="handleOverlayClick">
        <div class="modal-container">
          <!-- 헤더 -->
          <div class="modal-header">
            <h2>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
              설정
            </h2>
            <button class="close-btn" @click="handleClose">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <!-- 컨텐츠 -->
          <div class="modal-body">
            <div class="settings-section">
              <h3>일반 설정</h3>
              
              <div class="setting-item">
                <div class="setting-label">
                  <span class="label-text">애플리케이션 타이틀</span>
                  <span class="label-desc">
                    상단 헤더에 표시되는 애플리케이션 이름입니다.
                    브라우저 탭 제목에도 반영됩니다.
                  </span>
                </div>
                <div class="setting-control">
                  <input 
                    type="text" 
                    v-model="tempAppTitle" 
                    :placeholder="DEFAULT_APP_TITLE"
                    class="title-input"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- 푸터 -->
          <div class="modal-footer">
            <button class="btn btn--secondary" @click="handleClose">취소</button>
            <button class="btn btn--primary" @click="handleSave">저장</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  width: 500px;
  max-width: 90vw;
  max-height: 90vh;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: var(--color-bg-tertiary);
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.modal-header h2 svg {
  color: var(--color-accent);
}

.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
}

.close-btn:hover {
  background: var(--color-bg-elevated);
  color: var(--color-text);
}

.modal-body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.settings-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.setting-item {
  padding: 16px 0;
}

.setting-label {
  margin-bottom: 12px;
}

.label-text {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 4px;
}

.label-desc {
  display: block;
  font-size: 12px;
  color: var(--color-text-light);
  line-height: 1.5;
}

.setting-control {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-input {
  width: 100%;
  max-width: 300px;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--color-text-bright);
  background: var(--color-bg);
  transition: all 0.15s;
}

.title-input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(34, 139, 230, 0.15);
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.btn--secondary {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  color: var(--color-text);
}

.btn--secondary:hover {
  background: var(--color-bg-elevated);
}

.btn--primary {
  background: var(--color-accent);
  border: none;
  color: white;
}

.btn--primary:hover {
  background: #1c7ed6;
}

/* Animation */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.25s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: all 0.25s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95) translateY(10px);
}
</style>



