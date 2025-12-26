"""
Ingestion API - Document Upload and Step-by-Step Processing with User Review

Provides:
- File upload endpoint (text, PDF)
- SSE streaming for real-time progress updates
- Step-by-step workflow with user review at each phase
- Feedback-based regeneration support
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Add parent directory to path for agent imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


# =============================================================================
# Workflow Steps
# =============================================================================


class WorkflowStep(str, Enum):
    """Workflow steps that require user review."""
    UPLOAD = "upload"
    PARSING = "parsing"
    USER_STORIES = "user_stories"
    BOUNDED_CONTEXTS = "bounded_contexts"
    USER_STORY_MAPPING = "user_story_mapping"
    AGGREGATES = "aggregates"
    COMMANDS = "commands"
    EVENTS = "events"
    POLICIES = "policies"
    COMPLETE = "complete"
    ERROR = "error"


# Steps that require user review
REVIEW_STEPS = [
    WorkflowStep.USER_STORIES,
    WorkflowStep.BOUNDED_CONTEXTS,
    WorkflowStep.USER_STORY_MAPPING,
    WorkflowStep.AGGREGATES,
    WorkflowStep.COMMANDS,
    WorkflowStep.EVENTS,
    WorkflowStep.POLICIES,
]

STEP_LABELS = {
    WorkflowStep.USER_STORIES: "User Story 추출",
    WorkflowStep.BOUNDED_CONTEXTS: "Bounded Context 식별",
    WorkflowStep.USER_STORY_MAPPING: "User Story - BC 매핑",
    WorkflowStep.AGGREGATES: "Aggregate 추출",
    WorkflowStep.COMMANDS: "Command 추출",
    WorkflowStep.EVENTS: "Event 추출",
    WorkflowStep.POLICIES: "Policy 식별",
}


# =============================================================================
# Models
# =============================================================================


class StepEvent(BaseModel):
    """Event sent via SSE for each step."""
    step: WorkflowStep
    status: str  # 'processing', 'review_required', 'completed', 'error'
    message: str
    progress: int  # 0-100
    data: Optional[dict] = None
    items: Optional[list] = None  # Generated items for review
    waitForReview: bool = False


class ReviewAction(BaseModel):
    """User's review action."""
    action: str  # 'approve' or 'regenerate'
    feedback: Optional[str] = None  # Natural language feedback for regeneration


class GeneratedUserStory(BaseModel):
    """Generated User Story from requirements."""
    id: str
    role: str
    action: str
    benefit: str
    priority: str = "medium"


class UserStoryList(BaseModel):
    """List of generated user stories."""
    user_stories: list[GeneratedUserStory]


# =============================================================================
# Session Storage
# =============================================================================


@dataclass
class IngestionSession:
    """Tracks state of an ingestion session with step-by-step workflow."""
    id: str
    current_step: WorkflowStep = WorkflowStep.UPLOAD
    status: str = "idle"  # 'idle', 'processing', 'waiting_review', 'completed', 'error'
    message: str = ""
    content: str = ""
    
    # Accumulated data from each step
    user_stories: list = field(default_factory=list)
    bounded_contexts: list = field(default_factory=list)
    user_story_mappings: dict = field(default_factory=dict)  # {bc_id: [us_ids]}
    aggregates: dict = field(default_factory=dict)  # {bc_id: [aggregates]}
    commands: dict = field(default_factory=dict)  # {agg_id: [commands]}
    events: dict = field(default_factory=dict)  # {agg_id: [events]}
    policies: list = field(default_factory=list)
    
    # Review state
    pending_review_data: Optional[dict] = None
    feedback_history: list = field(default_factory=list)
    
    # Event queue for SSE
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    
    # Control flags
    waiting_for_review: bool = False
    should_continue: bool = False
    regenerate_with_feedback: Optional[str] = None


# Active sessions
_sessions: dict[str, IngestionSession] = {}


def get_session(session_id: str) -> Optional[IngestionSession]:
    return _sessions.get(session_id)


def create_session() -> IngestionSession:
    session_id = str(uuid.uuid4())[:8]
    session = IngestionSession(id=session_id)
    _sessions[session_id] = session
    return session


