<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useNavigatorStore } from '../stores/navigator'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'complete'])

const navigatorStore = useNavigatorStore()

// State
const dragActive = ref(false)
const file = ref(null)
const textContent = ref('')
const inputMode = ref('file') // 'file' or 'text'
const isUploading = ref(false)
const isProcessing = ref(false)
const sessionId = ref(null)
const progress = ref(0)
const currentPhase = ref('')
const currentMessage = ref('')
const createdItems = ref([])
const eventSource = ref(null)
const error = ref(null)
const summary = ref(null)

// Computed
const isOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const canSubmit = computed(() => {
  if (inputMode.value === 'file') {
    return file.value !== null
  }
  return textContent.value.trim().length > 10
})

const phaseLabel = computed(() => {
  const labels = {
    'upload': '업로드 중',
    'parsing': '문서 파싱',
    'extracting_user_stories': 'User Story 추출',
    'identifying_bc': 'Bounded Context 식별',
    'extracting_aggregates': 'Aggregate 추출',
    'extracting_commands': 'Command 추출',
    'extracting_events': 'Event 추출',
    'identifying_policies': 'Policy 식별',
    'saving': '저장 중',
    'complete': '완료',
    'error': '오류 발생'
  }
  return labels[currentPhase.value] || currentPhase.value
})

// Methods
function handleDragOver(e) {
  e.preventDefault()
  dragActive.value = true
}

function handleDragLeave(e) {
  e.preventDefault()
  dragActive.value = false
}

function handleDrop(e) {
  e.preventDefault()
  dragActive.value = false
  
  const files = e.dataTransfer.files
  if (files.length > 0) {
    handleFile(files[0])
  }
}

function handleFileSelect(e) {
  const files = e.target.files
  if (files.length > 0) {
    handleFile(files[0])
  }
}

function handleFile(f) {
  const validTypes = ['text/plain', 'application/pdf', 'text/markdown']
  const validExtensions = ['.txt', '.pdf', '.md']
  
  const isValidType = validTypes.includes(f.type) || 
    validExtensions.some(ext => f.name.toLowerCase().endsWith(ext))
  
  if (!isValidType) {
    error.value = '지원하지 않는 파일 형식입니다. (txt, pdf, md 지원)'
    return
  }
  
  file.value = f
  error.value = null
}

function removeFile() {
  file.value = null
}

async function startIngestion() {
  error.value = null
  isUploading.value = true
  createdItems.value = []
  summary.value = null
  
  // Clear navigator for fresh start (optional: could keep existing data)
  // navigatorStore.clearAll()
  
  try {
    // Step 1: Upload file/text
    const formData = new FormData()
    
    if (inputMode.value === 'file' && file.value) {
      formData.append('file', file.value)
    } else {
      formData.append('text', textContent.value)
    }
    
    const uploadResponse = await fetch('/api/ingest/upload', {
      method: 'POST',
      body: formData
    })
    
    if (!uploadResponse.ok) {
      const errData = await uploadResponse.json()
      throw new Error(errData.detail || 'Upload failed')
    }
    
    const { session_id } = await uploadResponse.json()
    sessionId.value = session_id
    isUploading.value = false
    isProcessing.value = true
    
    // Step 2: Connect to SSE stream
    connectToStream(session_id)
    
  } catch (e) {
    error.value = e.message
    isUploading.value = false
    isProcessing.value = false
  }
}

function connectToStream(sid) {
  eventSource.value = new EventSource(`/api/ingest/stream/${sid}`)
  
  eventSource.value.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data)
    
    currentPhase.value = data.phase
    currentMessage.value = data.message
    progress.value = data.progress
    
    // Handle created objects
    if (data.data?.object) {
      const obj = data.data.object
      createdItems.value.push(obj)
      
      // Trigger navigator updates for dynamic display
      if (obj.type === 'UserStory') {
        navigatorStore.addUserStory(obj)
      } else if (obj.type === 'BoundedContext') {
        navigatorStore.addContext(obj)
      }
    }
    
    // Handle User Story assignment to BC (move animation)
    if (data.data?.type === 'UserStoryAssigned') {
      const assignment = data.data.object
      navigatorStore.assignUserStoryToBC(
        assignment.id,
        assignment.targetBcId,
        assignment.targetBcName
      )
    }
    
    // Handle summary
    if (data.data?.summary) {
      summary.value = data.data.summary
    }
    
    // Handle completion
    if (data.phase === 'complete') {
      isProcessing.value = false
      closeStream()
      // Refresh navigator tree
      navigatorStore.refreshAll()
    }
    
    // Handle error
    if (data.phase === 'error') {
      error.value = data.message
      isProcessing.value = false
      closeStream()
    }
  })
  
  eventSource.value.onerror = () => {
    if (isProcessing.value) {
      error.value = '연결이 끊어졌습니다'
    }
    closeStream()
  }
}

