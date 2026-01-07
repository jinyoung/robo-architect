<script setup>
import { ref, computed, onMounted, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'close', 'complete', 'prd-generated'])

// API URL
const API_BASE = 'http://localhost:8000'

// State
const phase = ref('idle') // idle, generating_prd, prd_ready, error
const message = ref('')
const error = ref(null)

// PRD state
const prdContent = ref('')
const prdSummary = ref(null)
const isGeneratingPrd = ref(false)

// Legacy data summary
const legacySummary = ref(null)
const isLoadingSummary = ref(false)

// Computed
const hasLegacyData = computed(() => {
  return legacySummary.value?.hasLegacyData ?? false
})

// Load legacy summary on mount
async function loadLegacySummary() {
  isLoadingSummary.value = true
  try {
    const response = await fetch(`${API_BASE}/api/legacy/summary`)
    if (response.ok) {
      legacySummary.value = await response.json()
    }
  } catch (e) {
    console.error('Failed to load legacy summary:', e)
  } finally {
    isLoadingSummary.value = false
  }
}

// Generate PRD from legacy system
async function generatePRD() {
  if (!hasLegacyData.value) return
  
  phase.value = 'generating_prd'
  isGeneratingPrd.value = true
  message.value = '레거시 시스템에서 PRD 문서 생성 중...'
  error.value = null
  
  try {
    const response = await fetch(`${API_BASE}/api/legacy/generate-prd`, {
      method: 'POST'
    })
    
    if (!response.ok) {
      throw new Error('PRD 생성 실패')
    }
    
    const data = await response.json()
    
    if (!data.success) {
      throw new Error(data.message || 'PRD 생성 실패')
    }
    
    prdContent.value = data.prd_content
    prdSummary.value = data.source_summary
    phase.value = 'prd_ready'
    message.value = data.message
    
  } catch (e) {
    phase.value = 'error'
    error.value = e.message
  } finally {
    isGeneratingPrd.value = false
  }
}

// Start Event Storming - emit PRD to parent and open IngestionModal
function startEventStorming() {
  if (!prdContent.value) return
  
  // PRD 내용을 부모에게 전달하고 기존 문서 업로드 UI 사용
  emit('prd-generated', prdContent.value)
  
  // 이 모달 닫기
  emit('close')
  emit('update:visible', false)
}


// Close modal
function handleClose() {
  emit('close')
  emit('update:visible', false)
}

// Reset state
function resetState() {
  phase.value = 'idle'
  message.value = ''
  error.value = null
  prdContent.value = ''
  prdSummary.value = null
}

// Go back to PRD
function backToPrd() {
  phase.value = 'prd_ready'
  message.value = ''
  error.value = null
}

// Watch visibility
watch(() => props.visible, (newVal) => {
  if (newVal) {
    resetState()
    loadLegacySummary()
  }
})

