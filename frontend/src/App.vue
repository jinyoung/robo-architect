<script setup>
import { ref, provide } from 'vue'
import TopBar from './components/TopBar.vue'
import LeftPanel from './components/LeftPanel.vue'
import RightPanel from './components/RightPanel.vue'
import UserStoryEditModal from './components/UserStoryEditModal.vue'
import { useCanvasStore } from './stores/canvas'
import { useNavigatorStore } from './stores/navigator'

const canvasStore = useCanvasStore()
const navigatorStore = useNavigatorStore()

// User Story Modal state (supports both create and edit modes)
const showModal = ref(false)
const modalMode = ref('edit') // 'create' or 'edit'
const editingUserStory = ref(null)
const targetBcId = ref(null)

// Edit an existing user story
function handleEditUserStory(userStory) {
  editingUserStory.value = userStory
  modalMode.value = 'edit'
  targetBcId.value = null
  showModal.value = true
}

// Create a new user story (optionally in a specific BC)
function handleAddUserStory(bcId = null) {
  editingUserStory.value = null
  modalMode.value = 'create'
  targetBcId.value = bcId
  showModal.value = true
}

function handleCloseModal() {
  showModal.value = false
  editingUserStory.value = null
  targetBcId.value = null
}

async function handleUserStorySaved() {
  // Refresh the navigator to reflect changes
  await navigatorStore.refreshAll()
}

async function handleUserStoryCreated() {
  // Refresh the navigator to show new user story
  await navigatorStore.refreshAll()
}

// Provide canvas store and modal functions to child components
provide('canvasStore', canvasStore)
provide('editUserStory', handleEditUserStory)
provide('addUserStory', handleAddUserStory)
</script>

<template>
  <div class="app-container">
    <TopBar />
    <div class="main-content">
      <LeftPanel />
      <RightPanel />
    </div>
    
    <!-- User Story Modal (Create & Edit) -->
    <UserStoryEditModal 
      :visible="showModal"
      :mode="modalMode"
      :user-story="editingUserStory"
      :target-bc-id="targetBcId"
      @close="handleCloseModal"
      @saved="handleUserStorySaved"
      @created="handleUserStoryCreated"
    />
  </div>
</template>

