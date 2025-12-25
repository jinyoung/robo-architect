import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNavigatorStore = defineStore('navigator', () => {
  const contexts = ref([])
  const contextTrees = ref({})
  const userStories = ref([])  // Unassigned user stories at root level
  const loading = ref(false)
  const error = ref(null)
  
  // Expanded state for tree nodes
  const expandedNodes = ref(new Set())
  
  // Newly added items (for animation highlighting)
  const newlyAddedIds = ref(new Set())
  
  // Track user story assignments (for animation)
  const userStoryAssignments = ref({})  // { usId: bcId }
  
  // Fetch unassigned user stories
  async function fetchUserStories() {
    try {
      const response = await fetch('/api/user-stories/unassigned')
      if (!response.ok) throw new Error('Failed to fetch user stories')
      userStories.value = await response.json()
    } catch (e) {
      console.error('Error fetching user stories:', e)
    }
  }
  
  // Fetch all bounded contexts
  async function fetchContexts() {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/contexts')
      if (!response.ok) throw new Error('Failed to fetch contexts')
      contexts.value = await response.json()
    } catch (e) {
      error.value = e.message
      console.error('Error fetching contexts:', e)
    } finally {
      loading.value = false
    }
  }
  
  // Fetch tree for a specific context
  async function fetchContextTree(contextId, forceRefresh = false) {
    if (!forceRefresh && contextTrees.value[contextId]) {
      return contextTrees.value[contextId]
    }
    
    try {
      const response = await fetch(`/api/contexts/${contextId}/full-tree`)
      if (!response.ok) throw new Error('Failed to fetch context tree')
      const tree = await response.json()
      contextTrees.value[contextId] = tree
      return tree
    } catch (e) {
      console.error('Error fetching context tree:', e)
      return null
    }
  }
  
  // Add a user story to root level (during ingestion)
  function addUserStory(usData) {
    const exists = userStories.value.some(us => us.id === usData.id)
    if (!exists) {
      userStories.value.push({
        id: usData.id,
        role: usData.role,
        action: usData.action,
        benefit: usData.benefit,
        priority: usData.priority,
        type: 'UserStory',
        name: usData.name || `${usData.role}: ${usData.action?.substring(0, 30)}...`
      })
      
      // Mark as newly added
      markAsNew(usData.id)
    }
  }
  
  // Dynamically add a context (used during ingestion)
  function addContext(contextData) {
    // Check if context already exists
    const exists = contexts.value.some(c => c.id === contextData.id)
    if (!exists) {
      contexts.value.push({
        id: contextData.id,
        name: contextData.name,
        description: contextData.description,
        aggregateCount: 0,
        userStoryCount: 0,
        userStoryIds: contextData.userStoryIds || []
      })
      
      // Mark as newly added for animation
      markAsNew(contextData.id)
      
      // Auto-expand the new context
      expandedNodes.value.add(contextData.id)
      expandedNodes.value = new Set(expandedNodes.value)
    }
  }
  
  // Assign user story to a BC (move from root to BC)
  function assignUserStoryToBC(usId, bcId, bcName) {
    // Track the assignment
    userStoryAssignments.value[usId] = bcId
    
    // Remove from root level user stories
    const usIndex = userStories.value.findIndex(us => us.id === usId)
    if (usIndex !== -1) {
      userStories.value.splice(usIndex, 1)
    }
    
    // Update BC's userStoryCount
    const bc = contexts.value.find(c => c.id === bcId)
    if (bc) {
      bc.userStoryCount = (bc.userStoryCount || 0) + 1
    }
    
    // Mark the user story as newly added (will appear under BC)
    markAsNew(usId)
  }
  
  // Helper to mark item as newly added
  function markAsNew(itemId) {
    newlyAddedIds.value.add(itemId)
    newlyAddedIds.value = new Set(newlyAddedIds.value)
    
    // Clear the flag after animation
    setTimeout(() => {
      newlyAddedIds.value.delete(itemId)
      newlyAddedIds.value = new Set(newlyAddedIds.value)
    }, 2000)
  }
  
  // Dynamically add an item to a context tree (used during ingestion)
  function addItemToTree(contextId, item) {
    markAsNew(item.id)
  }
  
  // Check if an item is newly added (for highlighting)
  function isNewlyAdded(nodeId) {
    return newlyAddedIds.value.has(nodeId)
  }
  
  // Refresh all contexts and trees
  async function refreshAll() {
    loading.value = true
    error.value = null
    
    try {
      // Fetch unassigned user stories
      await fetchUserStories()
      
      // Fetch contexts
      const response = await fetch('/api/contexts')
      if (!response.ok) throw new Error('Failed to fetch contexts')
      contexts.value = await response.json()
      
      // Clear old trees and fetch new ones
      contextTrees.value = {}
      userStoryAssignments.value = {}
      
      for (const ctx of contexts.value) {
        await fetchContextTree(ctx.id, true)
      }
      
      // Auto-expand all for better visibility
      expandAll()
      
    } catch (e) {
      error.value = e.message
      console.error('Error refreshing:', e)
    } finally {
      loading.value = false
    }
  }
  
  // Clear all data (for new ingestion)
  function clearAll() {
    contexts.value = []
    contextTrees.value = {}
    userStories.value = []
    userStoryAssignments.value = {}
    expandedNodes.value = new Set()
    newlyAddedIds.value = new Set()
  }
  
  // Toggle expanded state
  function toggleExpanded(nodeId) {
    if (expandedNodes.value.has(nodeId)) {
      expandedNodes.value.delete(nodeId)
    } else {
      expandedNodes.value.add(nodeId)
    }
    // Force reactivity
    expandedNodes.value = new Set(expandedNodes.value)
  }
  
  function isExpanded(nodeId) {
    return expandedNodes.value.has(nodeId)
  }
  
  function expandAll() {
    // Expand all context nodes
    contexts.value.forEach(ctx => {
      expandedNodes.value.add(ctx.id)
      const tree = contextTrees.value[ctx.id]
      if (tree) {
        tree.aggregates?.forEach(agg => {
          expandedNodes.value.add(agg.id)
        })
      }
    })
    expandedNodes.value = new Set(expandedNodes.value)
  }
  
  function collapseAll() {
    expandedNodes.value.clear()
    expandedNodes.value = new Set()
  }
  
  return {
    contexts,
    contextTrees,
    userStories,
    userStoryAssignments,
    loading,
    error,
    expandedNodes,
    newlyAddedIds,
    fetchContexts,
    fetchContextTree,
    fetchUserStories,
    addContext,
    addUserStory,
    assignUserStoryToBC,
    addItemToTree,
    isNewlyAdded,
    refreshAll,
    clearAll,
    toggleExpanded,
    isExpanded,
    expandAll,
    collapseAll
  }
})

