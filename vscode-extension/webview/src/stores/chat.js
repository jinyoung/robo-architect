import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useCanvasStore } from './canvas'
import { getApiBaseUrl } from '../utils/vscode'

/**
 * Store for managing chat-based model modification with ReAct pattern.
 * 
 * This implements a "vibe coding" approach where users can:
 * 1. Select objects on the canvas
 * 2. Describe modifications in natural language
 * 3. Watch the agent reason and act (ReAct) to make changes
 * 4. Changes can chain to other objects as needed
 */
export const useChatStore = defineStore('chat', () => {
  const canvasStore = useCanvasStore()
  
  // Message history
  const messages = ref([])
  
  // Current session state
  const isProcessing = ref(false)
  const currentThought = ref('') // Current reasoning step
  const currentAction = ref('') // Current action being taken
  const streamingContent = ref('') // For streaming responses
  
  // ReAct trace for transparency
  const reactTrace = ref([]) // Array of { type: 'thought' | 'action' | 'observation', content: string }
  
  // Error state
  const error = ref(null)
  
  // Applied changes history
  const appliedChanges = ref([])
  
  // Computed
  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() => messages.value[messages.value.length - 1])
  
  /**
   * Message types:
   * - user: User's modification request
   * - assistant: Agent's response
   * - system: System notifications (e.g., changes applied)
   * - thought: Agent's reasoning (ReAct)
   * - action: Agent's action (ReAct)
   * - observation: Result of action (ReAct)
   */
  
  /**
   * Add a user message and trigger the modification workflow
   */
  async function sendMessage(content) {
    if (!content.trim()) return
    
    // Get selected nodes context
    const selectedNodes = canvasStore.selectedNodes
    if (selectedNodes.length === 0) {
      messages.value.push({
        id: generateId(),
        type: 'system',
        content: '먼저 캔버스에서 수정할 객체를 선택해주세요.',
        timestamp: new Date().toISOString()
      })
      return
    }
    
    // Add user message
    const userMessage = {
      id: generateId(),
      type: 'user',
      content,
      selectedNodes: selectedNodes.map(n => ({
        id: n.id,
        name: n.data?.name || n.data?.label,
        type: n.data?.type || n.type
      })),
      timestamp: new Date().toISOString()
    }
    messages.value.push(userMessage)
    
    // Start processing
    isProcessing.value = true
    error.value = null
    reactTrace.value = []
    streamingContent.value = ''
    
    try {
      // Call the ReAct modification API with streaming
      await processModificationRequest(content, selectedNodes)
    } catch (e) {
      error.value = e.message
      messages.value.push({
        id: generateId(),
        type: 'system',
        content: `오류가 발생했습니다: ${e.message}`,
        timestamp: new Date().toISOString(),
        isError: true
      })
    } finally {
      isProcessing.value = false
      currentThought.value = ''
      currentAction.value = ''
    }
  }
  
  /**
   * Process modification request using ReAct pattern
   */
  async function processModificationRequest(prompt, selectedNodes) {
    const nodeContext = selectedNodes.map(n => {
      // Get bcId from parentNode (VueFlow grouping) or data.bcId
      const bcId = n.parentNode || n.data?.bcId
      
      return {
        id: n.id,
        name: n.data?.name || n.data?.label,
        type: n.data?.type || n.type,
        description: n.data?.description,
        bcId: bcId,
        bcName: n.data?.bcName,
        // Include aggregate info if available
        aggregateId: n.data?.aggregateId,
        // Include all other data
        ...n.data
      }
    })
    
    // Start streaming request
    const apiBase = getApiBaseUrl()
    const response = await fetch(`${apiBase}/api/chat/modify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        selectedNodes: nodeContext,
        conversationHistory: messages.value.slice(-10) // Last 10 messages for context
      })
    })
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }
    
    // Handle streaming response
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let assistantMessage = {
      id: generateId(),
      type: 'assistant',
      content: '',
      changes: [],
      reactSteps: [],
      timestamp: new Date().toISOString()
    }
    messages.value.push(assistantMessage)
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      
      // Parse SSE events
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue
          
          try {
            const event = JSON.parse(data)
            handleStreamEvent(event, assistantMessage)
          } catch (e) {
            console.warn('Failed to parse SSE event:', data)
          }
        }
      }
    }
    
    // Final update
    updateLastAssistantMessage(assistantMessage)
  }
  
  /**
   * Handle a streaming event from the ReAct API
   */
  function handleStreamEvent(event, assistantMessage) {
    switch (event.type) {
      case 'thought':
        currentThought.value = event.content
        reactTrace.value.push({ type: 'thought', content: event.content })
        assistantMessage.reactSteps.push({ type: 'thought', content: event.content })
        break
        
      case 'action':
        currentAction.value = event.content
        reactTrace.value.push({ type: 'action', content: event.content, action: event.action })
        assistantMessage.reactSteps.push({ type: 'action', content: event.content, action: event.action })
        break
        
      case 'observation':
        reactTrace.value.push({ type: 'observation', content: event.content })
        assistantMessage.reactSteps.push({ type: 'observation', content: event.content })
        break
        
      case 'change':
        // A change was applied
        assistantMessage.changes.push(event.change)
        appliedChanges.value.push(event.change)
        break
        
      case 'content':
        // Final response content
        assistantMessage.content += event.content
        streamingContent.value = assistantMessage.content
        break
        
      case 'complete':
        // Processing complete
        assistantMessage.content = event.summary || assistantMessage.content
        assistantMessage.isComplete = true
        
        // Sync canvas with applied changes
        if (assistantMessage.changes && assistantMessage.changes.length > 0) {
          canvasStore.syncAfterChanges(assistantMessage.changes)
        }
        break
        
      case 'error':
        error.value = event.message
        assistantMessage.content = `오류: ${event.message}`
        assistantMessage.isError = true
        break
    }
    
    updateLastAssistantMessage(assistantMessage)
  }
  
  /**
   * Update the last assistant message in the messages array
   */
  function updateLastAssistantMessage(message) {
    const idx = messages.value.findIndex(m => m.id === message.id)
    if (idx !== -1) {
      messages.value[idx] = { ...message }
      // Trigger reactivity
      messages.value = [...messages.value]
    }
  }
  
  /**
   * Clear conversation history
   */
  function clearMessages() {
    messages.value = []
    reactTrace.value = []
    appliedChanges.value = []
    error.value = null
  }
  
  /**
   * Generate a unique ID
   */
  function generateId() {
    return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }
  
  /**
   * Retry the last failed request
   */
  async function retryLast() {
    const lastUserMessage = [...messages.value].reverse().find(m => m.type === 'user')
    if (lastUserMessage) {
      // Remove the error message
      const errorIdx = messages.value.findIndex(m => m.isError)
      if (errorIdx !== -1) {
        messages.value.splice(errorIdx, 1)
      }
      // Reselect the nodes from the original message
      if (lastUserMessage.selectedNodes) {
        canvasStore.selectNodes(lastUserMessage.selectedNodes.map(n => n.id))
      }
      await processModificationRequest(lastUserMessage.content, canvasStore.selectedNodes)
    }
  }
  
  /**
   * Cancel ongoing processing
   */
  function cancelProcessing() {
    // TODO: Implement actual request cancellation
    isProcessing.value = false
    currentThought.value = ''
    currentAction.value = ''
  }
  
  return {
    // State
    messages,
    isProcessing,
    currentThought,
    currentAction,
    streamingContent,
    reactTrace,
    error,
    appliedChanges,
    
    // Computed
    hasMessages,
    lastMessage,
    
    // Actions
    sendMessage,
    clearMessages,
    retryLast,
    cancelProcessing
  }
})

