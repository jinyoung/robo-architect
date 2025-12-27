<script setup>
import { computed, ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '../../stores/terminology'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Command')} >>`)

const showProperties = ref(false)
const hasProperties = computed(() => props.data.properties && props.data.properties.length > 0)

function toggleProperties(e) {
  e.stopPropagation()
  showProperties.value = !showProperties.value
}
</script>

<template>
  <div class="es-node es-node--command" :class="{ 'has-properties': hasProperties }">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.actor" class="es-node__actor">
        <!-- Stick Figure Actor -->
        <svg class="es-node__actor-icon" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="4" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/>
          <line x1="12" y1="7" x2="12" y2="15" stroke="currentColor" stroke-width="1.5"/>
          <line x1="12" y1="15" x2="8" y2="22" stroke="currentColor" stroke-width="1.5"/>
          <line x1="12" y1="15" x2="16" y2="22" stroke="currentColor" stroke-width="1.5"/>
          <line x1="6" y1="11" x2="18" y2="11" stroke="currentColor" stroke-width="1.5"/>
        </svg>
        <span>{{ data.actor }}</span>
      </div>
      
      <!-- Properties Toggle -->
      <div v-if="hasProperties" class="es-node__props-toggle" @click="toggleProperties">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline v-if="!showProperties" points="9 18 15 12 9 6"></polyline>
          <polyline v-else points="18 15 12 9 6 15"></polyline>
        </svg>
        <span>{{ data.properties.length }} params</span>
      </div>
      
      <!-- Properties List -->
      <div v-if="hasProperties && showProperties" class="es-node__props">
        <div v-for="prop in data.properties" :key="prop.id" class="es-node__prop">
          <span class="prop-name">{{ prop.name }}</span>
          <span class="prop-type">{{ prop.type }}</span>
        </div>
      </div>
    </div>
    
    <!-- Connection handles -->
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.es-node--command {
  background: linear-gradient(180deg, #5c7cfa 0%, #4263eb 100%);
  min-width: 130px;
}

.es-node--command.has-properties {
  min-width: 150px;
}

.es-node__header {
  background: rgba(0, 0, 0, 0.15);
  padding: 4px 10px;
  border-radius: 8px 8px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: rgba(255, 255, 255, 0.85);
}

.es-node__body {
  padding: 10px 12px 12px;
}

.es-node__name {
  font-size: 0.9rem;
  font-weight: 600;
  color: white;
  text-align: center;
}

.es-node__actor {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.8);
}

.es-node__actor-icon {
  width: 20px;
  height: 20px;
}

/* Properties section */
.es-node__props-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.85);
  cursor: pointer;
  transition: background 0.15s;
}

.es-node__props-toggle:hover {
  background: rgba(255, 255, 255, 0.25);
}

.es-node__props {
  margin-top: 8px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  font-size: 0.65rem;
  max-height: 100px;
  overflow-y: auto;
}

.es-node__prop {
  display: flex;
  justify-content: space-between;
  padding: 2px 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}

.es-node__prop:last-child {
  border-bottom: none;
}

.prop-name {
  font-weight: 600;
  color: white;
}

.prop-type {
  color: rgba(255, 255, 255, 0.7);
  font-style: italic;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #4263eb;
}
</style>

