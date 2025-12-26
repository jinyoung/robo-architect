"""
LangGraph-based User Story Planning Workflow

This module implements a workflow for adding new user stories that:
1. Analyzes the user story intent
2. Finds the best matching BC or proposes creating a new one
3. Generates related domain objects (Aggregate, Command, Event)
4. Supports human-in-the-loop for plan approval

Workflow Steps:
1. analyze_story: Understand the user story intent and extract domain concepts
2. find_matching_bc: Search for best matching BC or propose new one
3. generate_objects: Create plan for Aggregate, Command, Event
4. return_plan: Return the plan for human approval
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Optional, List, Dict
from enum import Enum

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

load_dotenv()


# =============================================================================
# State Definitions
# =============================================================================


class PlanningScope(str, Enum):
    """Scope of the user story placement."""
    EXISTING_BC = "existing_bc"  # Can be placed in an existing BC
    NEW_BC = "new_bc"  # Requires a new BC
    CROSS_BC = "cross_bc"  # Requires connections across BCs


class ProposedObject(BaseModel):
    """A proposed domain object to create."""
    action: str = "create"  # create, update, connect
    targetType: str  # BoundedContext, Aggregate, Command, Event, Policy
    targetId: str
    targetName: str
    targetBcId: Optional[str] = None
    targetBcName: Optional[str] = None
    description: str = ""
    reason: str = ""
    connectionType: Optional[str] = None
    sourceId: Optional[str] = None
    actor: Optional[str] = None
    aggregateId: Optional[str] = None
    commandId: Optional[str] = None


class UserStoryPlanningState(BaseModel):
    """State for the user story planning workflow."""
    
    # Input
    role: str = ""
    action: str = ""
    benefit: str = ""
    target_bc_id: Optional[str] = None
    auto_generate: bool = True
    
    # Analysis results
    story_intent: str = ""
    domain_keywords: List[str] = Field(default_factory=list)
    action_verbs: List[str] = Field(default_factory=list)
    
    # BC matching
    scope: PlanningScope = PlanningScope.EXISTING_BC
    scope_reasoning: str = ""
    matched_bc_id: Optional[str] = None
    matched_bc_name: Optional[str] = None
    
    # Related objects found
    related_objects: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Generated plan
    proposed_objects: List[ProposedObject] = Field(default_factory=list)
    plan_summary: str = ""
    
    # Error
    error: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


# =============================================================================
# Utility Functions
# =============================================================================


def get_llm():
    """Get the configured LLM instance."""
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL", "gpt-4o")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0)


def get_neo4j_driver():
    """Get Neo4j driver."""
    from neo4j import GraphDatabase
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "12345msaez")
    return GraphDatabase.driver(uri, auth=(user, password))


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{str(uuid.uuid4())[:8].upper()}"


# =============================================================================
# Node Functions
# =============================================================================


def analyze_story_node(state: UserStoryPlanningState) -> Dict[str, Any]:
    """
    Analyze the user story to extract intent and domain concepts.
    """
    llm = get_llm()
    
    prompt = f"""Analyze this user story and extract domain modeling information.

User Story:
- As a: {state.role}
- I want to: {state.action}
- So that: {state.benefit}

Extract:
1. Primary intent (what is the main action/goal?)
2. Domain keywords (nouns that could be Aggregates or Entities)
3. Action verbs (could become Commands)
4. State changes (could become Events)

