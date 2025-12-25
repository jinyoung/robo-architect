"""
Change Management API for User Story Editing with Impact Analysis

Provides endpoints for:
- Impact analysis when a User Story is modified
- LLM-based change plan generation
- Human-in-the-loop plan revision
- Applying approved changes to Neo4j
"""

from __future__ import annotations

import os
from typing import Any, Optional, List

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

load_dotenv()

router = APIRouter(prefix="/api/change", tags=["change"])

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345msaez")

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


class UserStoryEdit(BaseModel):
    """Edited user story data."""
    role: str
    action: str
    benefit: Optional[str] = None
    changes: List[dict] = Field(default_factory=list)


class ChangePlanRequest(BaseModel):
    """Request for generating or revising a change plan."""
    userStoryId: str
    originalUserStory: Optional[dict] = None
    editedUserStory: dict
    impactedNodes: List[dict]
    feedback: Optional[str] = None
    previousPlan: Optional[List[dict]] = None


class ChangeItem(BaseModel):
    """A single change in the plan."""
    action: str  # rename, update, create, delete
    targetType: str  # Aggregate, Command, Event, Policy
    targetId: str
    targetName: str
    from_value: Optional[str] = Field(None, alias="from")
    to_value: Optional[str] = Field(None, alias="to")
    description: str
    reason: str


class ChangePlanResponse(BaseModel):
    """Response containing the generated change plan."""
    changes: List[dict]
    summary: str


class ApplyChangesRequest(BaseModel):
    """Request to apply approved changes."""
    userStoryId: str
    editedUserStory: dict
    changePlan: List[dict]


class ApplyChangesResponse(BaseModel):
    """Response after applying changes."""
    success: bool
    appliedChanges: List[dict]
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/impact/{user_story_id}")
async def get_impact_analysis(user_story_id: str) -> dict[str, Any]:
    """
    Analyze the impact of changing a User Story.
    
    Returns:
    - The original user story
    - All connected objects (Aggregate, Command, Event) that may need updates
    
    This follows multiple relationship paths:
    1. Direct IMPLEMENTS from UserStory to any node
    2. Through BoundedContext hierarchy
    3. All related Commands and Events in the same aggregate
    """
    # Query to get the user story and all connected objects
    query = """
    MATCH (us:UserStory {id: $user_story_id})
    
    // Path 1: Direct IMPLEMENTS relationships
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(directTarget)
    WHERE directTarget:Aggregate OR directTarget:Command OR directTarget:Event OR directTarget:BoundedContext
    
    // Path 2: Through BoundedContext - find the BC this user story belongs to
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(bcAgg:Aggregate)
    OPTIONAL MATCH (bcAgg)-[:HAS_COMMAND]->(bcCmd:Command)
    OPTIONAL MATCH (bcCmd)-[:EMITS]->(bcEvt:Event)
    
    // Path 3: If user story implements an aggregate, get its commands and events
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(usAgg:Aggregate)
    OPTIONAL MATCH (usAgg)-[:HAS_COMMAND]->(usAggCmd:Command)
    OPTIONAL MATCH (usAggCmd)-[:EMITS]->(usAggEvt:Event)
    
    // Path 4: If user story implements a command, get its events
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(usCmd:Command)
    OPTIONAL MATCH (usCmd)-[:EMITS]->(usCmdEvt:Event)
    OPTIONAL MATCH (usAggParent:Aggregate)-[:HAS_COMMAND]->(usCmd)
    
    WITH us,
         collect(DISTINCT bc) as bcs,
         collect(DISTINCT bcAgg) + collect(DISTINCT usAgg) + collect(DISTINCT usAggParent) as allAggs,
         collect(DISTINCT bcCmd) + collect(DISTINCT usAggCmd) + collect(DISTINCT usCmd) as allCmds,
         collect(DISTINCT bcEvt) + collect(DISTINCT usAggEvt) + collect(DISTINCT usCmdEvt) as allEvts
    
    // Get the first BC (user story typically belongs to one BC)
    WITH us, 
         CASE WHEN size(bcs) > 0 THEN bcs[0] ELSE null END as bc,
         allAggs, allCmds, allEvts
    
    RETURN {
        id: us.id,
        role: us.role,
        action: us.action,
        benefit: us.benefit,
        priority: us.priority,
        status: us.status
    } as userStory,
    bc {.id, .name, .description} as boundedContext,
    [a IN allAggs WHERE a IS NOT NULL | a {.id, .name, .rootEntity, type: 'Aggregate'}] as aggregates,
    [c IN allCmds WHERE c IS NOT NULL | c {.id, .name, .actor, type: 'Command'}] as commands,
    [e IN allEvts WHERE e IS NOT NULL | e {.id, .name, .version, type: 'Event'}] as events
    """
    
    with get_session() as session:
        result = session.run(query, user_story_id=user_story_id)
        record = result.single()
        
        if not record:
            raise HTTPException(status_code=404, detail=f"User story {user_story_id} not found")
        
        user_story = dict(record["userStory"])
        bounded_context = dict(record["boundedContext"]) if record["boundedContext"] else None
        
        # Collect all impacted nodes
        impacted_nodes = []
        
        # Add aggregates (deduplicated)
        seen_ids = set()
        for agg in record["aggregates"]:
            if agg and agg["id"] not in seen_ids:
                impacted_nodes.append(dict(agg))
                seen_ids.add(agg["id"])
        
        # Add commands (deduplicated)
        for cmd in record["commands"]:
            if cmd and cmd["id"] not in seen_ids:
                impacted_nodes.append(dict(cmd))
                seen_ids.add(cmd["id"])
        
        # Add events (deduplicated)
        for evt in record["events"]:
            if evt and evt["id"] not in seen_ids:
                impacted_nodes.append(dict(evt))
                seen_ids.add(evt["id"])
        
        return {
            "userStory": user_story,
            "boundedContext": bounded_context,
            "impactedNodes": impacted_nodes
        }


