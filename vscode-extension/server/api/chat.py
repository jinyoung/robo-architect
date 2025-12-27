"""
Chat-based Model Modification API with ReAct Pattern

This API provides streaming chat-based modification of domain model objects.
It uses a ReAct (Reasoning-and-Action) approach where the agent:
1. Thinks about what changes are needed
2. Takes actions to modify objects
3. Observes the results
4. Chains to related objects if needed

The responses are streamed using Server-Sent Events (SSE) for real-time feedback.
"""

from __future__ import annotations

import os
import json
import asyncio
from typing import Any, List, Dict, Optional, AsyncGenerator

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from neo4j import GraphDatabase
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

load_dotenv()

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345msaez")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

driver = None


def get_driver():
    global driver
    if driver is None:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return driver


def get_session():
    return get_driver().session()


# =============================================================================
# Request/Response Models
# =============================================================================


class SelectedNode(BaseModel):
    """A node selected on the canvas."""
    id: str
    name: str
    type: str  # Command, Event, Policy, Aggregate, etc.
    description: Optional[str] = None
    bcId: Optional[str] = None
    # Additional data that might be useful
    actor: Optional[str] = None
    triggerCondition: Optional[str] = None
    invokeCommandId: Optional[str] = None


class ConversationMessage(BaseModel):
    """A message in the conversation history."""
    type: str  # user, assistant, system
    content: str


class ModifyRequest(BaseModel):
    """Request to modify selected nodes based on a prompt."""
    prompt: str
    selectedNodes: List[Dict[str, Any]]
    conversationHistory: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# ReAct Agent Implementation
# =============================================================================


REACT_SYSTEM_PROMPT = """You are an Event Storming domain model modification agent. 
You help users modify their domain models based on natural language requests.

You work with these node types:
- **Command**: An action that can be performed (blue sticky note)
- **Event**: Something that happened in the domain (orange sticky note)  
- **Policy**: A rule that triggers actions based on events (purple sticky note)
- **Aggregate**: A cluster of domain objects (yellow sticky note)
- **BoundedContext**: A logical boundary containing aggregates
- **UI**: A wireframe/screen for a Command or ReadModel (white sticky note)

When modifying nodes, you should:
1. Understand the user's intent
2. Identify which nodes need to change
3. Determine if changes will cascade to related nodes
4. Apply changes systematically

You can perform these actions:
- **rename**: Change the name of a node
- **update**: Update properties like description, or for UI nodes, update the template
- **create**: Create a new node (MUST include bcId from the selected node's context)
- **delete**: Remove a node (mark as deleted)
- **connect**: Create a relationship between nodes

For each modification, explain your reasoning and the expected impact.

IMPORTANT: 
- Respond in Korean when the user uses Korean. Match the user's language.
- When creating new nodes, ALWAYS include the "bcId" field from the selected node's context.
- When creating Commands, include "aggregateId" if you know which Aggregate it belongs to.
- When creating Events, include "commandId" if it's emitted by a Command.
- When creating or updating UI nodes, include "template" with Vue template HTML for the wireframe.
- When modifying UI wireframes, use the "update" action with "template" field containing the new HTML.

For UI wireframe templates:
- Use simple, semantic HTML (form, input, button, label, div)
- Include Korean labels and placeholder text
- Structure: title, form fields, action buttons
- Use CSS classes: form-group, btn-group, wireframe

Current selected nodes context will be provided. Focus modifications on these nodes first,
but you can suggest changes to related nodes if necessary for consistency.
"""


