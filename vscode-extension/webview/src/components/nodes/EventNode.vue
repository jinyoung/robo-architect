<script setup>
import { ref, computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useCanvasStore } from '../../stores/canvas'
import { useTerminologyStore } from '../../stores/terminology'

const props = defineProps({
  id: String,
  data: Object
})

const canvasStore = useCanvasStore()
const terminologyStore = useTerminologyStore()
const isExpanding = ref(false)
const showProperties = ref(false)

const headerText = computed(() => `<< ${terminologyStore.getTerm('Event')} >>`)
const hasProperties = computed(() => props.data.properties && props.data.properties.length > 0)

function toggleProperties(e) {
  e.stopPropagation()
  showProperties.value = !showProperties.value
}

// Double-click to expand triggered policies
async function handleDoubleClick() {
  if (isExpanding.value) return
  
  isExpanding.value = true
  try {
    const newNodes = await canvasStore.expandEventTriggers(props.id)
    if (newNodes.length > 0) {
      console.log(`Expanded ${newNodes.length} nodes from event triggers`)
    }
  } finally {
    isExpanding.value = false
  }
}
</script>

<template>
  <div 
    class="es-node es-node--event"
    :class="{ 'is-expanding': isExpanding, 'has-properties': hasProperties }"
    @dblclick="handleDoubleClick"
  >
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.version" class="es-node__version">
        v{{ data.version }}
      </div>
      <div v-if="isExpanding" class="es-node__loading">
        Expanding...
      </div>
      
      <!-- Properties Toggle -->
      <div v-if="hasProperties" class="es-node__props-toggle" @click="toggleProperties">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline v-if="!showProperties" points="9 18 15 12 9 6"></polyline>
          <polyline v-else points="18 15 12 9 6 15"></polyline>
        </svg>
        <span>{{ data.properties.length }} attrs</span>
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
.es-node--event {
  background: linear-gradient(180deg, #fd7e14 0%, #e8590c 100%);
  min-width: 130px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.es-node--event.has-properties {
  min-width: 150px;
}

.es-node--event:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(253, 126, 20, 0.4);
}

.es-node--event.is-expanding {
  opacity: 0.7;
  pointer-events: none;
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

.es-node__version {
  margin-top: 4px;
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.7);
  text-align: center;
}

.es-node__loading {
  margin-top: 6px;
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.8);
  text-align: center;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
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
  border: 2px solid #e8590c;
}
</style>

