<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  step: {
    type: String,
    required: true
  },
  stepLabel: {
    type: String,
    required: true
  },
  items: {
    type: Array,
    default: () => []
  },
  message: {
    type: String,
    default: ''
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['approve', 'regenerate'])

const feedback = ref('')
const showFeedbackInput = ref(false)

const hasItems = computed(() => props.items && props.items.length > 0)

function handleApprove() {
  emit('approve')
}

function handleRegenerate() {
  if (!showFeedbackInput.value) {
    showFeedbackInput.value = true
    return
  }
  
  if (!feedback.value.trim()) {
    return
  }
  
  emit('regenerate', feedback.value)
  feedback.value = ''
  showFeedbackInput.value = false
}

function cancelFeedback() {
  showFeedbackInput.value = false
  feedback.value = ''
}

// Get display info for each item type
function getItemDisplay(item) {
  // User Story
  if (item.role && item.action) {
    return {
      primary: `[${item.id}] ${item.role}`,
      secondary: item.action,
      tertiary: item.benefit,
      type: 'UserStory',
      icon: 'US'
    }
  }
  
  // Bounded Context
  if (item.description && item.userStoryIds) {
    return {
      primary: `[${item.id}] ${item.name}`,
      secondary: item.description,
      tertiary: `User Stories: ${item.userStoryIds?.join(', ') || 'None'}`,
      type: 'BoundedContext',
      icon: 'BC'
    }
  }
  
  // User Story Mapping
  if (item.usId && item.bcId) {
    return {
      primary: item.usId,
      secondary: `→ ${item.bcName}`,
      type: 'Mapping',
      icon: '→'
    }
  }
  
  // Aggregate
  if (item.rootEntity || item.bcName) {
    return {
      primary: `[${item.id}] ${item.name}`,
      secondary: `BC: ${item.bcName}`,
      tertiary: item.rootEntity ? `Root: ${item.rootEntity}` : '',
      type: 'Aggregate',
      icon: 'A'
    }
  }
  
  // Command
  if (item.aggregateName && item.actor) {
    return {
      primary: `[${item.id}] ${item.name}`,
      secondary: `Aggregate: ${item.aggregateName}`,
      tertiary: `Actor: ${item.actor}`,
      type: 'Command',
      icon: 'C'
    }
  }
  
  // Event
  if (item.commandId) {
    return {
      primary: `[${item.id}] ${item.name}`,
      secondary: `Aggregate: ${item.aggregateName}`,
      type: 'Event',
      icon: 'E'
    }
  }
  
  // Policy
  if (item.triggerEvent && item.invokeCommand) {
    return {
      primary: `[${item.id}] ${item.name}`,
      secondary: `${item.triggerEvent} → ${item.invokeCommand}`,
      tertiary: item.description,
      type: 'Policy',
      icon: 'P'
    }
  }
  
  // Default
  return {
    primary: item.name || item.id || JSON.stringify(item),
    secondary: '',
    type: 'Unknown',
    icon: '?'
  }
}

function getIconClass(type) {
  const classes = {
    UserStory: 'icon--userstory',
    BoundedContext: 'icon--bc',
    Aggregate: 'icon--aggregate',
    Command: 'icon--command',
    Event: 'icon--event',
    Policy: 'icon--policy',
    Mapping: 'icon--mapping'
  }
  return classes[type] || ''
}
</script>

