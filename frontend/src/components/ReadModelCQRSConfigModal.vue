<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  readModelId: String,
  readModelData: Object,
  availableEvents: Array,
  readModelFields: Array
})

const emit = defineEmits(['close', 'save'])

// Provisioning type selection
const provisioningType = ref('CQRS')
const provisioningOptions = [
  { value: 'CQRS', label: 'CQRS', description: 'Materialized View로 복제' },
  { value: 'API', label: 'UI Mashup', description: 'API 직접 호출' },
  { value: 'GraphQL', label: 'GraphQL', description: 'GraphQL Federation' },
  { value: 'SharedDB', label: 'Shared DB', description: 'View/Join 사용' }
]

// CQRS Rules
const cqrsRules = ref([])

// Initialize from props
watch(() => props.readModelData, (newData) => {
  if (newData) {
    provisioningType.value = newData.provisioningType || 'CQRS'
    
    // Parse existing CQRS config
    if (newData.cqrsConfig) {
      try {
        const config = typeof newData.cqrsConfig === 'string' 
          ? JSON.parse(newData.cqrsConfig) 
          : newData.cqrsConfig
        cqrsRules.value = config.rules || []
      } catch (e) {
        cqrsRules.value = []
      }
    } else {
      cqrsRules.value = []
    }
  }
}, { immediate: true })

// Add new rule
function addRule(action = 'CREATE') {
  cqrsRules.value.push({
    action,
    whenEvent: '',
    setMappings: [
      { readModelField: '', operator: '=', source: 'event', eventField: '', value: '' }
    ],
    whereCondition: action !== 'CREATE' ? {
      readModelField: '',
      operator: '=',
      eventField: ''
    } : null
  })
}

// Remove rule
function removeRule(index) {
  cqrsRules.value.splice(index, 1)
}

// Add set mapping to rule
function addSetMapping(ruleIndex) {
  cqrsRules.value[ruleIndex].setMappings.push({
    readModelField: '',
    operator: '=',
    source: 'event',
    eventField: '',
    value: ''
  })
}

// Remove set mapping
function removeSetMapping(ruleIndex, mappingIndex) {
  cqrsRules.value[ruleIndex].setMappings.splice(mappingIndex, 1)
}

// Get fields for an event (if available)
function getEventFields(eventId) {
  const event = props.availableEvents?.find(e => e.id === eventId)
  return event?.properties || []
}

// Save configuration
function save() {
  const config = {
    provisioningType: provisioningType.value,
    cqrsConfig: provisioningType.value === 'CQRS' ? {
      rules: cqrsRules.value
    } : null
  }
  emit('save', props.readModelId, config)
}

// Close modal
function close() {
  emit('close')
}

// Computed for showing CQRS config section
const showCqrsConfig = computed(() => provisioningType.value === 'CQRS')
</script>

<template>
  <div v-if="visible" class="modal-overlay" @click.self="close">
    <div class="modal-container">
      <div class="modal-header">
        <h3>ReadModel 설정</h3>
        <span class="modal-subtitle">{{ readModelData?.name }}</span>
        <button class="close-btn" @click="close">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      <div class="modal-body">
        <!-- Provisioning Type Selection -->
        <div class="section">
          <h4>데이터 프로비저닝 방식</h4>
          <div class="provisioning-options">
            <label 
              v-for="option in provisioningOptions" 
              :key="option.value"
              class="provisioning-option"
              :class="{ selected: provisioningType === option.value }"
            >
              <input 
                type="radio" 
                :value="option.value" 
                v-model="provisioningType"
              />
              <div class="option-content">
                <span class="option-label">{{ option.label }}</span>
                <span class="option-desc">{{ option.description }}</span>
              </div>
            </label>
          </div>
        </div>
        
        <!-- CQRS Configuration -->
        <div v-if="showCqrsConfig" class="section cqrs-section">
          <div class="section-header">
            <h4>CQRS 규칙</h4>
            <div class="add-rule-buttons">
              <button class="btn-add" @click="addRule('CREATE')">+ CREATE</button>
              <button class="btn-add" @click="addRule('UPDATE')">+ UPDATE</button>
            </div>
          </div>
          
          <div v-if="cqrsRules.length === 0" class="empty-rules">
            규칙이 없습니다. 위 버튼을 눌러 규칙을 추가하세요.
          </div>
          
          <div 
            v-for="(rule, ruleIdx) in cqrsRules" 
            :key="ruleIdx" 
            class="cqrs-rule"
            :class="rule.action.toLowerCase()"
          >
            <div class="rule-header">
              <span class="rule-action">{{ rule.action }} WHEN</span>
              <select v-model="rule.whenEvent" class="event-select">
                <option value="">Select Event</option>
                <option 
                  v-for="evt in availableEvents" 
                  :key="evt.id" 
                  :value="evt.id"
                >
                  {{ evt.name }}
                </option>
              </select>
              <button class="btn-remove-rule" @click="removeRule(ruleIdx)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
            
            <!-- SET Mappings -->
            <div class="rule-section">
              <div class="section-label">SET</div>
              <div 
                v-for="(mapping, mapIdx) in rule.setMappings" 
                :key="mapIdx"
                class="set-mapping"
              >
                <select v-model="mapping.readModelField" class="field-select">
                  <option value="">readModelField</option>
                  <option 
                    v-for="field in readModelFields" 
                    :key="field.name" 
                    :value="field.name"
                  >
                    {{ field.name }}
                  </option>
                </select>
                
                <select v-model="mapping.operator" class="operator-select">
                  <option value="=">=</option>
                  <option value="+=">+=</option>
                </select>
                
                <template v-if="mapping.source === 'event'">
                  <select v-model="mapping.eventField" class="field-select">
                    <option value="">eventField</option>
                    <option 
                      v-for="field in getEventFields(rule.whenEvent)" 
                      :key="field.name" 
                      :value="field.name"
                    >
                      {{ field.name }}
                    </option>
                  </select>
                </template>
                <template v-else>
                  <input 
                    v-model="mapping.value" 
                    type="text" 
                    class="value-input"
                    placeholder="value"
                  />
                </template>
                
                <select v-model="mapping.source" class="source-select">
                  <option value="event">event</option>
                  <option value="value">value</option>
                </select>
                
                <button class="btn-remove" @click="removeSetMapping(ruleIdx, mapIdx)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                  </svg>
                </button>
              </div>
              <button class="btn-add-mapping" @click="addSetMapping(ruleIdx)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="16"></line>
                  <line x1="8" y1="12" x2="16" y2="12"></line>
                </svg>
              </button>
            </div>
            
            <!-- WHERE Condition (for UPDATE/DELETE) -->
            <div v-if="rule.action !== 'CREATE' && rule.whereCondition" class="rule-section">
              <div class="section-label">WHERE</div>
              <div class="where-condition">
                <select v-model="rule.whereCondition.readModelField" class="field-select">
                  <option value="">readModelField</option>
                  <option 
                    v-for="field in readModelFields" 
                    :key="field.name" 
                    :value="field.name"
                  >
                    {{ field.name }}
                  </option>
                </select>
                
                <span class="operator">=</span>
                
                <select v-model="rule.whereCondition.eventField" class="field-select">
                  <option value="">eventField</option>
                  <option 
                    v-for="field in getEventFields(rule.whenEvent)" 
                    :key="field.name" 
                    :value="field.name"
                  >
                    {{ field.name }}
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="modal-footer">
        <button class="btn-cancel" @click="close">취소</button>
        <button class="btn-save" @click="save">저장</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background: #1e1e2e;
  border-radius: 12px;
  width: 700px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #2d2d3d;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #40c057;
}