async def stream_react_response(
    prompt: str,
    selected_nodes: List[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]]
) -> AsyncGenerator[str, None]:
    """
    Stream a ReAct-style response for model modification.
    
    Yields SSE events with types:
    - thought: Agent's reasoning
    - action: Action being taken
    - observation: Result of action
    - change: A change that was applied
    - content: Response content
    - complete: Processing finished
    - error: An error occurred
    """
    
    try:
        # Initialize LLM
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            streaming=True,
            api_key=OPENAI_API_KEY
        )
        
        # Build context from selected nodes
        nodes_context = "\n".join([
            f"- {node.get('type', 'Unknown')}: {node.get('name', node.get('id'))} "
            f"(ID: {node.get('id')}, BC: {node.get('bcId', 'N/A')})"
            for node in selected_nodes
        ])
        
        # Build conversation history
        messages = [SystemMessage(content=REACT_SYSTEM_PROMPT)]
        
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            if msg.get('type') == 'user':
                messages.append(HumanMessage(content=msg.get('content', '')))
            elif msg.get('type') == 'assistant':
                messages.append(AIMessage(content=msg.get('content', '')))
        
        # Add current request with context
        current_message = f"""## Selected Nodes
{nodes_context}

## User Request
{prompt}

## Instructions
1. First, analyze what changes are needed (THOUGHT)
2. Then describe the specific actions to take (ACTION)
3. After each action, describe the result (OBSERVATION)
4. If changes cascade to other nodes, continue the ReAct loop
5. Finally, summarize all changes made

Format your response like this:
💭 THOUGHT: [Your reasoning about what needs to be done]
⚡ ACTION: [The specific action you're taking]
👁️ OBSERVATION: [The result of the action]
... (repeat if needed for cascading changes)
✅ SUMMARY: [Final summary of all changes]

For each change, also output a JSON block in this format:
```json
{{"action": "rename|update|create|delete|connect", "targetId": "...", "targetName": "...", "targetType": "...", "description": "...", "bcId": "BC-xxx (from selected node context)"}}
```

For "create" actions, always include:
- "bcId": The BoundedContext ID from the selected node's context
- "aggregateId": (for Command) The parent Aggregate ID
- "commandId": (for Event) The Command that emits this event

For "connect" actions, include:
- "sourceId": The source node ID
- "connectionType": "TRIGGERS" (Event→Policy), "INVOKES" (Policy→Command), or "EMITS" (Command→Event)
"""
        messages.append(HumanMessage(content=current_message))
        
        # Stream response
        applied_changes = []
        current_section = None
        buffer = ""
        
        async for chunk in llm.astream(messages):
            if chunk.content:
                buffer += chunk.content
                
                # Check for section markers
                if "💭 THOUGHT:" in buffer or "THOUGHT:" in buffer:
                    # Extract thought content
                    thought_match = extract_section(buffer, "THOUGHT")
                    if thought_match:
                        yield format_sse_event("thought", {"content": thought_match})
                        buffer = buffer.replace(f"💭 THOUGHT: {thought_match}", "").replace(f"THOUGHT: {thought_match}", "")
                
                if "⚡ ACTION:" in buffer or "ACTION:" in buffer:
                    action_match = extract_section(buffer, "ACTION")
                    if action_match:
                        yield format_sse_event("action", {"content": action_match})
                        buffer = buffer.replace(f"⚡ ACTION: {action_match}", "").replace(f"ACTION: {action_match}", "")
                
                if "👁️ OBSERVATION:" in buffer or "OBSERVATION:" in buffer:
                    obs_match = extract_section(buffer, "OBSERVATION")
                    if obs_match:
                        yield format_sse_event("observation", {"content": obs_match})
                        buffer = buffer.replace(f"👁️ OBSERVATION: {obs_match}", "").replace(f"OBSERVATION: {obs_match}", "")
                
                # Check for JSON change blocks
                if "```json" in buffer and "```" in buffer[buffer.find("```json")+7:]:
                    start = buffer.find("```json") + 7
                    end = buffer.find("```", start)
                    if end > start:
                        json_str = buffer[start:end].strip()
                        try:
                            change = json.loads(json_str)
                            # Apply the change to Neo4j
                            applied = await apply_change(change)
                            if applied:
                                applied_changes.append(change)
                                yield format_sse_event("change", {"change": change})
                        except json.JSONDecodeError:
                            pass
                        buffer = buffer[:buffer.find("```json")] + buffer[end+3:]
                
                # Stream content progressively
                yield format_sse_event("content", {"content": chunk.content})
        
        # Send completion event with summary
        yield format_sse_event("complete", {
            "summary": f"완료: {len(applied_changes)}개의 변경사항이 적용되었습니다.",
            "appliedChanges": applied_changes
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        yield format_sse_event("error", {"message": str(e)})


def extract_section(text: str, section_name: str) -> Optional[str]:
    """Extract content for a specific section from the text."""
    import re
    
    # Look for section followed by newline or next section
    patterns = [
        rf"(?:💭|⚡|👁️)?\s*{section_name}:\s*(.+?)(?=(?:💭|⚡|👁️)?\s*(?:THOUGHT|ACTION|OBSERVATION|SUMMARY)|```|\n\n|$)",
        rf"{section_name}:\s*(.+?)(?=\n|$)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


async def apply_change(change: Dict[str, Any]) -> bool:
    """Apply a single change to Neo4j."""
    action = change.get("action")
    target_id = change.get("targetId")
    
    if not action or not target_id:
        return False
    
    try:
        with get_session() as session:
            if action == "rename":
                query = """
                MATCH (n {id: $target_id})
                SET n.name = $new_name, n.updatedAt = datetime()
                RETURN n.id as id
                """
                session.run(query, target_id=target_id, new_name=change.get("targetName", ""))
                return True
                
            elif action == "update":
                # Check if it's a UI template update
                if change.get("template"):
                    query = """
                    MATCH (n {id: $target_id})
                    SET n.template = $template, n.description = $description, n.updatedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(query, target_id=target_id, 
                               template=change.get("template", ""),
                               description=change.get("description", ""))
                else:
                    query = """
                    MATCH (n {id: $target_id})
                    SET n.description = $description, n.updatedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(query, target_id=target_id, description=change.get("description", ""))
                return True
                
            elif action == "create":
                target_type = change.get("targetType", "Command")
                target_name = change.get("targetName", "NewNode")
                bc_id = change.get("bcId") or change.get("targetBcId")
                aggregate_id = change.get("aggregateId")
                
                if target_type == "Command":
                    # Create command and link to aggregate if provided
                    if aggregate_id:
                        query = """
                        MERGE (n:Command {id: $target_id})
                        SET n.name = $name, n.description = $description, n.createdAt = datetime()
                        WITH n
                        MATCH (agg:Aggregate {id: $agg_id})
                        MERGE (agg)-[:HAS_COMMAND]->(n)
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""), agg_id=aggregate_id)
                    else:
                        query = """
                        MERGE (n:Command {id: $target_id})
                        SET n.name = $name, n.description = $description, n.createdAt = datetime()
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""))
                                   
                elif target_type == "Event":
                    # Create event - usually linked via Command EMITS
                    command_id = change.get("commandId")
                    if command_id:
                        query = """
                        MERGE (n:Event {id: $target_id})
                        SET n.name = $name, n.description = $description, n.version = 1, n.createdAt = datetime()
                        WITH n
                        MATCH (cmd:Command {id: $cmd_id})
                        MERGE (cmd)-[:EMITS]->(n)
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""), cmd_id=command_id)
                    else:
                        query = """
                        MERGE (n:Event {id: $target_id})
                        SET n.name = $name, n.description = $description, n.version = 1, n.createdAt = datetime()
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""))
                                   
                elif target_type == "Policy":
                    # Create policy and link to BC if provided
                    if bc_id:
                        query = """
                        MERGE (n:Policy {id: $target_id})
                        SET n.name = $name, n.description = $description, n.createdAt = datetime()
                        WITH n
                        MATCH (bc:BoundedContext {id: $bc_id})
                        MERGE (bc)-[:HAS_POLICY]->(n)
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""), bc_id=bc_id)
                    else:
                        query = """
                        MERGE (n:Policy {id: $target_id})
                        SET n.name = $name, n.description = $description, n.createdAt = datetime()
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""))
                                   
                elif target_type == "UI":
                    # Create UI wireframe and link to BC and attached Command/ReadModel
                    attached_to_id = change.get("attachedToId")
                    attached_to_type = change.get("attachedToType", "Command")
                    attached_to_name = change.get("attachedToName", "")
                    template = change.get("template", "")
                    
                    if bc_id:
                        query = """
                        MERGE (n:UI {id: $target_id})
                        SET n.name = $name, 
                            n.description = $description, 
                            n.template = $template,
                            n.attachedToId = $attached_to_id,
                            n.attachedToType = $attached_to_type,
                            n.attachedToName = $attached_to_name,
                            n.createdAt = datetime()
                        WITH n
                        MATCH (bc:BoundedContext {id: $bc_id})
                        MERGE (bc)-[:HAS_UI]->(n)
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""),
                                   template=template,
                                   attached_to_id=attached_to_id,
                                   attached_to_type=attached_to_type,
                                   attached_to_name=attached_to_name,
                                   bc_id=bc_id)
                        
                        # Also create ATTACHED_TO relationship if attached_to_id is provided
                        if attached_to_id:
                            attach_query = f"""
                            MATCH (ui:UI {{id: $ui_id}})
                            MATCH (target:{attached_to_type} {{id: $attached_to_id}})
                            MERGE (ui)-[:ATTACHED_TO]->(target)
                            """
                            session.run(attach_query, ui_id=target_id, attached_to_id=attached_to_id)
                    else:
                        query = """
                        MERGE (n:UI {id: $target_id})
                        SET n.name = $name, 
                            n.description = $description, 
                            n.template = $template,
                            n.attachedToId = $attached_to_id,
                            n.attachedToType = $attached_to_type,
                            n.attachedToName = $attached_to_name,
                            n.createdAt = datetime()
                        RETURN n.id as id
                        """
                        session.run(query, target_id=target_id, name=target_name, 
                                   description=change.get("description", ""),
                                   template=template,
                                   attached_to_id=attached_to_id,
                                   attached_to_type=attached_to_type,
                                   attached_to_name=attached_to_name)
                else:
                    return False
                
                # Store bcId in change for frontend sync
                change["bcId"] = bc_id
                return True
                
            elif action == "delete":
                query = """
                MATCH (n {id: $target_id})
                SET n.deleted = true, n.deletedAt = datetime()
                RETURN n.id as id
                """
                session.run(query, target_id=target_id)
                return True
                
            elif action == "connect":
                source_id = change.get("sourceId")
                connection_type = change.get("connectionType", "TRIGGERS")
                
                if not source_id:
                    return False
                
                if connection_type == "TRIGGERS":
                    query = """
                    MATCH (evt:Event {id: $source_id})
                    MATCH (pol:Policy {id: $target_id})
                    MERGE (evt)-[:TRIGGERS]->(pol)
                    RETURN evt.id as id
                    """
                elif connection_type == "INVOKES":
                    query = """
                    MATCH (pol:Policy {id: $source_id})
                    MATCH (cmd:Command {id: $target_id})
                    MERGE (pol)-[:INVOKES]->(cmd)
                    RETURN pol.id as id
                    """
                elif connection_type == "EMITS":
                    query = """
                    MATCH (cmd:Command {id: $source_id})
                    MATCH (evt:Event {id: $target_id})
                    MERGE (cmd)-[:EMITS]->(evt)
                    RETURN cmd.id as id
                    """
                else:
                    return False
                    
                session.run(query, source_id=source_id, target_id=target_id)
                return True
                
    except Exception as e:
        print(f"Failed to apply change: {e}")
        return False
    
    return False


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format data as an SSE event."""
    event_data = {"type": event_type, **data}
    return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/modify")