@router.post("/plan")
async def generate_change_plan(request: ChangePlanRequest) -> ChangePlanResponse:
    """
    Generate a change plan using LLM based on the user story changes.
    
    This endpoint uses the LLM to analyze:
    - What changed in the user story
    - Which connected objects need to be updated
    - What specific changes should be made to each object
    
    If feedback is provided, it will revise the previous plan.
    """
    from agent.change_planner import generate_change_plan as llm_generate_plan
    
    try:
        changes = llm_generate_plan(
            user_story_id=request.userStoryId,
            original_user_story=request.originalUserStory,
            edited_user_story=request.editedUserStory,
            impacted_nodes=request.impactedNodes,
            feedback=request.feedback,
            previous_plan=request.previousPlan
        )
        
        return ChangePlanResponse(
            changes=changes,
            summary=f"Generated {len(changes)} changes based on user story modification"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate change plan: {str(e)}")


@router.post("/apply")
async def apply_changes(request: ApplyChangesRequest) -> ApplyChangesResponse:
    """
    Apply the approved change plan to Neo4j.
    
    Steps:
    1. Update the user story with new values
    2. Apply each change in the plan (rename, update, etc.)
    3. Return results of applied changes
    """
    applied_changes = []
    errors = []
    
    with get_session() as session:
        # Step 1: Update the user story
        try:
            us_query = """
            MATCH (us:UserStory {id: $user_story_id})
            SET us.role = $role,
                us.action = $action,
                us.benefit = $benefit,
                us.updatedAt = datetime()
            RETURN us.id as id
            """
            session.run(
                us_query,
                user_story_id=request.userStoryId,
                role=request.editedUserStory.get("role"),
                action=request.editedUserStory.get("action"),
                benefit=request.editedUserStory.get("benefit")
            )
            applied_changes.append({
                "action": "update",
                "targetType": "UserStory",
                "targetId": request.userStoryId,
                "success": True
            })
        except Exception as e:
            errors.append(f"Failed to update user story: {str(e)}")
        
        # Step 2: Apply each change in the plan
        for change in request.changePlan:
            try:
                if change.get("action") == "rename":
                    # Rename a node
                    rename_query = """
                    MATCH (n {id: $node_id})
                    SET n.name = $new_name, n.updatedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(
                        rename_query,
                        node_id=change.get("targetId"),
                        new_name=change.get("to")
                    )
                    applied_changes.append({
                        **change,
                        "success": True
                    })
                    
                elif change.get("action") == "update":
                    # Update node properties
                    # Build dynamic property update
                    update_query = """
                    MATCH (n {id: $node_id})
                    SET n.description = $description, n.updatedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(
                        update_query,
                        node_id=change.get("targetId"),
                        description=change.get("description", "")
                    )
                    applied_changes.append({
                        **change,
                        "success": True
                    })
                    
                elif change.get("action") == "create":
                    # Create a new node (placeholder - implementation depends on node type)
                    applied_changes.append({
                        **change,
                        "success": True,
                        "note": "Creation not fully implemented"
                    })
                    
                elif change.get("action") == "delete":
                    # Delete a node (soft delete or actual delete)
                    delete_query = """
                    MATCH (n {id: $node_id})
                    SET n.deleted = true, n.deletedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(
                        delete_query,
                        node_id=change.get("targetId")
                    )
                    applied_changes.append({
                        **change,
                        "success": True
                    })
                    
            except Exception as e:
                errors.append(f"Failed to apply {change.get('action')} on {change.get('targetId')}: {str(e)}")
                applied_changes.append({
                    **change,
                    "success": False,
                    "error": str(e)
                })
    
    return ApplyChangesResponse(
        success=len(errors) == 0,
        appliedChanges=applied_changes,
        errors=errors
    )


@router.get("/history/{user_story_id}")
async def get_change_history(user_story_id: str) -> list[dict[str, Any]]:
    """
    Get the change history for a user story.
    """
    query = """
    MATCH (us:UserStory {id: $user_story_id})
    OPTIONAL MATCH (us)-[r:CHANGED_TO]->(version)
    RETURN us {.*} as current,
           collect(version {.*, changedAt: r.changedAt}) as history
    ORDER BY r.changedAt DESC
    """
    
    with get_session() as session:
        result = session.run(query, user_story_id=user_story_id)
        record = result.single()
        
        if not record:
            raise HTTPException(status_code=404, detail=f"User story {user_story_id} not found")
        
        return {
            "current": dict(record["current"]) if record["current"] else None,
            "history": [dict(h) for h in record["history"]]
        }