<template>
  <div class="step-review">
    <!-- Header -->
    <div class="step-review__header">
      <h3 class="step-review__title">
        <span class="step-badge">{{ stepLabel }}</span>
        검토
      </h3>
      <p class="step-review__message">{{ message }}</p>
    </div>
    
    <!-- Items List -->
    <div class="step-review__content">
      <div v-if="!hasItems" class="step-review__empty">
        생성된 항목이 없습니다
      </div>
      
      <div v-else class="step-review__items">
        <div 
          v-for="(item, index) in items" 
          :key="item.id || index"
          class="review-item"
        >
          <span class="review-item__icon" :class="getIconClass(getItemDisplay(item).type)">
            {{ getItemDisplay(item).icon }}
          </span>
          <div class="review-item__content">
            <div class="review-item__primary">{{ getItemDisplay(item).primary }}</div>
            <div v-if="getItemDisplay(item).secondary" class="review-item__secondary">
              {{ getItemDisplay(item).secondary }}
            </div>
            <div v-if="getItemDisplay(item).tertiary" class="review-item__tertiary">
              {{ getItemDisplay(item).tertiary }}
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Feedback Input -->
    <div v-if="showFeedbackInput" class="step-review__feedback">
      <textarea
        v-model="feedback"
        class="feedback-input"
        placeholder="수정이 필요한 내용을 자연어로 입력하세요...&#10;예: 'Order와 Inventory BC를 하나로 합쳐주세요'&#10;예: 'Customer 역할 대신 Buyer 역할을 사용해주세요'"
        rows="4"
      ></textarea>
      <div class="feedback-actions">
        <button class="btn btn--ghost" @click="cancelFeedback">
          취소
        </button>
        <button 
          class="btn btn--warning" 
          @click="handleRegenerate"
          :disabled="!feedback.trim()"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          피드백 반영하여 재생성
        </button>
      </div>
    </div>
    
    <!-- Actions -->
    <div v-else class="step-review__actions">
      <button 
        class="btn btn--secondary"
        @click="handleRegenerate"
        :disabled="isLoading"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
        </svg>
        수정 요청
      </button>
      <button 
        class="btn btn--primary"
        @click="handleApprove"
        :disabled="isLoading"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        확인 및 다음 단계
      </button>
    </div>
  </div>
</template>

<style scoped>
.step-review {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.step-review__header {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
}

.step-review__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0 0 var(--spacing-xs) 0;
}

.step-badge {
  padding: 2px 8px;
  background: var(--color-accent);
  color: white;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.step-review__message {
  font-size: 0.85rem;
  color: var(--color-text);
  margin: 0;
}

.step-review__content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
}

.step-review__empty {
  text-align: center;
  color: var(--color-text-light);
  padding: var(--spacing-xl);
}

.step-review__items {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.review-item {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--color-bg);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.review-item__icon {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.icon--userstory { background: #20c997; }
.icon--bc { background: var(--color-bc); border: 2px solid var(--color-text-light); color: var(--color-text-light); }
.icon--aggregate { background: var(--color-aggregate); color: var(--color-bc); }
.icon--command { background: var(--color-command); }
.icon--event { background: var(--color-event); }
.icon--policy { background: var(--color-policy); }
.icon--mapping { background: var(--color-text-light); font-size: 1rem; }

.review-item__content {
  flex: 1;
  min-width: 0;
}

.review-item__primary {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-text-bright);
  word-break: break-word;
}

.review-item__secondary {
  font-size: 0.8rem;
  color: var(--color-text);
  margin-top: 2px;
  word-break: break-word;
}

.review-item__tertiary {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-top: 2px;
  font-style: italic;
}

.step-review__feedback {
  padding: var(--spacing-md);
  border-top: 1px solid var(--color-border);
  background: rgba(255, 193, 7, 0.05);
}

.feedback-input {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--color-bg);
  border: 1px solid rgba(255, 193, 7, 0.5);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.85rem;
  line-height: 1.4;
  resize: vertical;
}

.feedback-input:focus {
  outline: none;
  border-color: #ffc107;
}

.feedback-input::placeholder {
  color: var(--color-text-light);
}

.feedback-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
}

.step-review__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border-top: 1px solid var(--color-border);
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, opacity 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn--primary {
  background: var(--color-accent);
  border: 1px solid var(--color-accent);
  color: white;
}

.btn--primary:hover:not(:disabled) {
  background: #1c7ed6;
  border-color: #1c7ed6;
}

.btn--secondary {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text);
}

.btn--secondary:hover:not(:disabled) {
  background: var(--color-bg-tertiary);
}

.btn--warning {
  background: #ffc107;
  border: 1px solid #ffc107;
  color: #1a1a1a;
}

.btn--warning:hover:not(:disabled) {
  background: #e0a800;
  border-color: #e0a800;
}

.btn--ghost {
  background: transparent;
  border: 1px solid transparent;
  color: var(--color-text-light);
}

.btn--ghost:hover:not(:disabled) {
  color: var(--color-text);
}
</style>

