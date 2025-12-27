<script setup>
import { computed, ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '../../stores/terminology'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Aggregate')} >>`)

const showProperties = ref(false)
const hasProperties = computed(() => props.data.properties && props.data.properties.length > 0)

function toggleProperties(e) {
  e.stopPropagation()
  showProperties.value = !showProperties.value
}
</script>

<template>
  <div class="es-node es-node--aggregate" :class="{ 'has-properties': hasProperties }">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.rootEntity" class="es-node__root">
        {{ data.rootEntity }}
      </div>
      
      <!-- Properties Toggle -->
      <div v-if="hasProperties" class="es-node__props-toggle" @click="toggleProperties">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline v-if="!showProperties" points="9 18 15 12 9 6"></polyline>
          <polyline v-else points="18 15 12 9 6 15"></polyline>
        </svg>
        <span>{{ data.properties.length }} fields</span>
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
    <Handle type="target" :position="Position.Top" />
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.es-node--aggregate {
  background: linear-gradient(180deg, #fcc419 0%, #f59f00 100%);
  min-width: 140px;
}

.es-node--aggregate.has-properties {
  min-width: 160px;
}

.es-node__header {
  background: rgba(0, 0, 0, 0.1);
  padding: 4px 10px;
  border-radius: 8px 8px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: rgba(0, 0, 0, 0.7);
}

.es-node__body {
  padding: 10px 12px 12px;
}

.es-node__name {
  font-size: 0.95rem;
  font-weight: 700;
  color: #212529;
  text-align: center;
}

.es-node__root {
  margin-top: 4px;
  font-size: 0.7rem;
  color: rgba(0, 0, 0, 0.6);
  text-align: center;
}

/* Properties section */
.es-node__props-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  font-size: 0.65rem;
  color: rgba(0, 0, 0, 0.7);
  cursor: pointer;
  transition: background 0.15s;
}

.es-node__props-toggle:hover {
  background: rgba(0, 0, 0, 0.15);
}

.es-node__props {
  margin-top: 8px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.4);
  border-radius: 4px;
  font-size: 0.65rem;
  max-height: 120px;
  overflow-y: auto;
}

.es-node__prop {
  display: flex;
  justify-content: space-between;
  padding: 2px 4px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.es-node__prop:last-child {
  border-bottom: none;
}

.prop-name {
  font-weight: 600;
  color: #212529;
}

.prop-type {
  color: rgba(0, 0, 0, 0.6);
  font-style: italic;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #f59f00;
}
</style>