Respond in JSON format:
{{
    "intent": "brief description of the primary intent",
    "domain_keywords": ["keyword1", "keyword2", ...],
    "action_verbs": ["verb1", "verb2", ...],
    "state_changes": ["PastTenseEvent1", "PastTenseEvent2", ...]
}}"""

    response = llm.invoke([
        SystemMessage(content="You are a DDD expert analyzing user stories for domain modeling."),
        HumanMessage(content=prompt)
    ])
    
    import json
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        result = json.loads(content.strip())
        
        return {
            "story_intent": result.get("intent", ""),
            "domain_keywords": result.get("domain_keywords", []),
            "action_verbs": result.get("action_verbs", [])
        }
    except Exception as e:
        return {
            "story_intent": state.action,
            "domain_keywords": [state.action.split()[0]] if state.action else [],
            "action_verbs": [],
            "error": str(e)
        }


def find_matching_bc_node(state: UserStoryPlanningState) -> Dict[str, Any]:
    """
    Find the best matching BC for this user story or propose creating a new one.
    Uses keyword search across existing BCs and Aggregates.
    """
    # If target BC is specified, use it
    if state.target_bc_id:
        driver = get_neo4j_driver()
        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (bc:BoundedContext {id: $bc_id})
                    RETURN bc.id as id, bc.name as name
                """, bc_id=state.target_bc_id)
                record = result.single()
                if record:
                    return {
                        "scope": PlanningScope.EXISTING_BC,
                        "scope_reasoning": f"Using specified BC: {record['name']}",
                        "matched_bc_id": record["id"],
                        "matched_bc_name": record["name"]
                    }
        finally:
            driver.close()
    
    # Search for matching BC based on keywords
    driver = get_neo4j_driver()
    keywords = state.domain_keywords + state.action_verbs
    
    try:
        with driver.session() as session:
            # Search BCs and Aggregates by keyword matching
            search_query = """
            UNWIND $keywords as keyword
            MATCH (bc:BoundedContext)
            OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
            WITH bc, agg, keyword,
                 CASE 
                     WHEN toLower(bc.name) CONTAINS toLower(keyword) THEN 3
                     WHEN toLower(coalesce(bc.description, '')) CONTAINS toLower(keyword) THEN 2
                     WHEN agg IS NOT NULL AND toLower(agg.name) CONTAINS toLower(keyword) THEN 1
                     ELSE 0
                 END as score
            WHERE score > 0
            WITH bc, sum(score) as totalScore
            ORDER BY totalScore DESC
            LIMIT 1
            RETURN bc.id as id, bc.name as name, totalScore as score
            """
            
            result = session.run(search_query, keywords=keywords)
            record = result.single()
            
            if record and record["score"] >= 2:
                # Found a good match
                # Also find related objects in this BC
                related_query = """
                MATCH (bc:BoundedContext {id: $bc_id})
                OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
                OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
                OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
                RETURN 
                    collect(DISTINCT {id: agg.id, name: agg.name, type: 'Aggregate'}) as aggregates,
                    collect(DISTINCT {id: cmd.id, name: cmd.name, type: 'Command'}) as commands,
                    collect(DISTINCT {id: evt.id, name: evt.name, type: 'Event'}) as events
                """
                related_result = session.run(related_query, bc_id=record["id"])
                related_record = related_result.single()
                
                related_objects = []
                if related_record:
                    for agg in related_record["aggregates"]:
                        if agg["id"]:
                            related_objects.append(agg)
                    for cmd in related_record["commands"]:
                        if cmd["id"]:
                            related_objects.append(cmd)
                    for evt in related_record["events"]:
                        if evt["id"]:
                            related_objects.append(evt)
                
                return {
                    "scope": PlanningScope.EXISTING_BC,
                    "scope_reasoning": f"Found matching BC '{record['name']}' based on keywords: {keywords}",
                    "matched_bc_id": record["id"],
                    "matched_bc_name": record["name"],
                    "related_objects": related_objects
                }
            else:
                # No good match, need to create new BC
                return {
                    "scope": PlanningScope.NEW_BC,
                    "scope_reasoning": f"No matching BC found for keywords: {keywords}. Proposing new BC.",
                    "matched_bc_id": None,
                    "matched_bc_name": None,
                    "related_objects": []
                }
    finally:
        driver.close()