onMounted(() => {
  if (props.visible) {
    loadLegacySummary()
  }
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container" :class="{ 'wide': phase === 'prd_ready' }">
        <header class="modal-header">
          <h2>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3v18"/>
              <path d="M18.7 8l-12 12"/>
              <path d="M5.3 8l12 12"/>
            </svg>
            레거시 시스템 → Event Storming
          </h2>
          <button class="close-btn" @click="handleClose">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </header>
        
        <div class="modal-body">
          <!-- Step 1: Idle State - Show summary and generate PRD button -->
          <div v-if="phase === 'idle'" class="idle-state">
            <div class="workflow-steps">
              <div class="step active">
                <div class="step-number">1</div>
                <div class="step-label">PRD 생성</div>
              </div>
              <div class="step-arrow">→</div>
              <div class="step">
                <div class="step-number">2</div>
                <div class="step-label">검토</div>
              </div>
              <div class="step-arrow">→</div>
              <div class="step">
                <div class="step-number">3</div>
                <div class="step-label">Event Storming</div>
              </div>
            </div>
            
            <div class="description">
              <p>
                레거시 시스템의 <strong>테이블 구조</strong>와 <strong>스토어드 프로시저 설명</strong>을 분석하여
                먼저 <strong>PRD(요구사항 문서)</strong>를 생성합니다.
              </p>
              <p class="hint">
                💡 PRD에는 User Story, Acceptance Criteria, 비즈니스 규칙이 포함됩니다.
              </p>
            </div>
            
            <!-- Summary Card -->
            <div v-if="isLoadingSummary" class="summary-card loading">
              <div class="spinner"></div>
              <span>레거시 데이터 확인 중...</span>
            </div>
            
            <div v-else-if="legacySummary" class="summary-card" :class="{ 'has-data': hasLegacyData }">
              <div class="summary-title">
                {{ hasLegacyData ? '✅ 분석 가능한 데이터 발견' : '❌ 분석할 데이터 없음' }}
              </div>
              
              <div v-if="hasLegacyData" class="summary-stats">
                <div class="stat">
                  <span class="stat-value">{{ legacySummary.tables?.total || 0 }}</span>
                  <span class="stat-label">테이블</span>
                </div>
                <div class="stat">
                  <span class="stat-value">{{ legacySummary.procedures?.total || 0 }}</span>
                  <span class="stat-label">프로시저</span>
                </div>
                <div class="stat">
                  <span class="stat-value">{{ legacySummary.relationships || 0 }}</span>
                  <span class="stat-label">FK 관계</span>
                </div>
              </div>
              
              <div v-if="hasLegacyData && legacySummary.procedures?.byType" class="type-breakdown">
                <span v-for="(count, type) in legacySummary.procedures.byType" :key="type" class="type-badge">
                  {{ type }}: {{ count }}
                </span>
              </div>
            </div>
            
            <button 
              class="analyze-btn"
              :disabled="!hasLegacyData"
              @click="generatePRD"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
              PRD 문서 생성
            </button>
          </div>
          
          <!-- Step 1.5: Generating PRD -->
          <div v-else-if="phase === 'generating_prd'" class="generating-state">
            <div class="phase-indicator">
              <div class="phase-icon spinning">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <div class="phase-label">PRD 문서 생성 중...</div>
              <div class="phase-sublabel">프로시저 summary를 분석하여 요구사항을 도출합니다</div>
            </div>
            <div class="loading-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
          
          <!-- Step 2: PRD Ready - Show and confirm PRD -->
          <div v-else-if="phase === 'prd_ready'" class="prd-ready-state">
            <div class="workflow-steps">
              <div class="step done">
                <div class="step-number">✓</div>
                <div class="step-label">PRD 생성</div>
              </div>
              <div class="step-arrow">→</div>
              <div class="step active">
                <div class="step-number">2</div>
                <div class="step-label">검토</div>
              </div>
              <div class="step-arrow">→</div>
              <div class="step">
                <div class="step-number">3</div>
                <div class="step-label">Event Storming</div>
              </div>
            </div>
            
            <div v-if="prdSummary" class="prd-source-info">
              <span>📊 분석 소스: {{ prdSummary.tables }}개 테이블, {{ prdSummary.procedures_with_summary }}개 프로시저 summary</span>
            </div>
            
            <div class="prd-preview">
              <div class="prd-header">
                <h4>📄 생성된 PRD 문서</h4>
                <button class="copy-btn" @click="navigator.clipboard.writeText(prdContent)">
                  복사
                </button>
              </div>
              <div class="prd-content">
                <pre>{{ prdContent }}</pre>
              </div>
            </div>
            
            <div class="prd-info-box">
              <p>💡 "Event Storming 도출 시작"을 클릭하면 기존 <strong>문서 업로드</strong> 화면이 열리고,<br/>위 PRD가 자동으로 입력됩니다.</p>
            </div>
            
            <div class="prd-actions">
              <button class="back-btn" @click="resetState">
                ← 다시 생성
              </button>
              <button class="proceed-btn" @click="startEventStorming">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                Event Storming 도출 시작 →
              </button>
            </div>
          </div>
          
          <!-- Error State -->
          <div v-else-if="phase === 'error'" class="error-state">
            <div class="error-icon">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            
            <h3>오류가 발생했습니다</h3>
            <p class="error-message">{{ error }}</p>
            
            <div class="error-actions">
              <button class="retry-btn" @click="resetState">
                처음부터 다시
              </button>
              <button v-if="prdContent" class="back-btn" @click="backToPrd">
                PRD로 돌아가기
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-container {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-lg);
  width: 560px;
  max-height: 85vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  animation: modal-enter 0.25s ease-out;
  transition: width 0.3s ease;
}

.modal-container.wide {
  width: 800px;
}

@keyframes modal-enter {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #059669 0%, #10b981 100%);
}

.modal-header h2 {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin: 0;
  font-size: 1.25rem;
  color: white;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: var(--radius-sm);
  padding: 6px;
  cursor: pointer;
  color: white;
  transition: background 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.modal-body {
  padding: var(--spacing-lg);
  max-height: 70vh;
  overflow-y: auto;
}

/* Workflow Steps */
.workflow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
}

.workflow-steps.small {
  padding: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.step-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-bg-secondary);
  border: 2px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
}

