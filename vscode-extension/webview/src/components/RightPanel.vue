<script setup>
import { ref, computed, defineAsyncComponent, h, compile, provide } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useCanvasStore } from '../stores/canvas'
import { getApiBaseUrl } from '../utils/vscode'

// API base URL helper
const apiBase = () => getApiBaseUrl()

// Custom Nodes
import CommandNode from './nodes/CommandNode.vue'
import EventNode from './nodes/EventNode.vue'
import PolicyNode from './nodes/PolicyNode.vue'
import AggregateNode from './nodes/AggregateNode.vue'
import ReadModelNode from './nodes/ReadModelNode.vue'
import BoundedContextNode from './nodes/BoundedContextNode.vue'
import UINode from './nodes/UINode.vue'

// Modals
import ReadModelCQRSConfigModal from './ReadModelCQRSConfigModal.vue'

// Chat Panel
import ChatPanel from './ChatPanel.vue'

const canvasStore = useCanvasStore()
const isDragOver = ref(false)
const chatPanelWidth = ref(360)
const isChatPanelOpen = ref(true)

// UI Preview state
const isUIPreviewOpen = ref(false)
const previewingUI = ref(null)

// CQRS Config Modal state
const isCqrsModalOpen = ref(false)
const cqrsModalReadModelId = ref(null)
const cqrsModalReadModelData = ref(null)

const { fitView, zoomIn, zoomOut } = useVueFlow()

// Computed class for nodes to show selection state
const nodesWithSelection = computed(() => {
  return canvasStore.nodes.map(node => ({
    ...node,
    class: canvasStore.isSelected(node.id) ? 'es-node--selected' : ''
  }))
})

// Node types mapping
const nodeTypes = {
  command: CommandNode,
  event: EventNode,
  policy: PolicyNode,
  aggregate: AggregateNode,
  readmodel: ReadModelNode,
  boundedcontext: BoundedContextNode,
  ui: UINode
}

// MiniMap node color
function getNodeColor(node) {
  const colors = {
    command: '#5c7cfa',
    event: '#fd7e14',
    policy: '#b197fc',
    aggregate: '#fcc419',
    readmodel: '#40c057',
    boundedcontext: '#373a40',
    ui: '#ffffff'
  }
  return colors[node.type] || '#909296'
}

// Handle UI preview request from UINode double-click
function handleUIPreview(uiData) {
  previewingUI.value = uiData
  isUIPreviewOpen.value = true
  isChatPanelOpen.value = false  // Close chat panel when previewing UI
}

// Close UI preview
function closeUIPreview() {
  isUIPreviewOpen.value = false
  previewingUI.value = null
}

// Switch to chat for editing
function switchToChat() {
  isUIPreviewOpen.value = false
  isChatPanelOpen.value = true
  // Select the UI node for editing
  if (previewingUI.value?.id) {
    canvasStore.selectNode(previewingUI.value.id)
  }
}

// Handle drop from navigator
async function handleDrop(event) {
  event.preventDefault()
  isDragOver.value = false
  
  const data = event.dataTransfer.getData('application/json')
  if (!data) return
  
  try {
    const { nodeId } = JSON.parse(data)
    
    // Use the new API that includes BC context
    const response = await fetch(`${apiBase()}/api/graph/expand-with-bc/${nodeId}`)
    const expandedData = await response.json()
    
    // Track new node IDs for cross-BC relation finding
    const newNodeIds = expandedData.nodes.map(n => n.id)
    
    canvasStore.addNodesWithLayout(
      expandedData.nodes, 
      expandedData.relationships, 
      expandedData.bcContext
    )
    
    // Find cross-BC relations (Event → TRIGGERS → Policy between BCs)
    await canvasStore.findCrossBCRelations(newNodeIds)
    
    // Also find any other relations
    await canvasStore.findAndAddRelations()
    
    // Fit view after adding nodes
    setTimeout(() => fitView({ padding: 0.3 }), 150)
  } catch (error) {
    console.error('Failed to handle drop:', error)
  }
}

function handleDragOver(event) {
  event.preventDefault()
  isDragOver.value = true
  event.dataTransfer.dropEffect = 'copy'
}

function handleDragLeave() {
  isDragOver.value = false
}

// Watch for node changes and update positions
function onNodesChange(changes) {
  changes.forEach(change => {
    if (change.type === 'position' && change.position) {
      canvasStore.updateNodePosition(change.id, change.position)
    }
  })
}

