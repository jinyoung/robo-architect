"""
User Story Management API - Add and manage user stories with automatic domain object generation

Provides endpoints for:
- Adding new user stories with auto-placement in BCs
- Generating related domain objects (Aggregates, Commands, Events)
- Creating connections between objects
"""

from __future__ import annotations

import os
from typing import Any, Optional, List

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

load_dotenv()

router = APIRouter(prefix="/api/user-story", tags=["user-story"])

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


class AddUserStoryRequest(BaseModel):
    """Request to add a new user story."""
    role: str
    action: str
    benefit: Optional[str] = None
    targetBcId: Optional[str] = None  # Optional: if provided, add to this BC
    autoGenerate: bool = True  # Generate related objects automatically


class ApplyUserStoryRequest(BaseModel):
    """Request to apply the generated plan for a new user story."""
    userStory: dict
    targetBcId: Optional[str] = None
    changePlan: List[dict]


class AddUserStoryResponse(BaseModel):
    """Response after analyzing a new user story."""
    scope: str
    scopeReasoning: str
    keywords: List[str] = Field(default_factory=list)
    relatedObjects: List[dict] = Field(default_factory=list)
    changes: List[dict]
    summary: str


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/add")
async def add_user_story(request: AddUserStoryRequest) -> dict[str, Any]:
    """
    Add a new user story and generate a plan for related domain objects.
    
    This endpoint uses the LangGraph workflow to:
    1. Analyze the user story to understand its intent
    2. Find the best matching BC or propose creating a new one
    3. Generate related Aggregates, Commands, Events
    4. Return the plan for human approval
    
    The plan is NOT applied automatically - use /apply to apply it.
    """
    from agent.user_story_graph import run_user_story_planning
    
    try:
        result = run_user_story_planning(
            role=request.role,
            action=request.action,
            benefit=request.benefit or "",
            target_bc_id=request.targetBcId,
            auto_generate=request.autoGenerate
        )
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")