# =============================================================================
# PDF Extraction
# =============================================================================


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=file_content, filetype="pdf")
        text_parts = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_parts.append(page.get_text())
        
        doc.close()
        return "\n".join(text_parts)
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF processing requires PyMuPDF. Install with: pip install PyMuPDF"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")


# =============================================================================
# LLM Integration
# =============================================================================


def get_llm():
    """Get configured LLM instance."""
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL", "gpt-4o")
    
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0)


# =============================================================================
# Step Processors
# =============================================================================


def extract_user_stories(content: str, feedback: Optional[str] = None) -> list[GeneratedUserStory]:
    """Extract user stories from requirements text."""
    from langchain_core.messages import HumanMessage, SystemMessage
    
    prompt = f"""분석할 요구사항 문서:

{content[:8000]}

---

위 요구사항을 분석하여 User Story 목록을 추출하세요.

지침:
1. 각 기능/요구사항을 독립적인 User Story로 변환
2. "As a [role], I want to [action], so that [benefit]" 형식 사용
3. 역할(role)은 구체적으로 (customer, seller, admin, system 등)
4. 액션(action)은 명확한 동사로 시작
5. 이점(benefit)은 비즈니스 가치 설명
6. 우선순위는 핵심 기능은 high, 부가 기능은 medium, 선택 기능은 low

User Story ID는 US-001, US-002 형식으로 순차적으로 부여하세요.
모든 주요 기능을 빠짐없이 User Story로 추출하세요."""

    if feedback:
        prompt += f"""

사용자 피드백 (반드시 반영하세요):
{feedback}"""

    llm = get_llm()
    structured_llm = llm.with_structured_output(UserStoryList)
    
    system_prompt = """당신은 도메인 주도 설계(DDD) 전문가입니다. 
요구사항을 User Story로 변환하는 작업을 수행합니다.
User Story는 명확하고 테스트 가능해야 합니다."""
    
    response = structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ])
    
    return response.user_stories


def identify_bounded_contexts(user_stories: list, feedback: Optional[str] = None):
    """Identify bounded contexts from user stories."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from agent.nodes import BoundedContextList
    from agent.prompts import SYSTEM_PROMPT
    
    stories_text = "\n".join([
        f"[{us.id if hasattr(us, 'id') else us['id']}] As a {us.role if hasattr(us, 'role') else us['role']}, "
        f"I want to {us.action if hasattr(us, 'action') else us['action']}, "
        f"so that {us.benefit if hasattr(us, 'benefit') else us['benefit']}"
        for us in user_stories
    ])
    
    prompt = f"""다음 User Story들을 분석하여 적절한 Bounded Context들을 식별하세요.

User Stories:
{stories_text}

---

지침:
1. 관련 도메인 개념들을 그룹화하여 Bounded Context 식별
2. 각 BC는 명확한 책임과 경계를 가져야 함
3. BC 이름은 영어로, 명확하고 간결하게
4. 각 BC에 어떤 User Story들이 속하는지 user_story_ids에 포함
5. BC ID는 BC-영문약어 형식 (예: BC-ORD, BC-PAY)

모든 User Story가 최소 하나의 BC에 할당되어야 합니다."""

    if feedback:
        prompt += f"""

사용자 피드백 (반드시 반영하세요):
{feedback}"""

    llm = get_llm()
    structured_llm = llm.with_structured_output(BoundedContextList)
    
    response = structured_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])
    
    return response.bounded_contexts


def extract_aggregates_for_bc(bc, user_stories: list, feedback: Optional[str] = None):
    """Extract aggregates for a specific bounded context."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from agent.nodes import AggregateList
    from agent.prompts import SYSTEM_PROMPT, EXTRACT_AGGREGATES_PROMPT
    
    bc_id_short = bc.id.replace("BC-", "")
    
    # Get user stories for this BC
    bc_stories = [us for us in user_stories 
                  if (us.id if hasattr(us, 'id') else us['id']) in bc.user_story_ids]
    
    breakdowns_text = "\n".join([
        f"- [{us.id if hasattr(us, 'id') else us['id']}] {us.action if hasattr(us, 'action') else us['action']}"
        for us in bc_stories
    ])
    
    prompt = EXTRACT_AGGREGATES_PROMPT.format(
        bc_name=bc.name,
        bc_id=bc.id,
        bc_id_short=bc_id_short,
        bc_description=bc.description,
        breakdowns=breakdowns_text
    )
    
    if feedback:
        prompt += f"""

사용자 피드백 (반드시 반영하세요):
{feedback}"""

    llm = get_llm()
    structured_llm = llm.with_structured_output(AggregateList)
    
    response = structured_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])
    
    return response.aggregates