function closeStream() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
}

function closeModal() {
  if (isProcessing.value) {
    if (!confirm('진행 중인 작업이 있습니다. 정말 닫으시겠습니까?')) {
      return
    }
    closeStream()
  }
  
  // Reset state
  file.value = null
  textContent.value = ''
  progress.value = 0
  currentPhase.value = ''
  currentMessage.value = ''
  createdItems.value = []
  isProcessing.value = false
  isUploading.value = false
  error.value = null
  summary.value = null
  
  isOpen.value = false
  
  // Emit complete if we have created items
  if (createdItems.value.length > 0) {
    emit('complete')
  }
}

function getTypeIcon(type) {
  const icons = {
    UserStory: 'US',
    BoundedContext: 'BC',
    Aggregate: 'A',
    Command: 'C',
    Event: 'E',
    Policy: 'P'
  }
  return icons[type] || '?'
}

function getTypeClass(type) {
  return `item-icon--${type.toLowerCase()}`
}

// Cleanup on unmount
onUnmounted(() => {
  closeStream()
})

// Sample requirements text
const sampleText = `# 온라인 쇼핑몰 요구사항

## 1. 주문 관리
- 고객은 상품을 장바구니에 담고 주문할 수 있어야 한다
- 고객은 주문을 취소할 수 있어야 한다 (배송 전까지)
- 고객은 주문 상태를 조회할 수 있어야 한다

## 2. 상품 관리
- 판매자는 상품을 등록할 수 있어야 한다
- 판매자는 상품 정보를 수정할 수 있어야 한다
- 판매자는 상품 재고를 관리할 수 있어야 한다

## 3. 결제 처리
- 시스템은 주문 시 결제를 처리해야 한다
- 주문 취소 시 자동으로 환불이 처리되어야 한다

## 4. 재고 관리
- 주문 시 재고가 자동으로 차감되어야 한다
- 주문 취소 시 재고가 복원되어야 한다

## 5. 알림
- 주문 완료 시 고객에게 이메일 알림을 보내야 한다
- 배송 시작 시 고객에게 알림을 보내야 한다`