@router.post("/apply")
async def apply_user_story(request: ApplyUserStoryRequest) -> dict[str, Any]:
    """
    Apply the approved plan for a new user story.
    
    Steps:
    1. Create the user story node
    2. Apply each change in the plan (create objects, connections)
    3. Return results
    """
    import uuid
    
    applied_changes = []
    errors = []
    user_story_id = f"US-{str(uuid.uuid4())[:8].upper()}"
    
    with get_session() as session:
        # Step 1: Create the user story
        try:
            us_query = """
            CREATE (us:UserStory {
                id: $us_id,
                role: $role,
                action: $action,
                benefit: $benefit,
                priority: 'medium',
                status: 'new',
                createdAt: datetime()
            })
            RETURN us.id as id
            """
            session.run(
                us_query,
                us_id=user_story_id,
                role=request.userStory.get("role", ""),
                action=request.userStory.get("action", ""),
                benefit=request.userStory.get("benefit", "")
            )
            applied_changes.append({
                "action": "create",
                "targetType": "UserStory",
                "targetId": user_story_id,
                "targetName": f"{request.userStory.get('role')}: {request.userStory.get('action', '')[:30]}...",
                "success": True
            })
        except Exception as e:
            errors.append(f"Failed to create user story: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create user story: {str(e)}")
        
        # Step 2: Connect to BC if specified
        target_bc_id = request.targetBcId
        if target_bc_id:
            try:
                bc_connect_query = """
                MATCH (us:UserStory {id: $us_id})
                MATCH (bc:BoundedContext {id: $bc_id})
                MERGE (us)-[:IMPLEMENTS]->(bc)
                RETURN bc.id as id
                """
                session.run(bc_connect_query, us_id=user_story_id, bc_id=target_bc_id)
                applied_changes.append({
                    "action": "connect",
                    "targetType": "BoundedContext",
                    "targetId": target_bc_id,
                    "connectionType": "IMPLEMENTS",
                    "sourceId": user_story_id,
                    "success": True
                })
            except Exception as e:
                errors.append(f"Failed to connect to BC: {str(e)}")
        
        # Step 3: Apply each change in the plan
        for change in request.changePlan:
            try:
                action = change.get("action")
                target_type = change.get("targetType")
                target_id = change.get("targetId")
                target_name = change.get("targetName")
                target_bc_id = change.get("targetBcId")
                connection_type = change.get("connectionType")
                source_id = change.get("sourceId")
                
                if action == "create":
                    if target_type == "Aggregate":
                        create_query = """
                        MERGE (agg:Aggregate {id: $agg_id})
                        SET agg.name = $name,
                            agg.rootEntity = $name,
                            agg.description = $description,
                            agg.createdAt = datetime()
                        WITH agg
                        OPTIONAL MATCH (bc:BoundedContext {id: $bc_id})
                        WHERE bc IS NOT NULL
                        MERGE (bc)-[:HAS_AGGREGATE]->(agg)
                        WITH agg
                        MATCH (us:UserStory {id: $us_id})
                        MERGE (us)-[:IMPLEMENTS]->(agg)
                        RETURN agg.id as id
                        """
                        session.run(
                            create_query,
                            agg_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            bc_id=target_bc_id,
                            us_id=user_story_id
                        )
                        
                    elif target_type == "Command":
                        create_query = """
                        MERGE (cmd:Command {id: $cmd_id})
                        SET cmd.name = $name,
                            cmd.actor = $actor,
                            cmd.description = $description,
                            cmd.createdAt = datetime()
                        WITH cmd
                        OPTIONAL MATCH (agg:Aggregate {id: $agg_id})
                        WHERE agg IS NOT NULL
                        MERGE (agg)-[:HAS_COMMAND]->(cmd)
                        RETURN cmd.id as id
                        """
                        session.run(
                            create_query,
                            cmd_id=target_id,
                            name=target_name,
                            actor=change.get("actor", "user"),
                            description=change.get("description", ""),
                            agg_id=source_id or change.get("aggregateId")
                        )
                        
                    elif target_type == "Event":
                        create_query = """
                        MERGE (evt:Event {id: $evt_id})
                        SET evt.name = $name,
                            evt.version = 1,
                            evt.description = $description,
                            evt.createdAt = datetime()
                        WITH evt
                        OPTIONAL MATCH (cmd:Command {id: $cmd_id})
                        WHERE cmd IS NOT NULL
                        MERGE (cmd)-[:EMITS]->(evt)
                        RETURN evt.id as id
                        """
                        session.run(
                            create_query,
                            evt_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            cmd_id=source_id or change.get("commandId")
                        )
                        
                    elif target_type == "Policy":
                        create_query = """
                        MERGE (pol:Policy {id: $pol_id})
                        SET pol.name = $name,
                            pol.description = $description,
                            pol.createdAt = datetime()
                        WITH pol
                        OPTIONAL MATCH (bc:BoundedContext {id: $bc_id})
                        WHERE bc IS NOT NULL
                        MERGE (bc)-[:HAS_POLICY]->(pol)
                        RETURN pol.id as id
                        """
                        session.run(
                            create_query,
                            pol_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            bc_id=target_bc_id
                        )
                    
                    elif target_type == "BoundedContext":
                        create_query = """
                        MERGE (bc:BoundedContext {id: $bc_id})
                        SET bc.name = $name,
                            bc.description = $description,
                            bc.createdAt = datetime()
                        WITH bc
                        MATCH (us:UserStory {id: $us_id})
                        MERGE (us)-[:IMPLEMENTS]->(bc)
                        RETURN bc.id as id
                        """
                        session.run(
                            create_query,
                            bc_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            us_id=user_story_id
                        )
                        # Update target BC for subsequent objects
                        target_bc_id = target_id
                    
                    applied_changes.append({
                        **change,
                        "success": True
                    })
                    
                elif action == "connect":
                    if connection_type == "TRIGGERS":
                        connect_query = """
                        MATCH (evt:Event {id: $source_id})
                        MATCH (pol:Policy {id: $target_id})
                        MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
                        RETURN evt.id as id
                        """
                        session.run(connect_query, source_id=source_id, target_id=target_id)
                    elif connection_type == "INVOKES":
                        connect_query = """
                        MATCH (pol:Policy {id: $source_id})
                        MATCH (cmd:Command {id: $target_id})
                        MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
                        RETURN pol.id as id
                        """
                        session.run(connect_query, source_id=source_id, target_id=target_id)
                    elif connection_type == "IMPLEMENTS":
                        connect_query = """
                        MATCH (us:UserStory {id: $source_id})
                        MATCH (n {id: $target_id})
                        MERGE (us)-[:IMPLEMENTS]->(n)
                        RETURN us.id as id
                        """
                        session.run(connect_query, source_id=source_id, target_id=target_id)
                    
                    applied_changes.append({
                        **change,
                        "success": True
                    })
                    
                elif action == "update":
                    update_query = """
                    MATCH (n {id: $node_id})
                    SET n.name = $name, n.updatedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(update_query, node_id=target_id, name=target_name)
                    applied_changes.append({
                        **change,
                        "success": True
                    })
                    
            except Exception as e:
                errors.append(f"Failed to apply {action} on {target_id}: {str(e)}")
                applied_changes.append({
                    **change,
                    "success": False,
                    "error": str(e)
                })
    
    return {
        "success": len(errors) == 0,
        "userStoryId": user_story_id,
        "appliedChanges": applied_changes,
        "errors": errors
    }


@router.get("/unassigned")
async def get_unassigned_user_stories() -> List[dict[str, Any]]:
    """
    Get all user stories that are not assigned to any Bounded Context.
    """
    query = """
    MATCH (us:UserStory)
    WHERE NOT (us)-[:IMPLEMENTS]->(:BoundedContext)
    RETURN us {.id, .role, .action, .benefit, .priority, .status} as userStory
    ORDER BY us.createdAt DESC
    """
    
    with get_session() as session:
        result = session.run(query)
        return [dict(record["userStory"]) for record in result]