def generate_objects_node(state: UserStoryPlanningState) -> Dict[str, Any]:
    """
    Generate the plan for domain objects based on the user story.
    """
    if not state.auto_generate:
        # Just return empty plan if auto-generate is disabled
        return {
            "proposed_objects": [],
            "plan_summary": "Auto-generation disabled. User story will be created without related objects."
        }
    
    llm = get_llm()
    
    # Build context
    related_text = "\n".join([
        f"- {obj.get('type', 'Unknown')}: {obj.get('name', '?')}"
        for obj in state.related_objects
    ]) if state.related_objects else "None"
    
    bc_context = ""
    if state.scope == PlanningScope.EXISTING_BC:
        bc_context = f"Target BC: {state.matched_bc_name} (ID: {state.matched_bc_id})"
    else:
        bc_context = "Need to create a new Bounded Context"
    
    prompt = f"""Generate domain objects for this new User Story.

## User Story
- As a: {state.role}
- I want to: {state.action}
- So that: {state.benefit}

## Analysis
- Intent: {state.story_intent}
- Domain Keywords: {state.domain_keywords}
- Action Verbs: {state.action_verbs}

## Context
{bc_context}

## Existing Related Objects in this BC
{related_text}

## Your Task
Generate the necessary domain objects following DDD patterns:

1. If creating a new BC, propose the BC first
2. Create or reuse Aggregate (the main entity affected)
3. Create Command (the action to be performed)
4. Create Event (the result of the command, past tense)

For IDs, use these prefixes:
- BC: BC-NAME
- Aggregate: AGG-NAME
- Command: CMD-NAME-ACTION
- Event: EVT-NAME-ACTION (past tense)

If an Aggregate already exists (from related objects), use its ID and just add new Commands/Events.

Respond in JSON format:
{{
    "summary": "Brief summary of what will be created",
    "objects": [
        {{
            "action": "create",
            "targetType": "BoundedContext|Aggregate|Command|Event",
            "targetId": "unique-id",
            "targetName": "Display Name",
            "targetBcId": "BC-ID (for objects in a BC)",
            "targetBcName": "BC Name",
            "description": "What this object represents",
            "reason": "Why this is needed",
            "actor": "for Commands: who performs this",
            "aggregateId": "for Commands: parent aggregate ID",
            "commandId": "for Events: parent command ID"
        }}
    ]
}}"""

    response = llm.invoke([
        SystemMessage(content="""You are a DDD expert generating domain objects.
Follow these rules:
- Aggregate names should be nouns (e.g., Order, Product, Customer)
- Command names should be verbs (e.g., PlaceOrder, CreateProduct)
- Event names should be past tense (e.g., OrderPlaced, ProductCreated)
- Reuse existing objects when appropriate"""),
        HumanMessage(content=prompt)
    ])
    
    import json
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        result = json.loads(content.strip())
        
        proposed_objects = []
        for obj in result.get("objects", []):
            proposed_objects.append(ProposedObject(
                action=obj.get("action", "create"),
                targetType=obj.get("targetType", "Unknown"),
                targetId=obj.get("targetId", generate_id("OBJ")),
                targetName=obj.get("targetName", ""),
                targetBcId=obj.get("targetBcId") or state.matched_bc_id,
                targetBcName=obj.get("targetBcName") or state.matched_bc_name,
                description=obj.get("description", ""),
                reason=obj.get("reason", ""),
                connectionType=obj.get("connectionType"),
                sourceId=obj.get("sourceId"),
                actor=obj.get("actor"),
                aggregateId=obj.get("aggregateId"),
                commandId=obj.get("commandId")
            ))
        
        return {
            "proposed_objects": proposed_objects,
            "plan_summary": result.get("summary", "")
        }
        
    except Exception as e:
        return {
            "proposed_objects": [],
            "plan_summary": f"Error generating objects: {str(e)}",
            "error": str(e)
        }


# =============================================================================
# Graph Builder
# =============================================================================


def create_user_story_planning_graph():
    """Create the user story planning workflow graph."""
    
    graph = StateGraph(UserStoryPlanningState)
    
    # Add nodes
    graph.add_node("analyze_story", analyze_story_node)
    graph.add_node("find_matching_bc", find_matching_bc_node)
    graph.add_node("generate_objects", generate_objects_node)
    
    # Set entry point
    graph.set_entry_point("analyze_story")
    
    # Add edges
    graph.add_edge("analyze_story", "find_matching_bc")
    graph.add_edge("find_matching_bc", "generate_objects")
    graph.add_edge("generate_objects", END)
    
    return graph.compile()


# =============================================================================
# Main Entry Point
# =============================================================================


def run_user_story_planning(
    role: str,
    action: str,
    benefit: str,
    target_bc_id: Optional[str] = None,
    auto_generate: bool = True
) -> Dict[str, Any]:
    """
    Run the user story planning workflow and return the plan.
    
    This is the main entry point called by the API.
    """
    graph = create_user_story_planning_graph()
    
    initial_state = UserStoryPlanningState(
        role=role,
        action=action,
        benefit=benefit,
        target_bc_id=target_bc_id,
        auto_generate=auto_generate
    )
    
    # Run the workflow
    result = graph.invoke(initial_state)
    
    # Convert to API response format
    return {
        "scope": result.scope.value if hasattr(result, 'scope') else result.get("scope", PlanningScope.EXISTING_BC).value,
        "scopeReasoning": result.scope_reasoning if hasattr(result, 'scope_reasoning') else result.get("scope_reasoning", ""),
        "keywords": result.domain_keywords if hasattr(result, 'domain_keywords') else result.get("domain_keywords", []),
        "relatedObjects": result.related_objects if hasattr(result, 'related_objects') else result.get("related_objects", []),
        "changes": [
            obj.dict() if hasattr(obj, 'dict') else obj
            for obj in (result.proposed_objects if hasattr(result, 'proposed_objects') else result.get("proposed_objects", []))
        ],
        "summary": result.plan_summary if hasattr(result, 'plan_summary') else result.get("plan_summary", "")
    }