def extract_commands_for_aggregate(agg, bc, user_stories: list, feedback: Optional[str] = None):
    """Extract commands for a specific aggregate."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from agent.nodes import CommandList
    from agent.prompts import SYSTEM_PROMPT, EXTRACT_COMMANDS_PROMPT
    
    bc_id_short = bc.id.replace("BC-", "")
    
    # Get user stories for this BC
    bc_stories = [us for us in user_stories 
                  if (us.id if hasattr(us, 'id') else us['id']) in bc.user_story_ids]
    
    stories_context = "\n".join([
        f"[{us.id if hasattr(us, 'id') else us['id']}] As a {us.role if hasattr(us, 'role') else us['role']}, "
        f"I want to {us.action if hasattr(us, 'action') else us['action']}"
        for us in bc_stories
    ])
    
    prompt = EXTRACT_COMMANDS_PROMPT.format(
        aggregate_name=agg.name,
        aggregate_id=agg.id,
        bc_name=bc.name,
        bc_short=bc_id_short,
        user_story_context=stories_context[:2000]
    )
    
    if feedback:
        prompt += f"""

사용자 피드백 (반드시 반영하세요):
{feedback}"""

    llm = get_llm()
    structured_llm = llm.with_structured_output(CommandList)
    
    try:
        response = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        return response.commands
    except Exception:
        return []


def extract_events_for_aggregate(agg, bc, commands: list, feedback: Optional[str] = None):
    """Extract events for a specific aggregate."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from agent.nodes import EventList
    from agent.prompts import SYSTEM_PROMPT, EXTRACT_EVENTS_PROMPT
    
    if not commands:
        return []
    
    bc_id_short = bc.id.replace("BC-", "")
    
    commands_text = "\n".join([
        f"- {cmd.name}: {cmd.description}" if hasattr(cmd, 'description') and cmd.description else f"- {cmd.name}"
        for cmd in commands
    ])
    
    prompt = EXTRACT_EVENTS_PROMPT.format(
        aggregate_name=agg.name,
        bc_name=bc.name,
        bc_short=bc_id_short,
        commands=commands_text
    )
    
    if feedback:
        prompt += f"""

사용자 피드백 (반드시 반영하세요):
{feedback}"""

    llm = get_llm()
    structured_llm = llm.with_structured_output(EventList)
    
    try:
        response = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        return response.events
    except Exception:
        return []


def identify_policies(bounded_contexts, aggregates, commands, events, feedback: Optional[str] = None):
    """Identify policies across bounded contexts."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from agent.nodes import PolicyList
    from agent.prompts import SYSTEM_PROMPT, IDENTIFY_POLICIES_PROMPT
    
    # Collect all events
    all_events_list = []
    for agg_id, evts in events.items():
        for evt in evts:
            all_events_list.append(f"- {evt.name}")
    
    events_text = "\n".join(all_events_list)
    
    # Collect commands by BC
    commands_by_bc = {}
    for bc in bounded_contexts:
        bc_cmds = []
        for agg in aggregates.get(bc.id, []):
            for cmd in commands.get(agg.id, []):
                bc_cmds.append(f"- {cmd.name}")
        commands_by_bc[bc.name] = "\n".join(bc_cmds) if bc_cmds else "No commands"
    
    commands_text = "\n".join([
        f"{bc_name}:\n{cmds}" for bc_name, cmds in commands_by_bc.items()
    ])
    
    bc_text = "\n".join([
        f"- {bc.name}: {bc.description}" for bc in bounded_contexts
    ])
    
    prompt = IDENTIFY_POLICIES_PROMPT.format(
        events=events_text,
        commands_by_bc=commands_text,
        bounded_contexts=bc_text
    )
    
    if feedback:
        prompt += f"""