.modal-subtitle {
  color: #a0a0a0;
  font-size: 0.9rem;
}

.close-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: #808080;
  cursor: pointer;
  padding: 4px;
}

.close-btn:hover {
  color: #fff;
}

.modal-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.section {
  margin-bottom: 24px;
}

.section h4 {
  margin: 0 0 12px 0;
  font-size: 0.9rem;
  color: #c0c0c0;
}

/* Provisioning Options */
.provisioning-options {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.provisioning-option {
  flex: 1;
  min-width: 140px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: #2a2a3e;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.provisioning-option:hover {
  background: #32324e;
}

.provisioning-option.selected {
  border-color: #40c057;
  background: rgba(64, 192, 87, 0.1);
}

.provisioning-option input {
  margin-top: 2px;
  accent-color: #40c057;
}

.option-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-label {
  font-weight: 600;
  color: #e0e0e0;
  font-size: 0.85rem;
}

.option-desc {
  font-size: 0.7rem;
  color: #808080;
}

/* CQRS Section */
.cqrs-section {
  background: #252538;
  border-radius: 8px;
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
}

.add-rule-buttons {
  display: flex;
  gap: 8px;
}

.btn-add {
  background: #40c057;
  color: #fff;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-add:hover {
  background: #37a349;
}

.empty-rules {
  text-align: center;
  color: #606060;
  padding: 24px;
  font-size: 0.85rem;
}

/* CQRS Rule */
.cqrs-rule {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  border-left: 4px solid #40c057;
}

.cqrs-rule.update {
  border-left-color: #5c7cfa;
}

.cqrs-rule.delete {
  border-left-color: #ff6b6b;
}

.rule-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.rule-action {
  font-weight: 600;
  color: #40c057;
  font-size: 0.85rem;
}

.cqrs-rule.update .rule-action {
  color: #5c7cfa;
}

.event-select {
  flex: 1;
  background: #2a2a3e;
  border: 1px solid #3d3d5c;
  color: #e0e0e0;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.85rem;
}

.btn-remove-rule {
  background: none;
  border: none;
  color: #ff6b6b;
  cursor: pointer;
  padding: 4px;
  opacity: 0.7;
}

.btn-remove-rule:hover {
  opacity: 1;
}

/* Rule Sections */
.rule-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #2d2d3d;
}

.section-label {
  font-size: 0.75rem;
  color: #808080;
  font-weight: 600;
  margin-bottom: 8px;
}

/* SET Mapping */
.set-mapping {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.field-select,
.operator-select,
.source-select,
.value-input {
  background: #2a2a3e;
  border: 1px solid #3d3d5c;
  color: #e0e0e0;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.field-select {
  flex: 1;
}

.operator-select {
  width: 50px;
}

.source-select {
  width: 70px;
}

.value-input {
  flex: 1;
}

.btn-remove,
.btn-add-mapping {
  background: none;
  border: none;
  color: #808080;
  cursor: pointer;
  padding: 4px;
}

.btn-remove:hover {
  color: #ff6b6b;
}

.btn-add-mapping:hover {
  color: #40c057;
}

/* WHERE Condition */
.where-condition {
  display: flex;
  align-items: center;
  gap: 8px;
}

.operator {
  color: #808080;
  font-weight: 600;
}

/* Modal Footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #2d2d3d;
}

.btn-cancel {
  background: #3d3d5c;
  color: #c0c0c0;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-cancel:hover {
  background: #4d4d6c;
}

.btn-save {
  background: #40c057;
  color: #fff;
  border: none;
  padding: 10px 24px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-save:hover {
  background: #37a349;
}
</style>