function useSample() {
  textContent.value = sampleText
  inputMode.value = 'text'
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay" @click.self="closeModal">
        <div class="modal-container">
          <!-- Header -->
          <div class="modal-header">
            <h2 class="modal-title">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="12" y1="18" x2="12" y2="12"></line>
                <line x1="9" y1="15" x2="15" y2="15"></line>
              </svg>
              요구사항 문서 업로드
            </h2>
            <button class="modal-close" @click="closeModal">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          
          <!-- Body -->
          <div class="modal-body">
            <!-- Input Mode Tabs -->
            <div v-if="!isProcessing && !summary" class="input-tabs">
              <button 
                :class="['tab-btn', { active: inputMode === 'file' }]"
                @click="inputMode = 'file'"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                  <polyline points="13 2 13 9 20 9"></polyline>
                </svg>
                파일 업로드
              </button>
              <button 
                :class="['tab-btn', { active: inputMode === 'text' }]"
                @click="inputMode = 'text'"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="17" y1="10" x2="3" y2="10"></line>
                  <line x1="21" y1="6" x2="3" y2="6"></line>
                  <line x1="21" y1="14" x2="3" y2="14"></line>
                  <line x1="17" y1="18" x2="3" y2="18"></line>
                </svg>
                텍스트 입력
              </button>
            </div>
            
            <!-- File Upload Area -->
            <div v-if="inputMode === 'file' && !isProcessing && !summary" class="upload-section">
              <div 
                class="dropzone"
                :class="{ 'is-active': dragActive, 'has-file': file }"
                @dragover="handleDragOver"
                @dragleave="handleDragLeave"
                @drop="handleDrop"
                @click="$refs.fileInput.click()"
              >
                <input 
                  ref="fileInput"
                  type="file" 
                  accept=".txt,.pdf,.md"
                  style="display: none"
                  @change="handleFileSelect"
                />
                
                <div v-if="!file" class="dropzone-content">
                  <div class="dropzone-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="17 8 12 3 7 8"></polyline>
                      <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                  </div>
                  <p class="dropzone-text">파일을 드래그하거나 클릭하여 선택</p>
                  <p class="dropzone-hint">PDF, TXT, MD 파일 지원</p>
                </div>
                
                <div v-else class="file-preview">
                  <div class="file-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                  </div>
                  <div class="file-info">
                    <span class="file-name">{{ file.name }}</span>
                    <span class="file-size">{{ (file.size / 1024).toFixed(1) }} KB</span>
                  </div>
                  <button class="file-remove" @click.stop="removeFile">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </button>
                </div>
              </div>
            </div>
            
            <!-- Text Input Area -->
            <div v-if="inputMode === 'text' && !isProcessing && !summary" class="text-section">
              <textarea
                v-model="textContent"
                class="text-input"
                placeholder="요구사항 문서 내용을 입력하세요..."
                rows="12"
              ></textarea>
              <button class="sample-btn" @click="useSample">
                샘플 요구사항 사용
              </button>
            </div>
            
            <!-- Processing View -->
            <div v-if="isProcessing || isUploading" class="processing-section">
              <!-- Progress Bar -->
              <div class="progress-container">
                <div class="progress-header">
                  <span class="progress-phase">{{ phaseLabel }}</span>
                  <span class="progress-percent">{{ progress }}%</span>
                </div>
                <div class="progress-bar">
                  <div 
                    class="progress-fill" 
                    :style="{ width: `${progress}%` }"
                  ></div>
                </div>
                <p class="progress-message">{{ currentMessage }}</p>
              </div>
              
              <!-- Live Created Items -->
              <div class="created-items">
                <h3 class="items-title">생성된 객체</h3>
                <div class="items-list">
                  <TransitionGroup name="item-list">
                    <div 
                      v-for="item in createdItems.slice(-10)"
                      :key="item.id"
                      class="created-item"
                    >
                      <span 
                        class="item-icon"
                        :class="getTypeClass(item.type)"
                      >
                        {{ getTypeIcon(item.type) }}
                      </span>
                      <span class="item-type">{{ item.type }}</span>
                      <span class="item-name">{{ item.name }}</span>
                    </div>
                  </TransitionGroup>
                </div>
                <div v-if="createdItems.length > 10" class="items-more">
                  +{{ createdItems.length - 10 }} more items
                </div>
              </div>
            </div>
            
            <!-- Summary View -->
            <div v-if="summary" class="summary-section">
              <div class="summary-icon">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
              </div>
              <h3 class="summary-title">모델 생성 완료!</h3>
              
              <div class="summary-stats">
                <div class="stat-item">
                  <span class="stat-icon stat-icon--userstory">US</span>
                  <span class="stat-value">{{ summary.user_stories || createdItems.filter(i => i.type === 'UserStory').length }}</span>
                  <span class="stat-label">User Stories</span>
                </div>
                <div class="stat-item">
                  <span class="stat-icon stat-icon--bc">BC</span>
                  <span class="stat-value">{{ summary.bounded_contexts }}</span>
                  <span class="stat-label">Bounded Contexts</span>
                </div>
                <div class="stat-item">
                  <span class="stat-icon stat-icon--aggregate">A</span>
                  <span class="stat-value">{{ summary.aggregates }}</span>
                  <span class="stat-label">Aggregates</span>
                </div>
                <div class="stat-item">
                  <span class="stat-icon stat-icon--command">C</span>
                  <span class="stat-value">{{ summary.commands }}</span>
                  <span class="stat-label">Commands</span>
                </div>
                <div class="stat-item">
                  <span class="stat-icon stat-icon--event">E</span>
                  <span class="stat-value">{{ summary.events }}</span>
                  <span class="stat-label">Events</span>
                </div>
                <div class="stat-item">
                  <span class="stat-icon stat-icon--policy">P</span>
                  <span class="stat-value">{{ summary.policies }}</span>
                  <span class="stat-label">Policies</span>
                </div>
              </div>
              
              <p class="summary-hint">
                네비게이터에서 생성된 객체를 확인하고 캔버스에 드래그하세요
              </p>
            </div>
            
            <!-- Error Display -->
            <div v-if="error" class="error-message">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              {{ error }}
            </div>
          </div>
          
          <!-- Footer -->
          <div class="modal-footer">
            <button 
              v-if="!isProcessing && !summary"
              class="btn btn--secondary"
              @click="closeModal"
            >
              취소
            </button>
            <button 
              v-if="!isProcessing && !summary"
              class="btn btn--primary"
              :disabled="!canSubmit || isUploading"
              @click="startIngestion"
            >
              <template v-if="isUploading">
                <span class="spinner"></span>
                업로드 중...
              </template>
              <template v-else>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                분석 시작
              </template>
            </button>
            <button 
              v-if="summary"
              class="btn btn--primary"
              @click="closeModal"
            >
              완료
            </button>
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
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 640px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.modal-title svg {
  color: var(--color-accent);
}

.modal-close {
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
}

.modal-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.modal-body {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg);
  border-top: 1px solid var(--color-border);
}

/* Input Tabs */
.input-tabs {
  display: flex;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-lg);
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.tab-btn:hover {
  background: var(--color-bg);
}

.tab-btn.active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: white;
}