// Handle node click for selection
function onNodeClick(event) {
  const nodeId = event.node.id
  
  // Don't select BC containers
  if (event.node.type === 'boundedcontext') {
    return
  }
  
  // Check for multi-select (Ctrl/Cmd + Click)
  if (event.event.ctrlKey || event.event.metaKey) {
    canvasStore.toggleNodeSelection(nodeId)
  } else if (event.event.shiftKey) {
    canvasStore.addToSelection(nodeId)
  } else {
    canvasStore.selectNode(nodeId)
  }
}

// Handle pane click to clear selection
function onPaneClick() {
  canvasStore.clearSelection()
}

// Toggle chat panel
function toggleChatPanel() {
  isChatPanelOpen.value = !isChatPanelOpen.value
  if (isChatPanelOpen.value) {
    isUIPreviewOpen.value = false
  }
}

// Handle node double-click (for UI preview)
function onNodeDoubleClick(event) {
  const node = event.node
  if (node.type === 'ui') {
    handleUIPreview({
      id: node.id,
      name: node.data?.name,
      template: node.data?.template,
      attachedToId: node.data?.attachedToId,
      attachedToName: node.data?.attachedToName,
      attachedToType: node.data?.attachedToType,
      userStoryId: node.data?.userStoryId
    })
  }
}

// Handle CQRS Config Modal
function openCqrsConfigModal(readModelId, readModelData) {
  cqrsModalReadModelId.value = readModelId
  cqrsModalReadModelData.value = readModelData
  isCqrsModalOpen.value = true
}

function closeCqrsConfigModal() {
  isCqrsModalOpen.value = false
  cqrsModalReadModelId.value = null
  cqrsModalReadModelData.value = null
}

// Provide the CQRS modal handler to child nodes
provide('openCqrsConfigModal', openCqrsConfigModal)
</script>