.step.active .step-number {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: white;
}

.step.done .step-number {
  background: #10b981;
  border-color: #10b981;
  color: white;
}

.step-label {
  font-size: 0.7rem;
  color: var(--color-text-light);
}

.step.active .step-label,
.step.done .step-label {
  color: var(--color-text);
  font-weight: 500;
}

.step-arrow {
  color: var(--color-text-light);
  font-size: 0.9rem;
}

/* Idle State */
.idle-state .description {
  margin-bottom: var(--spacing-lg);
}

.idle-state .description p {
  margin: 0 0 var(--spacing-sm);
  color: var(--color-text);
  line-height: 1.6;
}

.idle-state .hint {
  color: var(--color-text-light);
  font-size: 0.875rem;
}

/* Summary Card */
.summary-card {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
}

.summary-card.loading {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  color: var(--color-text-light);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.summary-card.has-data {
  border-color: #059669;
  background: rgba(5, 150, 105, 0.1);
}

.summary-title {
  font-weight: 600;
  margin-bottom: var(--spacing-md);
}

.summary-stats {
  display: flex;
  gap: var(--spacing-xl);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-accent);
}

.stat-label {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.type-breakdown {
  margin-top: var(--spacing-md);
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.type-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
}

.analyze-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #059669 0%, #10b981 100%);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.analyze-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(5, 150, 105, 0.4);
}

.analyze-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Generating State */
.generating-state {
  text-align: center;
  padding: var(--spacing-xl) 0;
}

.phase-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-md);
}

.phase-icon {
  color: var(--color-accent);
}

.phase-icon.spinning {
  animation: spin 2s linear infinite;
}

.phase-label {
  font-size: 1.1rem;
  font-weight: 600;
}

.phase-sublabel {
  font-size: 0.875rem;
  color: var(--color-text-light);
}

.loading-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: var(--spacing-lg);
}

.loading-dots span {
  width: 10px;
  height: 10px;
  background: var(--color-accent);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* PRD Ready State */
.prd-ready-state {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.prd-source-info {
  font-size: 0.8rem;
  color: var(--color-text-light);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
}

.prd-preview {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.prd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-tertiary);
  border-bottom: 1px solid var(--color-border);
}

.prd-header h4 {
  margin: 0;
  font-size: 0.9rem;
}

.copy-btn {
  padding: 4px 12px;
  background: var(--color-accent);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  font-size: 0.75rem;
  cursor: pointer;
}

.prd-content {
  max-height: 300px;
  overflow-y: auto;
  padding: var(--spacing-md);
  background: var(--color-bg-primary);
}

.prd-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--color-text);
}