/* Dropzone */
.dropzone {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-xl);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.dropzone:hover,
.dropzone.is-active {
  border-color: var(--color-accent);
  background: rgba(34, 139, 230, 0.05);
}

.dropzone.has-file {
  border-style: solid;
  border-color: var(--color-accent);
  background: rgba(34, 139, 230, 0.05);
}

.dropzone-icon {
  color: var(--color-text-light);
  margin-bottom: var(--spacing-md);
}

.dropzone-text {
  font-size: 1rem;
  color: var(--color-text);
  margin-bottom: var(--spacing-xs);
}

.dropzone-hint {
  font-size: 0.875rem;
  color: var(--color-text-light);
}

/* File Preview */
.file-preview {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  text-align: left;
}

.file-icon {
  color: var(--color-accent);
}

.file-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.file-name {
  font-size: 0.875rem;
  color: var(--color-text-bright);
  font-weight: 500;
}

.file-size {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.file-remove {
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
}

.file-remove:hover {
  background: rgba(255, 100, 100, 0.1);
  color: #ff6464;
}

/* Text Input */
.text-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.text-input {
  width: 100%;
  padding: var(--spacing-md);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  line-height: 1.6;
  resize: vertical;
  min-height: 200px;
}

.text-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.text-input::placeholder {
  color: var(--color-text-light);
}

.sample-btn {
  align-self: flex-start;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 0.75rem;
  padding: var(--spacing-xs) var(--spacing-sm);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.sample-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

/* Processing Section */
.processing-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.progress-container {
  background: var(--color-bg);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.progress-phase {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-accent);
}

.progress-percent {
  font-size: 0.875rem;
  color: var(--color-text-light);
}

.progress-bar {
  height: 8px;
  background: var(--color-bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent), var(--color-command));
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-message {
  margin-top: var(--spacing-sm);
  font-size: 0.875rem;
  color: var(--color-text);
}

/* Created Items */
.created-items {
  background: var(--color-bg);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.items-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-sm);
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  max-height: 200px;
  overflow-y: auto;
}

.created-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.item-icon {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 600;
  color: white;
}

.item-icon--userstory {
  background: #20c997;
  font-size: 0.55rem;
}

.item-icon--boundedcontext {
  background: var(--color-bc);
  border: 2px solid var(--color-text-light);
  color: var(--color-text-light);
}

.item-icon--aggregate {
  background: var(--color-aggregate);
  color: var(--color-bc);
}

.item-icon--command {
  background: var(--color-command);
}

.item-icon--event {
  background: var(--color-event);
}

.item-icon--policy {
  background: var(--color-policy);
}

.item-type {
  font-size: 0.7rem;
  color: var(--color-text-light);
  min-width: 80px;
}

.item-name {
  font-size: 0.875rem;
  color: var(--color-text);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.items-more {
  margin-top: var(--spacing-sm);
  font-size: 0.75rem;
  color: var(--color-text-light);
  text-align: center;
}

/* Summary Section */
.summary-section {
  text-align: center;
  padding: var(--spacing-lg);
}

.summary-icon {
  color: #40c057;
  margin-bottom: var(--spacing-md);
}

.summary-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: var(--spacing-lg);
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-md);
  background: var(--color-bg);
  border-radius: var(--radius-md);
}

.stat-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
  color: white;
}

.stat-icon--userstory {
  background: #20c997;
  font-size: 0.7rem;
}

.stat-icon--bc {
  background: var(--color-bc);
  border: 2px solid var(--color-text-light);
  color: var(--color-text-light);
}

.stat-icon--aggregate { background: var(--color-aggregate); color: var(--color-bc); }
.stat-icon--command { background: var(--color-command); }
.stat-icon--event { background: var(--color-event); }
.stat-icon--policy { background: var(--color-policy); }

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-bright);
}

.stat-label {
  font-size: 0.7rem;
  color: var(--color-text-light);
}

.summary-hint {
  font-size: 0.875rem;
  color: var(--color-text-light);
}

/* Error Message */
.error-message {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: rgba(255, 100, 100, 0.1);
  border: 1px solid rgba(255, 100, 100, 0.3);
  border-radius: var(--radius-md);
  color: #ff6464;
  font-size: 0.875rem;
  margin-top: var(--spacing-md);
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-lg);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, opacity 0.15s;
}

.btn--secondary {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text);
}

.btn--secondary:hover {
  background: var(--color-bg-tertiary);
}

.btn--primary {
  background: var(--color-accent);
  border: 1px solid var(--color-accent);
  color: white;
}

.btn--primary:hover {
  background: #1c7ed6;
  border-color: #1c7ed6;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Modal Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}

/* List Transitions */
.item-list-enter-active,
.item-list-leave-active {
  transition: all 0.3s ease;
}

.item-list-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.item-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>