<template>
  <div class="right-panel-container">
    <!-- Canvas Area -->
    <div 
      class="right-panel"
      :class="{ 'drop-zone-active': isDragOver }"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
    >
      <div class="canvas-container">
        <!-- Empty State -->
        <div v-if="canvasStore.nodes.length === 0" class="canvas-empty">
          <div class="canvas-empty__icon">📋</div>
          <div class="canvas-empty__text">Canvas is empty</div>
          <div class="canvas-empty__hint">
            Drag items from the navigator or double-click to add
          </div>
        </div>
        
        <!-- Vue Flow Canvas -->
        <VueFlow
          v-else
          :nodes="nodesWithSelection"
          :edges="canvasStore.edges"
          :node-types="nodeTypes"
          :default-viewport="{ zoom: 0.8, x: 50, y: 50 }"
          :min-zoom="0.2"
          :max-zoom="2"
          :snap-to-grid="true"
          :snap-grid="[10, 10]"
          :nodes-draggable="true"
          :nodes-connectable="false"
          :pan-on-drag="true"
          :zoom-on-scroll="true"
          :prevent-scrolling="true"
          fit-view-on-init
          @nodes-change="onNodesChange"
          @node-click="onNodeClick"
          @node-double-click="onNodeDoubleClick"
          @pane-click="onPaneClick"
        >
          <Background pattern-color="#2a2a3a" :gap="20" />
          <Controls position="bottom-left" />
          <MiniMap 
            :node-color="getNodeColor"
            :node-stroke-width="3"
            pannable
            zoomable
          />
        </VueFlow>
      </div>
      
      <!-- Selection Info Badge -->
      <div v-if="canvasStore.selectedNodes.length > 0" class="selection-badge">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 11 12 14 22 4"></polyline>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
        <span>{{ canvasStore.selectedNodes.length }} selected</span>
        <button class="selection-badge__clear" @click="canvasStore.clearSelection()">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      <!-- Canvas Toolbar -->
      <div v-if="canvasStore.nodes.length > 0" class="canvas-toolbar">
        <button 
          class="canvas-toolbar__btn"
          @click="zoomIn()"
          title="Zoom In"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="11" y1="8" x2="11" y2="14"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>
        
        <button 
          class="canvas-toolbar__btn"
          @click="zoomOut()"
          title="Zoom Out"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>
        
        <button 
          class="canvas-toolbar__btn"
          @click="fitView({ padding: 0.3 })"
          title="Fit View"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
          </svg>
        </button>
        
        <div class="canvas-toolbar__divider"></div>
        
        <button 
          class="canvas-toolbar__btn"
          @click="canvasStore.findAndAddRelations()"
          title="Find Relations"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="18" cy="5" r="3"></circle>
            <circle cx="6" cy="12" r="3"></circle>
            <circle cx="18" cy="19" r="3"></circle>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
          </svg>
        </button>
        
        <button 
          class="canvas-toolbar__btn"
          @click="canvasStore.clearCanvas()"
          title="Clear Canvas"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
        
        <div class="canvas-toolbar__divider"></div>
        
        <!-- Chat Panel Toggle -->
        <button 
          class="canvas-toolbar__btn"
          :class="{ 'is-active': isChatPanelOpen }"
          @click="toggleChatPanel"
          title="Toggle Model Modifier"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </button>
      </div>
    </div>
    
    <!-- Chat Panel (Collapsible) -->
    <div 
      v-if="isChatPanelOpen"
      class="chat-panel-wrapper"
      :style="{ width: chatPanelWidth + 'px' }"
    >
      <ChatPanel />
    </div>
    
    <!-- UI Preview Panel -->
    <div 
      v-if="isUIPreviewOpen && previewingUI"
      class="ui-preview-wrapper"
      :style="{ width: chatPanelWidth + 'px' }"
    >
      <div class="ui-preview-panel">
        <!-- Header -->
        <div class="ui-preview-panel__header">
          <div class="ui-preview-panel__title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="3" width="20" height="18" rx="2" />
              <line x1="2" y1="7" x2="22" y2="7" />
            </svg>
            <span>UI Preview</span>
          </div>
          <div class="ui-preview-panel__actions">
            <button 
              class="ui-preview-panel__btn"
              @click="switchToChat"
              title="Edit with AI"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
            <button 
              class="ui-preview-panel__btn"
              @click="closeUIPreview"
              title="Close"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>
        
        <!-- UI Info -->
        <div class="ui-preview-panel__info">
          <div class="ui-preview-panel__name">{{ previewingUI.name }}</div>
          <div v-if="previewingUI.attachedToName" class="ui-preview-panel__attached">
            <span class="label">Attached to:</span>
            <span class="value">{{ previewingUI.attachedToName }}</span>
          </div>
        </div>
        
        <!-- Preview Content -->
        <div class="ui-preview-panel__content">
          <div v-if="previewingUI.template" class="ui-preview-frame">
            <div class="ui-preview-frame__browser-bar">
              <div class="browser-dots">
                <span></span><span></span><span></span>
              </div>
              <div class="browser-url">preview://{{ previewingUI.name }}</div>
            </div>
            <div class="ui-preview-frame__body" v-html="previewingUI.template"></div>
          </div>
          <div v-else class="ui-preview-empty">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
              <rect x="2" y="3" width="20" height="18" rx="2" />
              <line x1="2" y1="7" x2="22" y2="7" />
              <rect x="4" y="9" width="7" height="3" rx="0.5" stroke-dasharray="2 1" />
              <rect x="4" y="14" width="16" height="2" rx="0.5" stroke-dasharray="2 1" />
            </svg>
            <p>No wireframe template yet</p>
            <button class="ui-preview-empty__btn" @click="switchToChat">
              Generate with AI
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- CQRS Config Modal -->
    <ReadModelCQRSConfigModal
      :visible="isCqrsModalOpen"
      :read-model-id="cqrsModalReadModelId"
      :read-model-data="cqrsModalReadModelData"
      @close="closeCqrsConfigModal"
      @updated="() => {}"
    />
  </div>
</template>

<style>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';
@import '@vue-flow/minimap/dist/style.css';

/* Container for canvas + chat */
.right-panel-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Vue Flow custom background */
.vue-flow {
  background: #1a1b26 !important;
}

/* BC Group Node styling */
.vue-flow__node-boundedcontext {
  padding: 0 !important;
  border-radius: 16px !important;
  background: transparent !important;
  border: none !important;
}

/* Ensure child nodes are visible above parent */
.vue-flow__node {
  z-index: 1;
}

.vue-flow__node-boundedcontext {
  z-index: 0 !important;
}

/* Selected node styling */
.vue-flow__node.es-node--selected {
  outline: 3px solid var(--color-accent) !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 20px rgba(34, 139, 230, 0.4) !important;
}

