<script setup>
import { computed, inject } from 'vue'
import { useCanvasStore } from '../../stores/canvas'

const props = defineProps({
  id: String,
  data: Object
})

const canvasStore = useCanvasStore()

// Get the display name
const displayName = computed(() => {
  return props.data?.name || props.id?.replace('BC-', '') || 'Context'
})

// Check if this BC is collapsed
const isCollapsed = computed(() => {
  return props.data?.collapsed ?? canvasStore.isBCCollapsed(props.id)
})

// Toggle collapse/expand
function handleToggle(event) {
  event.stopPropagation()
  canvasStore.toggleBCCollapse(props.id)
}

// Delete this BC
function handleDelete(event) {
  event.stopPropagation()
  canvasStore.removeBCWithChildren(props.id)
}
</script>

<template>
  <div class="bc-container" :class="{ 'bc-container--collapsed': isCollapsed }">
    <!-- Header -->
    <div class="bc-container__header">
      <button 
        class="bc-container__toggle"
        @click="handleToggle"
        :title="isCollapsed ? 'Expand' : 'Collapse'"
      >
        <svg 
          width="14" 
          height="14" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          stroke-width="2"
          :style="{ transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }"
        >
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      <span class="bc-container__name">{{ displayName.toLowerCase() }}</span>
      <div class="bc-container__actions">
        <button 
          class="bc-container__delete"
          @click="handleDelete"
          title="Remove from canvas"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>
    
    <!-- Body - children will be rendered by Vue Flow inside this -->
    <div v-if="!isCollapsed" class="bc-container__body">
      <!-- Child nodes are automatically placed here by Vue Flow -->
    </div>
  </div>
</template>

<style scoped>
.bc-container {
  width: 100%;
  height: 100%;
  background: rgba(40, 42, 54, 0.6);
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  overflow: visible;
  box-shadow: 
    0 4px 24px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: all 0.3s ease;
}

.bc-container--collapsed {
  background: rgba(40, 42, 54, 0.9);
  border-color: rgba(139, 92, 246, 0.4);
}

.bc-container__header {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
  border-radius: 14px 14px 0 0;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: grab;
}

.bc-container--collapsed .bc-container__header {
  border-bottom: none;
  border-radius: 14px;
}

.bc-container__header:active {
  cursor: grabbing;
}

.bc-container__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.bc-container__toggle:hover {
  background: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.95);
}

.bc-container__toggle svg {
  transition: transform 0.25s ease;
}

.bc-container__name {
  font-size: 0.95rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 0.02em;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bc-container__actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.bc-container:hover .bc-container__actions {
  opacity: 1;
}

.bc-container__delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  background: rgba(239, 68, 68, 0.2);
  border: none;
  border-radius: 4px;
  color: rgba(239, 68, 68, 0.8);
  cursor: pointer;
  transition: all 0.2s ease;
}

.bc-container__delete:hover {
  background: rgba(239, 68, 68, 0.4);
  color: #ef4444;
}

.bc-container__body {
  position: relative;
  width: 100%;
  height: calc(100% - 48px);
  padding: 16px;
}

/* Make the node draggable only from header */
:deep(.vue-flow__node) {
  cursor: default;
}
</style>