사용자 피드백 (반드시 반영하세요):
{feedback}"""

    llm = get_llm()
    structured_llm = llm.with_structured_output(PolicyList)
    
    try:
        response = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        return response.policies
    except Exception:
        return []


# =============================================================================
# Workflow Runner
# =============================================================================


async def run_step_workflow(session: IngestionSession) -> AsyncGenerator[StepEvent, None]:
    """
    Run the step-by-step workflow with review checkpoints.
    Yields StepEvent objects and pauses at each review step.
    """
    from agent.neo4j_client import get_neo4j_client
    
    client = get_neo4j_client()
    
    try:
        # ===================
        # STEP 1: User Stories
        # ===================
        session.current_step = WorkflowStep.USER_STORIES
        
        yield StepEvent(
            step=WorkflowStep.USER_STORIES,
            status="processing",
            message="User Story 추출 중...",
            progress=10
        )
        
        feedback = session.regenerate_with_feedback
        session.regenerate_with_feedback = None
        
        user_stories = extract_user_stories(session.content, feedback)
        session.user_stories = user_stories
        
        # Emit each user story for UI
        for i, us in enumerate(user_stories):
            yield StepEvent(
                step=WorkflowStep.USER_STORIES,
                status="processing",
                message=f"User Story 생성: {us.id}",
                progress=10 + (5 * (i + 1) // len(user_stories)),
                data={
                    "type": "UserStory",
                    "object": {
                        "id": us.id,
                        "name": f"{us.role}: {us.action[:30]}...",
                        "type": "UserStory",
                        "role": us.role,
                        "action": us.action,
                        "benefit": us.benefit,
                        "priority": us.priority
                    }
                }
            )
            await asyncio.sleep(0.1)
        
        # Save to Neo4j
        for us in user_stories:
            try:
                client.create_user_story(
                    id=us.id,
                    role=us.role,
                    action=us.action,
                    benefit=us.benefit,
                    priority=us.priority,
                    status="draft"
                )
            except Exception:
                pass
        
        # Request review
        yield StepEvent(
            step=WorkflowStep.USER_STORIES,
            status="review_required",
            message=f"{len(user_stories)}개 User Story 추출 완료 - 검토해주세요",
            progress=15,
            items=[{
                "id": us.id,
                "role": us.role,
                "action": us.action,
                "benefit": us.benefit,
                "priority": us.priority
            } for us in user_stories],
            waitForReview=True
        )
        
        # Wait for user review
        session.waiting_for_review = True
        while session.waiting_for_review:
            await asyncio.sleep(0.1)
        
        # Check if regeneration requested
        if session.regenerate_with_feedback:
            # Clear and restart this step
            for us in session.user_stories:
                try:
                    client.delete_node(us.id)
                except Exception:
                    pass
            async for event in run_step_workflow(session):
                yield event
            return
        
        # ===================
        # STEP 2: Bounded Contexts
        # ===================
        session.current_step = WorkflowStep.BOUNDED_CONTEXTS
        
        yield StepEvent(
            step=WorkflowStep.BOUNDED_CONTEXTS,
            status="processing",
            message="Bounded Context 식별 중...",
            progress=20
        )
        
        feedback = session.regenerate_with_feedback
        session.regenerate_with_feedback = None
        
        bounded_contexts = identify_bounded_contexts(session.user_stories, feedback)
        session.bounded_contexts = bounded_contexts
        
        # Emit each BC for UI
        for i, bc in enumerate(bounded_contexts):
            yield StepEvent(
                step=WorkflowStep.BOUNDED_CONTEXTS,
                status="processing",
                message=f"BC 생성: {bc.name}",
                progress=20 + (5 * (i + 1) // len(bounded_contexts)),
                data={
                    "type": "BoundedContext",
                    "object": {
                        "id": bc.id,
                        "name": bc.name,
                        "type": "BoundedContext",
                        "description": bc.description,
                        "userStoryIds": bc.user_story_ids
                    }
                }
            )
            await asyncio.sleep(0.1)
        
        # Save to Neo4j
        for bc in bounded_contexts:
            try:
                client.create_bounded_context(
                    id=bc.id,
                    name=bc.name,
                    description=bc.description
                )
            except Exception:
                pass
        
        # Request review
        yield StepEvent(
            step=WorkflowStep.BOUNDED_CONTEXTS,
            status="review_required",
            message=f"{len(bounded_contexts)}개 Bounded Context 식별 완료 - 검토해주세요",
            progress=25,
            items=[{
                "id": bc.id,
                "name": bc.name,
                "description": bc.description,
                "userStoryIds": bc.user_story_ids
            } for bc in bounded_contexts],
            waitForReview=True
        )
        
        session.waiting_for_review = True
        while session.waiting_for_review:
            await asyncio.sleep(0.1)
        
        if session.regenerate_with_feedback:
            for bc in session.bounded_contexts:
                try:
                    client.delete_node(bc.id)
                except Exception:
                    pass
            session.current_step = WorkflowStep.BOUNDED_CONTEXTS
            # Re-run from BC step
            feedback = session.regenerate_with_feedback
            session.regenerate_with_feedback = None
            bounded_contexts = identify_bounded_contexts(session.user_stories, feedback)
            session.bounded_contexts = bounded_contexts
            # Continue below...
        
        # ===================
        # STEP 3: User Story Mapping
        # ===================
        session.current_step = WorkflowStep.USER_STORY_MAPPING
        
        yield StepEvent(
            step=WorkflowStep.USER_STORY_MAPPING,
            status="processing",
            message="User Story를 BC에 매핑 중...",
            progress=30
        )
        
        # Link user stories to BCs
        mappings = []
        for bc in session.bounded_contexts:
            for us_id in bc.user_story_ids:
                try:
                    client.link_user_story_to_bc(us_id, bc.id)
                    mappings.append({"usId": us_id, "bcId": bc.id, "bcName": bc.name})
                    
                    yield StepEvent(
                        step=WorkflowStep.USER_STORY_MAPPING,
                        status="processing",
                        message=f"{us_id} → {bc.name}",
                        progress=35,
                        data={
                            "type": "UserStoryAssigned",
                            "object": {
                                "id": us_id,
                                "type": "UserStory",
                                "targetBcId": bc.id,
                                "targetBcName": bc.name
                            }
                        }
                    )
                    await asyncio.sleep(0.05)
                except Exception:
                    pass
        
        session.user_story_mappings = {bc.id: bc.user_story_ids for bc in session.bounded_contexts}
        
        # Request review
        yield StepEvent(
            step=WorkflowStep.USER_STORY_MAPPING,
            status="review_required",
            message="User Story 매핑 완료 - 검토해주세요",
            progress=40,
            items=mappings,
            waitForReview=True
        )
        
        session.waiting_for_review = True
        while session.waiting_for_review:
            await asyncio.sleep(0.1)
        
        # ===================
        # STEP 4: Aggregates
        # ===================
        session.current_step = WorkflowStep.AGGREGATES
        
        yield StepEvent(
            step=WorkflowStep.AGGREGATES,
            status="processing",
            message="Aggregate 추출 중...",
            progress=45
        )
        
        feedback = session.regenerate_with_feedback
        session.regenerate_with_feedback = None
        
        all_aggregates = {}
        all_agg_items = []
        
        for bc in session.bounded_contexts:
            aggregates = extract_aggregates_for_bc(bc, session.user_stories, feedback)
            all_aggregates[bc.id] = aggregates
            
            for agg in aggregates:
                try:
                    client.create_aggregate(
                        id=agg.id,
                        name=agg.name,
                        bc_id=bc.id,
                        root_entity=agg.root_entity,
                        invariants=agg.invariants
                    )
                except Exception:
                    pass
                
                yield StepEvent(
                    step=WorkflowStep.AGGREGATES,
                    status="processing",
                    message=f"Aggregate 생성: {agg.name}",
                    progress=50,
                    data={
                        "type": "Aggregate",
                        "object": {
                            "id": agg.id,
                            "name": agg.name,
                            "type": "Aggregate",
                            "parentId": bc.id
                        }
                    }
                )
                await asyncio.sleep(0.1)
                
                all_agg_items.append({
                    "id": agg.id,
                    "name": agg.name,
                    "bcId": bc.id,
                    "bcName": bc.name,
                    "rootEntity": agg.root_entity
                })
        
        session.aggregates = all_aggregates
        
        # Request review
        yield StepEvent(
            step=WorkflowStep.AGGREGATES,
            status="review_required",
            message=f"{len(all_agg_items)}개 Aggregate 추출 완료 - 검토해주세요",
            progress=55,
            items=all_agg_items,
            waitForReview=True
        )
        
        session.waiting_for_review = True
        while session.waiting_for_review:
            await asyncio.sleep(0.1)
        
        # ===================
        # STEP 5: Commands
        # ===================
        session.current_step = WorkflowStep.COMMANDS
        
        yield StepEvent(
            step=WorkflowStep.COMMANDS,
            status="processing",
            message="Command 추출 중...",
            progress=60
        )
        
        feedback = session.regenerate_with_feedback
        session.regenerate_with_feedback = None
        
        all_commands = {}
        all_cmd_items = []
        
        for bc in session.bounded_contexts:
            bc_aggregates = session.aggregates.get(bc.id, [])
            
            for agg in bc_aggregates:
                commands = extract_commands_for_aggregate(agg, bc, session.user_stories, feedback)
                all_commands[agg.id] = commands
                
                for cmd in commands:
                    try:
                        client.create_command(
                            id=cmd.id,
                            name=cmd.name,
                            aggregate_id=agg.id,
                            actor=cmd.actor
                        )
                    except Exception:
                        pass
                    
                    yield StepEvent(
                        step=WorkflowStep.COMMANDS,
                        status="processing",
                        message=f"Command 생성: {cmd.name}",
                        progress=65,
                        data={
                            "type": "Command",
                            "object": {
                                "id": cmd.id,
                                "name": cmd.name,
                                "type": "Command",
                                "parentId": agg.id
                            }
                        }
                    )
                    await asyncio.sleep(0.05)
                    
                    all_cmd_items.append({
                        "id": cmd.id,
                        "name": cmd.name,
                        "aggregateId": agg.id,
                        "aggregateName": agg.name,
                        "actor": cmd.actor
                    })
        
        session.commands = all_commands
        
        # Request review
        yield StepEvent(
            step=WorkflowStep.COMMANDS,
            status="review_required",
            message=f"{len(all_cmd_items)}개 Command 추출 완료 - 검토해주세요",
            progress=70,
            items=all_cmd_items,
            waitForReview=True
        )
        
        session.waiting_for_review = True
        while session.waiting_for_review:
            await asyncio.sleep(0.1)
        
        # ===================
        # STEP 6: Events
        # ===================
        session.current_step = WorkflowStep.EVENTS
        
        yield StepEvent(
            step=WorkflowStep.EVENTS,
            status="processing",
            message="Event 추출 중...",
            progress=75
        )
        
        feedback = session.regenerate_with_feedback
        session.regenerate_with_feedback = None
        
        all_events = {}
        all_evt_items = []
        
        for bc in session.bounded_contexts:
            bc_aggregates = session.aggregates.get(bc.id, [])
            
            for agg in bc_aggregates:
                commands = session.commands.get(agg.id, [])
                events = extract_events_for_aggregate(agg, bc, commands, feedback)
                all_events[agg.id] = events
                
                for i, evt in enumerate(events):
                    cmd_id = commands[i].id if i < len(commands) else commands[0].id if commands else None
                    
                    if cmd_id:
                        try:
                            client.create_event(
                                id=evt.id,
                                name=evt.name,
                                command_id=cmd_id
                            )
                        except Exception:
                            pass
                        
                        yield StepEvent(
                            step=WorkflowStep.EVENTS,
                            status="processing",
                            message=f"Event 생성: {evt.name}",
                            progress=80,
                            data={
                                "type": "Event",
                                "object": {
                                    "id": evt.id,
                                    "name": evt.name,
                                    "type": "Event",
                                    "parentId": cmd_id
                                }
                            }
                        )
                        await asyncio.sleep(0.05)
                        
                        all_evt_items.append({
                            "id": evt.id,
                            "name": evt.name,
                            "commandId": cmd_id,
                            "aggregateName": agg.name
                        })
        
        session.events = all_events
        
        # Request review
        yield StepEvent(
            step=WorkflowStep.EVENTS,
            status="review_required",
            message=f"{len(all_evt_items)}개 Event 추출 완료 - 검토해주세요",
            progress=85,
            items=all_evt_items,
            waitForReview=True
        )
        
        session.waiting_for_review = True
        while session.waiting_for_review:
            await asyncio.sleep(0.1)
        
        # ===================
        # STEP 7: Policies
        # ===================
        session.current_step = WorkflowStep.POLICIES
        
        yield StepEvent(
            step=WorkflowStep.POLICIES,
            status="processing",
            message="Policy 식별 중...",
            progress=90
        )
        
        feedback = session.regenerate_with_feedback
        session.regenerate_with_feedback = None
        
        policies = identify_policies(
            session.bounded_contexts,
            session.aggregates,
            session.commands,
            session.events,
            feedback
        )
        session.policies = policies
        
        all_pol_items = []
        
        for pol in policies:
            # Find trigger event and invoke command IDs
            trigger_event_id = None
            invoke_command_id = None
            target_bc_id = None
            
            for agg_id, evts in session.events.items():
                for evt in evts:
                    if evt.name == pol.trigger_event:
                        trigger_event_id = evt.id
                        break
            
            for bc in session.bounded_contexts:
                if bc.name == pol.target_bc or bc.id == pol.target_bc:
                    target_bc_id = bc.id
                    for agg in session.aggregates.get(bc.id, []):
                        for cmd in session.commands.get(agg.id, []):
                            if cmd.name == pol.invoke_command:
                                invoke_command_id = cmd.id
                                break
            
            if trigger_event_id and invoke_command_id and target_bc_id:
                try:
                    client.create_policy(
                        id=pol.id,
                        name=pol.name,
                        bc_id=target_bc_id,
                        trigger_event_id=trigger_event_id,
                        invoke_command_id=invoke_command_id,
                        description=pol.description
                    )
                except Exception:
                    pass
                
                yield StepEvent(
                    step=WorkflowStep.POLICIES,
                    status="processing",
                    message=f"Policy 생성: {pol.name}",
                    progress=95,
                    data={
                        "type": "Policy",
                        "object": {
                            "id": pol.id,
                            "name": pol.name,
                            "type": "Policy",
                            "parentId": target_bc_id
                        }
                    }
                )
                await asyncio.sleep(0.1)
                
                all_pol_items.append({
                    "id": pol.id,
                    "name": pol.name,
                    "triggerEvent": pol.trigger_event,
                    "invokeCommand": pol.invoke_command,
                    "description": pol.description
                })
        
        # Request review
        yield StepEvent(
            step=WorkflowStep.POLICIES,
            status="review_required",
            message=f"{len(all_pol_items)}개 Policy 식별 완료 - 검토해주세요",
            progress=98,
            items=all_pol_items,
            waitForReview=True
        )
        
        session.waiting_for_review = True
        while session.waiting_for_review:
            await asyncio.sleep(0.1)
        
        # ===================
        # COMPLETE
        # ===================
        session.current_step = WorkflowStep.COMPLETE
        
        yield StepEvent(
            step=WorkflowStep.COMPLETE,
            status="completed",
            message="✅ 모델 생성 완료!",
            progress=100,
            data={
                "summary": {
                    "user_stories": len(session.user_stories),
                    "bounded_contexts": len(session.bounded_contexts),
                    "aggregates": sum(len(aggs) for aggs in session.aggregates.values()),
                    "commands": sum(len(cmds) for cmds in session.commands.values()),
                    "events": sum(len(evts) for evts in session.events.values()),
                    "policies": len([p for p in session.policies])
                }
            }
        )
        
    except Exception as e:
        yield StepEvent(
            step=WorkflowStep.ERROR,
            status="error",
            message=f"❌ 오류 발생: {str(e)}",
            progress=0,
            data={"error": str(e)}
        )


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/upload")
async def upload_document(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
) -> dict[str, Any]:
    """
    Upload a requirements document (text or PDF) to start ingestion.
    Returns a session_id for SSE streaming of progress.
    """
    content = ""
    
    if file:
        file_content = await file.read()
        filename = file.filename or ""
        
        if filename.lower().endswith('.pdf'):
            content = extract_text_from_pdf(file_content)
        else:
            try:
                content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                content = file_content.decode('latin-1')
    elif text:
        content = text
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'file' or 'text' must be provided"
        )
    
    if not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Document content is empty"
        )
    
    # Create session
    session = create_session()
    session.content = content
    
    return {
        "session_id": session.id,
        "content_length": len(content),
        "preview": content[:500] + "..." if len(content) > 500 else content
    }


@router.get("/stream/{session_id}")
async def stream_progress(session_id: str):
    """
    SSE endpoint for streaming ingestion progress.
    Pauses at each step for user review.
    """
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    async def event_generator():
        async for event in run_step_workflow(session):
            yield {
                "event": "step",
                "data": event.model_dump_json()
            }
        
        # Clean up session after completion
        if session_id in _sessions:
            del _sessions[session_id]
    
    return EventSourceResponse(event_generator())


@router.post("/{session_id}/review")
async def submit_review(session_id: str, review: ReviewAction) -> dict[str, Any]:
    """
    Submit user review for current step.
    
    Actions:
    - 'approve': Continue to next step
    - 'regenerate': Regenerate current step with feedback
    """
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.waiting_for_review:
        raise HTTPException(status_code=400, detail="Not waiting for review")
    
    if review.action == "approve":
        session.waiting_for_review = False
        session.should_continue = True
        return {"status": "approved", "step": session.current_step.value}
    
    elif review.action == "regenerate":
        if not review.feedback:
            raise HTTPException(status_code=400, detail="Feedback required for regeneration")
        
        session.regenerate_with_feedback = review.feedback
        session.feedback_history.append({
            "step": session.current_step.value,
            "feedback": review.feedback
        })
        session.waiting_for_review = False
        return {"status": "regenerating", "step": session.current_step.value, "feedback": review.feedback}
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {review.action}")


@router.get("/{session_id}/status")
async def get_session_status(session_id: str) -> dict[str, Any]:
    """Get current status of an ingestion session."""
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "current_step": session.current_step.value,
        "waiting_for_review": session.waiting_for_review,
        "user_stories_count": len(session.user_stories),
        "bounded_contexts_count": len(session.bounded_contexts),
        "feedback_history": session.feedback_history
    }


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    """List all active ingestion sessions."""
    return [
        {
            "id": s.id,
            "current_step": s.current_step.value,
            "waiting_for_review": s.waiting_for_review
        }
        for s in _sessions.values()
    ]


@router.delete("/clear-all")
async def clear_all_data() -> dict[str, Any]:
    """Clear all nodes and relationships from Neo4j."""
    from agent.neo4j_client import get_neo4j_client
    
    client = get_neo4j_client()
    
    try:
        with client.session() as db_session:
            count_query = """
            MATCH (n)
            WITH labels(n)[0] as label, count(n) as count
            RETURN collect({label: label, count: count}) as counts
            """
            result = db_session.run(count_query)
            record = result.single()
            before_counts = {item["label"]: item["count"] for item in record["counts"]} if record else {}
            
            delete_query = "MATCH (n) DETACH DELETE n"
            db_session.run(delete_query)
            
            return {
                "success": True,
                "message": "모든 데이터가 삭제되었습니다",
                "deleted": before_counts
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"삭제 실패: {str(e)}",
            "deleted": {}
        }


@router.get("/stats")
async def get_data_stats() -> dict[str, Any]:
    """Get current data statistics from Neo4j."""
    from agent.neo4j_client import get_neo4j_client
    
    client = get_neo4j_client()
    
    try:
        with client.session() as db_session:
            query = """
            MATCH (n)
            WITH labels(n)[0] as label, count(n) as count
            RETURN collect({label: label, count: count}) as counts
            """
            result = db_session.run(query)
            record = result.single()
            counts = {item["label"]: item["count"] for item in record["counts"]} if record else {}
            
            total = sum(counts.values())
            
            return {
                "total": total,
                "counts": counts,
                "hasData": total > 0
            }
    except Exception as e:
        return {
            "total": 0,
            "counts": {},
            "hasData": False,
            "error": str(e)
        }