async def modify_nodes(request: ModifyRequest):
    """
    Modify selected nodes based on a natural language prompt.
    
    Returns a streaming response with ReAct-style events:
    - thought: Agent's reasoning process
    - action: Actions being taken
    - observation: Results of actions
    - change: Applied changes
    - content: Response content
    - complete: Processing finished
    - error: Error occurred
    """
    if not request.selectedNodes:
        raise HTTPException(status_code=400, detail="No nodes selected")
    
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    async def generate():
        async for event in stream_react_response(
            request.prompt,
            request.selectedNodes,
            request.conversationHistory
        ):
            yield event
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/node/{node_id}")
async def get_node_details(node_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific node including its parent BC."""
    query = """
    MATCH (n {id: $node_id})
    
    // Find parent BC based on node type
    OPTIONAL MATCH (bc1:BoundedContext)-[:HAS_AGGREGATE]->(n)
    OPTIONAL MATCH (bc2:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(n)
    OPTIONAL MATCH (bc3:BoundedContext)-[:HAS_AGGREGATE]->(agg2:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(n)
    OPTIONAL MATCH (bc4:BoundedContext)-[:HAS_POLICY]->(n)
    
    WITH n, coalesce(bc1, bc2, bc3, bc4) as bc
    
    // Get relationships
    OPTIONAL MATCH (n)-[r]-(related)
    
    RETURN n {.*, labels: labels(n)} as node,
           bc {.id, .name, .description} as boundedContext,
           collect({
               id: related.id,
               name: related.name,
               type: labels(related)[0],
               relationship: type(r),
               direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END
           }) as relationships
    """
    
    with get_session() as session:
        result = session.run(query, node_id=node_id)
        record = result.single()
        
        if not record:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        
        node = dict(record["node"])
        relationships = [r for r in record["relationships"] if r.get("id")]
        bc = dict(record["boundedContext"]) if record["boundedContext"] else None
        
        # Add bcId to node data
        if bc:
            node["bcId"] = bc["id"]
            node["bcName"] = bc["name"]
        
        return {
            "node": node,
            "boundedContext": bc,
            "relationships": relationships
        }


@router.get("/impact/{node_id}")
async def get_impact_preview(node_id: str) -> Dict[str, Any]:
    """
    Preview what would be impacted if a node is modified.
    
    Returns nodes that might need to be updated based on relationships.
    """
    query = """
    MATCH (n {id: $node_id})
    
    // Direct relationships
    OPTIONAL MATCH (n)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (n)<-[:EMITS]-(cmd:Command)
    OPTIONAL MATCH (n)-[:TRIGGERS]->(pol:Policy)
    OPTIONAL MATCH (n)<-[:TRIGGERS]-(trigEvt:Event)
    OPTIONAL MATCH (n)-[:INVOKES]->(invCmd:Command)
    OPTIONAL MATCH (n)<-[:INVOKES]-(invPol:Policy)
    
    // Get parent aggregate/BC
    OPTIONAL MATCH (agg:Aggregate)-[:HAS_COMMAND]->(n)
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg)
    
    RETURN n {.*, type: labels(n)[0]} as node,
           collect(DISTINCT evt {.id, .name, type: 'Event', impact: 'direct'}) as emittedEvents,
           collect(DISTINCT cmd {.id, .name, type: 'Command', impact: 'direct'}) as emittingCommands,
           collect(DISTINCT pol {.id, .name, type: 'Policy', impact: 'triggered'}) as triggeredPolicies,
           collect(DISTINCT trigEvt {.id, .name, type: 'Event', impact: 'triggering'}) as triggeringEvents,
           collect(DISTINCT invCmd {.id, .name, type: 'Command', impact: 'invoked'}) as invokedCommands,
           collect(DISTINCT invPol {.id, .name, type: 'Policy', impact: 'invoking'}) as invokingPolicies,
           agg {.id, .name, type: 'Aggregate'} as parentAggregate,
           bc {.id, .name, type: 'BoundedContext'} as parentBC
    """
    
    with get_session() as session:
        result = session.run(query, node_id=node_id)
        record = result.single()
        
        if not record:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        
        # Collect all impacted nodes
        impacted = []
        
        for key in ['emittedEvents', 'emittingCommands', 'triggeredPolicies', 
                    'triggeringEvents', 'invokedCommands', 'invokingPolicies']:
            for item in record[key]:
                if item.get('id'):
                    impacted.append(dict(item))
        
        return {
            "node": dict(record["node"]),
            "impactedNodes": impacted,
            "parentAggregate": dict(record["parentAggregate"]) if record["parentAggregate"] else None,
            "parentBC": dict(record["parentBC"]) if record["parentBC"] else None
        }