.prd-info-box {
  padding: var(--spacing-md);
  background: rgba(34, 139, 230, 0.1);
  border: 1px solid rgba(34, 139, 230, 0.3);
  border-radius: var(--radius-md);
  margin-top: var(--spacing-md);
}

.prd-info-box p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--color-text);
  line-height: 1.5;
}

.prd-actions {
  display: flex;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.back-btn {
  flex: 1;
  padding: var(--spacing-md);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.15s;
}

.back-btn:hover {
  background: var(--color-bg-secondary);
}

.proceed-btn {
  flex: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: linear-gradient(135deg, var(--color-accent) 0%, #1c7ed6 100%);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.proceed-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(34, 139, 230, 0.4);
}

/* Analyzing State */
.analyzing-state {
  text-align: center;
}

.progress-bar {
  height: 8px;
  background: var(--color-bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
  margin-top: var(--spacing-lg);
}

.progress-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.progress-text {
  margin-top: var(--spacing-sm);
  font-size: 0.875rem;
  color: var(--color-text-light);
}

.message {
  margin-top: var(--spacing-md);
  color: var(--color-text);
}

.created-list {
  margin-top: var(--spacing-lg);
  text-align: left;
}

.created-header {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-sm);
}

.created-items {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.created-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 6px 10px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
}

.item-type {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
}

.created-item.userstory .item-type { background: #6366f1; color: white; }
.created-item.boundedcontext .item-type { background: rgba(255, 255, 255, 0.1); }
.created-item.aggregate .item-type { background: var(--color-aggregate); color: black; }
.created-item.command .item-type { background: var(--color-command); color: white; }
.created-item.event .item-type { background: var(--color-event); color: black; }
.created-item.readmodel .item-type { background: #22d3ee; color: black; }
.created-item.ui .item-type { background: #a78bfa; color: white; }
.created-item.policy .item-type { background: var(--color-policy); color: black; }
.created-item.property .item-type { background: #94a3b8; color: white; }

/* Complete State */
.complete-state {
  text-align: center;
}

.success-icon {
  color: #10b981;
  margin-bottom: var(--spacing-lg);
}

.complete-state h3 {
  margin: 0 0 var(--spacing-lg);
}

.result-summary {
  margin-bottom: var(--spacing-lg);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--spacing-sm);
}

.summary-grid.secondary {
  margin-top: var(--spacing-sm);
  grid-template-columns: repeat(4, 1fr);
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-md);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
}

.summary-item .count {
  font-size: 1.5rem;
  font-weight: 700;
}

.summary-item .label {
  font-size: 0.6rem;
  color: var(--color-text-light);
  text-align: center;
}

.summary-item.us .count { color: #6366f1; }
.summary-item.bc .count { color: var(--color-text); }
.summary-item.agg .count { color: var(--color-aggregate); }
.summary-item.cmd .count { color: var(--color-command); }
.summary-item.evt .count { color: var(--color-event); }
.summary-item.rm .count { color: #22d3ee; }
.summary-item.ui .count { color: #a78bfa; }
.summary-item.pol .count { color: var(--color-policy); }
.summary-item.prop .count { color: #94a3b8; }

.done-btn {
  padding: var(--spacing-md) var(--spacing-xl);
  background: linear-gradient(135deg, var(--color-accent) 0%, #1c7ed6 100%);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.done-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(34, 139, 230, 0.4);
}

/* Error State */
.error-state {
  text-align: center;
}

.error-icon {
  color: var(--color-event);
  margin-bottom: var(--spacing-lg);
}

.error-state h3 {
  margin: 0 0 var(--spacing-md);
  color: var(--color-event);
}

.error-message {
  color: var(--color-text-light);
  margin-bottom: var(--spacing-lg);
}

.error-actions {
  display: flex;
  gap: var(--spacing-md);
  justify-content: center;
}

.retry-btn {
  padding: var(--spacing-md) var(--spacing-xl);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.15s;
}

.retry-btn:hover {
  background: var(--color-bg-secondary);
}
</style>
