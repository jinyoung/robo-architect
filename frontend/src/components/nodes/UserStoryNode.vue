<script setup>
import { computed, inject } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  id: String,
  data: Object
})

// Inject edit function from parent
const editUserStory = inject('editUserStory', null)

const displayName = computed(() => {
  if (props.data?.name) return props.data.name
  if (props.data?.role && props.data?.action) {
    return `${props.data.role}: ${props.data.action?.substring(0, 25)}...`
  }
  return props.id
})

const roleText = computed(() => props.data?.role || 'User')

function handleDoubleClick() {
  if (editUserStory) {
    editUserStory({
      id: props.id,
      ...props.data
    })
  }
}
</script>

<template>
  <div 
    class="es-node es-node--userstory"
    @dblclick="handleDoubleClick"
    :title="`As a ${data.role}, I want to ${data.action} so that ${data.benefit}`"
  >
    <div class="es-node__header">
      << User Story >>
    </div>
    <div class="es-node__body">
      <div class="es-node__role">{{ roleText }}</div>
      <div class="es-node__name">{{ displayName }}</div>
    </div>
    
    <!-- Connection handles -->
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.es-node--userstory {
  background: linear-gradient(180deg, #20c997 0%, #12b886 100%);
  min-width: 160px;
  max-width: 200px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(32, 201, 151, 0.3);
}

.es-node--userstory:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(32, 201, 151, 0.4);
}

.es-node__header {
  background: rgba(0, 0, 0, 0.15);
  padding: 4px 10px;
  border-radius: 10px 10px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: rgba(255, 255, 255, 0.85);
}

.es-node__body {
  padding: 8px 12px 12px;
}

.es-node__role {
  font-size: 0.65rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  text-align: center;
  margin-bottom: 4px;
  text-transform: capitalize;
}

.es-node__name {
  font-size: 0.8rem;
  font-weight: 600;
  color: white;
  text-align: center;
  line-height: 1.3;
  word-wrap: break-word;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #12b886;
}
</style>