/* Vue Flow Minimap custom styles */
.vue-flow__minimap {
  background: var(--color-bg-secondary) !important;
  border: 1px solid var(--color-border) !important;
  border-radius: var(--radius-md) !important;
}

/* Vue Flow Controls custom styles */
.vue-flow__controls {
  background: var(--color-bg-secondary) !important;
  border: 1px solid var(--color-border) !important;
  border-radius: var(--radius-md) !important;
  box-shadow: var(--shadow-md) !important;
}

.vue-flow__controls-button {
  background: transparent !important;
  border: none !important;
  color: var(--color-text) !important;
}

.vue-flow__controls-button:hover {
  background: var(--color-bg-tertiary) !important;
}

.vue-flow__controls-button svg {
  fill: var(--color-text) !important;
}

/* Edge labels */
.vue-flow__edge-textbg {
  fill: #1a1b26 !important;
}

.vue-flow__edge-text {
  fill: #c1c2c5 !important;
}

/* Selection Badge */
.selection-badge {
  position: absolute;
  top: var(--spacing-md);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-md);
  background: var(--color-accent);
  color: white;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
  box-shadow: var(--shadow-md);
  z-index: 10;
  animation: slideDown 0.2s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.selection-badge__clear {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.15s ease;
}

.selection-badge__clear:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* Chat Panel Wrapper */
.chat-panel-wrapper {
  flex-shrink: 0;
  height: 100%;
  overflow: hidden;
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* UI Preview Panel Wrapper */
.ui-preview-wrapper {
  flex-shrink: 0;
  height: 100%;
  overflow: hidden;
  animation: slideIn 0.2s ease;
}

.ui-preview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
}

.ui-preview-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.ui-preview-panel__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.ui-preview-panel__actions {
  display: flex;
  gap: 4px;
}

.ui-preview-panel__btn {
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.ui-preview-panel__btn:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

.ui-preview-panel__info {
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.ui-preview-panel__name {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 4px;
}

.ui-preview-panel__attached {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.ui-preview-panel__attached .label {
  opacity: 0.7;
}

.ui-preview-panel__attached .value {
  color: var(--color-accent);
  margin-left: 4px;
}

.ui-preview-panel__content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
}

/* Preview Frame (looks like browser) */
.ui-preview-frame {
  background: #ffffff;
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.ui-preview-frame__browser-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: 8px 12px;
  background: #e9ecef;
  border-bottom: 1px solid #dee2e6;
}

.browser-dots {
  display: flex;
  gap: 6px;
}

.browser-dots span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #adb5bd;
}

.browser-dots span:first-child { background: #ff6b6b; }
.browser-dots span:nth-child(2) { background: #ffd43b; }
.browser-dots span:last-child { background: #69db7c; }

.browser-url {
  flex: 1;
  font-size: 0.7rem;
  color: #495057;
  background: #f8f9fa;
  padding: 4px 10px;
  border-radius: 4px;
}

.ui-preview-frame__body {
  padding: 16px;
  min-height: 200px;
  color: #212529;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* Wireframe styles for dynamically rendered content */
.ui-preview-frame__body :deep(input),
.ui-preview-frame__body :deep(select),
.ui-preview-frame__body :deep(textarea) {
  display: block;
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 12px;
  border: 2px dashed #adb5bd;
  border-radius: 4px;
  background: #f8f9fa;
  font-size: 0.85rem;
}

.ui-preview-frame__body :deep(button) {
  padding: 8px 16px;
  border: 2px dashed #228be6;
  border-radius: 4px;
  background: #e7f5ff;
  color: #1971c2;
  font-size: 0.85rem;
  cursor: pointer;
  margin: 4px;
}

.ui-preview-frame__body :deep(label) {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: #495057;
  margin-bottom: 4px;
}

.ui-preview-frame__body :deep(h1),
.ui-preview-frame__body :deep(h2),
.ui-preview-frame__body :deep(h3) {
  color: #212529;
  margin-bottom: 12px;
}

.ui-preview-frame__body :deep(.form-group) {
  margin-bottom: 16px;
}

.ui-preview-frame__body :deep(.btn-group) {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

/* Empty state */
.ui-preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
  text-align: center;
  color: var(--color-text-light);
}

.ui-preview-empty p {
  margin: var(--spacing-md) 0;
  font-size: 0.875rem;
}

.ui-preview-empty__btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ui-preview-empty__btn:hover {
  background: #1c7ed6;
  transform: translateY(-1px);
}
</style>
