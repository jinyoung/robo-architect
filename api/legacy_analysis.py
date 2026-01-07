"""
Legacy System Analysis API - 테이블/SP 기반 이벤트 스토밍 추출

Neo4j에 저장된 레거시 시스템 분석 결과(테이블, 컬럼, 스토어드 프로시저 등)를
기반으로 이벤트 스토밍 요소를 자동으로 추출합니다.

robo-analyzer에서 생성한 노드 타입:
- Table: 테이블 정보 (name, schema, description)
- Column: 컬럼 정보
- PROCEDURE, FUNCTION, TRIGGER: 스토어드 프로시저/함수/트리거
- Variable: 변수 정보

관계 타입:
- HAS_COLUMN: 테이블 → 컬럼
- FK_TO_TABLE: 외래키 관계
- FROM: 테이블 읽기
- WRITES: 테이블 쓰기
- CALL: 프로시저 호출
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent.neo4j_client import get_neo4j_client

router = APIRouter(prefix="/api/legacy", tags=["legacy-analysis"])


# =============================================================================
# Models
# =============================================================================


class LegacyAnalysisPhase(str, Enum):
    """이벤트 스토밍 추출 단계"""
    LOADING = "loading"
    ANALYZING_TABLES = "analyzing_tables"
    ANALYZING_PROCEDURES = "analyzing_procedures"
    EXTRACTING_AGGREGATES = "extracting_aggregates"
    EXTRACTING_COMMANDS = "extracting_commands"
    EXTRACTING_EVENTS = "extracting_events"
    EXTRACTING_POLICIES = "extracting_policies"
    IDENTIFYING_BC = "identifying_bc"
    SAVING = "saving"
    COMPLETE = "complete"
    ERROR = "error"


class ProgressEvent(BaseModel):
    """Progress event sent via SSE."""
    phase: LegacyAnalysisPhase
    message: str
    progress: int  # 0-100
    data: Optional[dict] = None


class TableInfo(BaseModel):
    """테이블 정보"""
    name: str
    schema_name: Optional[str] = None
    description: Optional[str] = None
    columns: list[dict] = []


class ProcedureInfo(BaseModel):
    """프로시저 정보"""
    name: str
    procedure_type: str  # PROCEDURE, FUNCTION, TRIGGER
    summary: Optional[str] = None
    reads_tables: list[str] = []
    writes_tables: list[str] = []


# =============================================================================
# Neo4j Queries for Legacy Analysis
# =============================================================================


def get_legacy_tables(client, user_id: str = None, project_name: str = None) -> list[dict]:
    """Neo4j에서 테이블 정보 조회"""
    query = """
    MATCH (t:Table)
    WHERE ($user_id IS NULL OR t.user_id = $user_id)
      AND ($project_name IS NULL OR t.project_name = $project_name)
    OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
    WITH t, collect(c {.name, .dtype, .description, .nullable}) as columns
    RETURN {
        id: elementId(t),
        name: t.name,
        schema: t.schema,
        description: t.description,
        table_type: t.table_type,
        columns: columns
    } as table_info
    ORDER BY t.schema, t.name
    """
    with client.session() as session:
        result = session.run(query, user_id=user_id, project_name=project_name)
        return [dict(record["table_info"]) for record in result]


def get_legacy_procedures(client, user_id: str = None, project_name: str = None) -> list[dict]:
    """Neo4j에서 프로시저/함수 정보 조회"""
    query = """
    MATCH (p)
    WHERE (p:PROCEDURE OR p:FUNCTION OR p:TRIGGER)
      AND ($user_id IS NULL OR p.user_id = $user_id)
      AND ($project_name IS NULL OR p.project_name = $project_name)
    OPTIONAL MATCH (p)-[:FROM]->(rt:Table)
    OPTIONAL MATCH (p)-[:WRITES]->(wt:Table)
    WITH p, 
         collect(DISTINCT rt.name) as reads_tables,
         collect(DISTINCT wt.name) as writes_tables
    RETURN {
        id: elementId(p),
        name: COALESCE(p.procedure_name, p.function_name, p.trigger_name, p.name),
        type: labels(p)[0],
        summary: p.summary,
        file_name: p.file_name,
        reads_tables: reads_tables,
        writes_tables: writes_tables
    } as proc_info
    ORDER BY proc_info.name
    """
    with client.session() as session:
        result = session.run(query, user_id=user_id, project_name=project_name)
        return [dict(record["proc_info"]) for record in result]


def get_table_relationships(client, user_id: str = None, project_name: str = None) -> list[dict]:
    """테이블 간 FK 관계 조회"""
    query = """
    MATCH (t1:Table)-[r:FK_TO_TABLE]->(t2:Table)
    WHERE ($user_id IS NULL OR t1.user_id = $user_id)
      AND ($project_name IS NULL OR t1.project_name = $project_name)
    RETURN {
        from_table: t1.name,
        from_schema: t1.schema,
        to_table: t2.name,
        to_schema: t2.schema,
        fk_column: r.column_name
    } as relationship
    """
    with client.session() as session:
        result = session.run(query, user_id=user_id, project_name=project_name)
        return [dict(record["relationship"]) for record in result]


def get_procedure_calls(client, user_id: str = None, project_name: str = None) -> list[dict]:
    """프로시저 간 호출 관계(CALL) 조회"""
    query = """
    MATCH (p1)-[r:CALL]->(p2)
    WHERE (p1:PROCEDURE OR p1:FUNCTION OR p1:TRIGGER)
      AND (p2:PROCEDURE OR p2:FUNCTION)
      AND ($user_id IS NULL OR p1.user_id = $user_id)
      AND ($project_name IS NULL OR p1.project_name = $project_name)
    RETURN {
        caller: COALESCE(p1.procedure_name, p1.function_name, p1.trigger_name, p1.name),
        caller_type: labels(p1)[0],
        callee: COALESCE(p2.procedure_name, p2.function_name, p2.name),
        callee_type: labels(p2)[0]
    } as call_info
    """
    with client.session() as session:
        result = session.run(query, user_id=user_id, project_name=project_name)
        return [dict(record["call_info"]) for record in result]


def get_procedure_table_access(client, user_id: str = None, project_name: str = None) -> list[dict]:
    """프로시저의 테이블 읽기/쓰기 관계 조회"""
    query = """
    MATCH (p)-[r]->(t:Table)
    WHERE (p:PROCEDURE OR p:FUNCTION OR p:TRIGGER)
      AND type(r) IN ['FROM', 'WRITES']
      AND ($user_id IS NULL OR p.user_id = $user_id)
      AND ($project_name IS NULL OR p.project_name = $project_name)
    RETURN {
        procedure: COALESCE(p.procedure_name, p.function_name, p.trigger_name, p.name),
        procedure_type: labels(p)[0],
        table_name: t.name,
        access_type: type(r)
    } as access_info
    """
    with client.session() as session:
        result = session.run(query, user_id=user_id, project_name=project_name)
        return [dict(record["access_info"]) for record in result]


# =============================================================================
# LLM-based Event Storming Extraction
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


# Prompt Templates
ANALYZE_LEGACY_SYSTEM_PROMPT = """당신은 레거시 시스템을 분석하여 Event Storming 모델을 도출하는 DDD(Domain-Driven Design) 전문가입니다.

분석 대상 시스템 정보:
{system_info}

위 레거시 시스템 정보를 분석하여 다음을 도출하세요:

1. **Bounded Context 식별**: 테이블 그룹핑과 프로시저의 책임 영역을 기반으로 BC를 식별
2. **Aggregate 도출**: 각 BC 내에서 핵심 비즈니스 엔티티(테이블)를 기반으로 Aggregate 도출
3. **Command 도출**: 프로시저/함수가 수행하는 쓰기 작업을 기반으로 Command 도출
4. **Event 도출**: Command 실행 결과로 발생하는 도메인 이벤트 도출
5. **Policy 도출**: 프로시저 간 호출 관계와 트리거를 기반으로 Policy 도출

도출 규칙:
- Aggregate는 테이블 이름을 PascalCase로 변환 (예: ORDER_ITEMS → OrderItem)
- Command는 동사형으로 (예: CreateOrder, UpdateCustomer)
- Event는 과거형으로 (예: OrderCreated, CustomerUpdated)
- BC는 관련 테이블/프로시저를 그룹핑하여 명명
"""


class BoundedContextCandidate(BaseModel):
    """BC 후보"""
    id: str
    name: str
    description: str
    table_names: list[str] = []
    procedure_names: list[str] = []


class AggregateCandidate(BaseModel):
    """Aggregate 후보"""
    id: str
    name: str
    root_entity: str
    description: str
    source_table: str
    bc_id: str


class CommandCandidate(BaseModel):
    """Command 후보"""
    id: str
    name: str
    actor: str
    description: str
    aggregate_id: str
    source_procedure: Optional[str] = None


class EventCandidate(BaseModel):
    """Event 후보"""
    id: str
    name: str
    description: str
    command_id: str


class PolicyCandidate(BaseModel):
    """Policy 후보"""
    id: str
    name: str
    description: str
    trigger_event: str
    invoke_command: str
    bc_id: str


class LegacyAnalysisResult(BaseModel):
    """레거시 분석 결과"""
    bounded_contexts: list[BoundedContextCandidate] = []
    aggregates: list[AggregateCandidate] = []
    commands: list[CommandCandidate] = []
    events: list[EventCandidate] = []
    policies: list[PolicyCandidate] = []


def build_system_info(
    tables: list[dict], 
    procedures: list[dict], 
    relationships: list[dict],
    procedure_calls: list[dict] = None,
    table_access: list[dict] = None
) -> str:
    """시스템 정보를 텍스트로 구성 (프로시저 summary 전체 포함)"""
    lines = []
    
    # 테이블 정보
    lines.append("## 테이블 목록")
    for t in tables:
        schema = t.get("schema", "")
        name = t.get("name", "")
        desc = t.get("description", "")
        full_name = f"{schema}.{name}" if schema else name
        lines.append(f"- {full_name}: {desc}")
        
        columns = t.get("columns", [])
        if columns:
            col_names = [c.get("name", "") for c in columns[:10]]  # 최대 10개
            lines.append(f"  컬럼: {', '.join(col_names)}")
    
    lines.append("")
    
    # 테이블 관계
    lines.append("## 테이블 관계 (FK)")
    for r in relationships:
        from_t = r.get("from_table", "")
        to_t = r.get("to_table", "")
        fk_col = r.get("fk_column", "")
        lines.append(f"- {from_t} → {to_t} ({fk_col})")
    
    lines.append("")
    
    # 프로시저 호출 관계 (시나리오 흐름 파악용)
    if procedure_calls:
        lines.append("## 프로시저 호출 관계 (시나리오 흐름)")
        for call in procedure_calls:
            caller = call.get("caller", "")
            callee = call.get("callee", "")
            caller_type = call.get("caller_type", "")
            lines.append(f"- [{caller_type}] {caller} → {callee}")
        lines.append("")
    
    # 프로시저 정보 (summary 전체 포함)
    lines.append("## 프로시저/함수 상세 정보")
    for p in procedures:
        name = p.get("name", "")
        ptype = p.get("type", "PROCEDURE")
        summary = p.get("summary", "") or ""
        reads = p.get("reads_tables", [])
        writes = p.get("writes_tables", [])
        
        lines.append(f"\n### [{ptype}] {name}")
        if summary:
            # summary 전체를 포함 (최대 2000자까지)
            summary_text = summary[:2000] if len(summary) > 2000 else summary
            lines.append(f"**설명**: {summary_text}")
        if reads:
            lines.append(f"**읽기 테이블**: {', '.join(reads)}")
        if writes:
            lines.append(f"**쓰기 테이블**: {', '.join(writes)}")
    
    return "\n".join(lines)


def build_procedure_detail_for_llm(procedure: dict) -> str:
    """개별 프로시저의 상세 분석용 텍스트"""
    lines = []
    name = procedure.get("name", "")
    ptype = procedure.get("type", "PROCEDURE")
    summary = procedure.get("summary", "") or ""
    reads = procedure.get("reads_tables", [])
    writes = procedure.get("writes_tables", [])
    
    lines.append(f"프로시저 이름: {name}")
    lines.append(f"타입: {ptype}")
    
    if summary:
        lines.append(f"\n상세 설명:\n{summary}")
    
    if reads:
        lines.append(f"\n읽기 테이블: {', '.join(reads)}")
    if writes:
        lines.append(f"\n쓰기 테이블: {', '.join(writes)}")
    
    return "\n".join(lines)


class ProcedureAnalysisResult(BaseModel):
    """프로시저 분석 결과 - LLM이 반환"""
    commands: list[dict] = []  # {"name": str, "description": str, "actor": str}
    events: list[dict] = []  # {"name": str, "description": str, "trigger_command": str}
    policies: list[dict] = []  # {"name": str, "description": str, "when": str, "then": str}
    business_rules: list[str] = []  # 비즈니스 규칙 목록


async def analyze_procedure_with_llm(procedure: dict, llm, aggregates: list[AggregateCandidate]) -> ProcedureAnalysisResult:
    """개별 프로시저를 LLM으로 분석하여 Command, Event, Policy 추출"""
    from langchain_core.messages import HumanMessage, SystemMessage
    
    summary = procedure.get("summary", "")
    if not summary:
        return ProcedureAnalysisResult()
    
    proc_name = procedure.get("name", "")
    reads = procedure.get("reads_tables", [])
    writes = procedure.get("writes_tables", [])
    
    agg_names = [a.name for a in aggregates]
    
    prompt = f"""다음 스토어드 프로시저의 상세 설명을 분석하여 Event Storming 요소를 도출하세요.

## 프로시저 정보
- 이름: {proc_name}
- 타입: {procedure.get("type", "PROCEDURE")}
- 읽기 테이블: {', '.join(reads) if reads else '없음'}
- 쓰기 테이블: {', '.join(writes) if writes else '없음'}

## 프로시저 상세 설명
{summary}

## 관련 Aggregate
{', '.join(agg_names)}

## 도출 규칙
1. **Command**: 프로시저가 수행하는 핵심 비즈니스 작업을 동사형으로 (예: CalculateDailySupply, UpdateTagData)
   - 프로시저 설명에서 "~를 수행한다", "~를 처리한다", "~를 갱신한다" 등의 표현에서 도출
   - INSERT, UPDATE, MERGE 등의 쓰기 작업에서 도출

2. **Event**: Command 실행 결과로 발생하는 도메인 이벤트를 과거형으로 (예: DailySupplyCalculated, TagDataUpdated)
   - 각 Command에 대해 최소 1개의 Event 도출
   - 조건부 분기가 있다면 각 분기에 대한 Event 도출

3. **Policy**: 특정 조건/이벤트가 발생했을 때 자동으로 실행되는 규칙
   - "~일 때 ~한다", "~인 경우 ~를 수행" 형태로 도출
   - 다른 프로시저를 호출하거나 후속 작업이 있는 경우 Policy로 도출
   - WHEN: 트리거 조건, THEN: 실행할 작업

4. **Business Rules**: 프로시저에 포함된 핵심 비즈니스 규칙
   - 임계값, 검증 조건, 계산 공식 등

Korean description은 그대로 유지하세요.
"""

    structured_llm = llm.with_structured_output(ProcedureAnalysisResult)
    try:
        result = structured_llm.invoke([
            SystemMessage(content="당신은 레거시 시스템의 스토어드 프로시저를 분석하여 DDD/Event Storming 요소를 도출하는 전문가입니다. 프로시저의 비즈니스 로직을 정확히 분석하여 의미있는 도메인 모델 요소를 추출합니다."),
            HumanMessage(content=prompt)
        ])
        return result
    except Exception as e:
        print(f"프로시저 분석 오류 ({proc_name}): {e}")
        return ProcedureAnalysisResult()


async def extract_event_storming_from_legacy(
    tables: list[dict],
    procedures: list[dict],
    relationships: list[dict],
    procedure_calls: list[dict] = None,
    progress_callback = None,
) -> LegacyAnalysisResult:
    """레거시 시스템 정보에서 Event Storming 요소 추출 (개선된 버전)"""
    from langchain_core.messages import HumanMessage, SystemMessage
    
    llm = get_llm()
    
    system_info = build_system_info(tables, procedures, relationships, procedure_calls)
    
    # Step 1: BC 식별
    bc_prompt = f"""다음 레거시 시스템을 분석하여 Bounded Context를 식별하세요.

{system_info}

규칙:
1. 관련 테이블과 프로시저를 그룹핑하여 BC 식별
2. BC 이름은 비즈니스 도메인을 반영 (예: DataCollection, DataAggregation, TagManagement, WaterSupply)
3. 각 BC에 속하는 테이블과 프로시저 목록 제공
4. 프로시저 호출 관계를 고려하여 연관된 프로시저들은 같은 BC로 그룹핑

JSON 형식으로 응답:
"""

    class BCList(BaseModel):
        bounded_contexts: list[BoundedContextCandidate]

    structured_llm = llm.with_structured_output(BCList)
    bc_response = structured_llm.invoke([
        SystemMessage(content="당신은 DDD 전문가입니다. 레거시 시스템을 분석하여 Bounded Context를 식별합니다."),
        HumanMessage(content=bc_prompt)
    ])
    
    bounded_contexts = bc_response.bounded_contexts
    
    # Step 2: Aggregate 도출 (테이블 기반)
    aggregates = []
    for bc in bounded_contexts:
        for table_name in bc.table_names:
            # 테이블 이름을 Aggregate 이름으로 변환
            agg_name = "".join(word.capitalize() for word in table_name.replace("_", " ").split())
            agg_id = f"AGG-{bc.id.replace('BC-', '')}-{agg_name.upper()}"
            
            # 테이블 설명 찾기
            table_info = next((t for t in tables if t.get("name") == table_name), None)
            table_desc = table_info.get("description", "") if table_info else ""
            
            aggregates.append(AggregateCandidate(
                id=agg_id,
                name=agg_name,
                root_entity=agg_name,
                description=table_desc if table_desc else f"테이블 {table_name}에서 도출된 Aggregate",
                source_table=table_name,
                bc_id=bc.id
            ))
    
    # Step 3: 프로시저별 상세 분석으로 Command/Event/Policy 도출
    commands = []
    events = []
    policies = []
    
    # summary가 있는 프로시저만 분석
    procs_with_summary = [p for p in procedures if p.get("summary")]
    
    for i, proc in enumerate(procs_with_summary):
        proc_name = proc.get("name", "")
        
        if progress_callback:
            await progress_callback(f"프로시저 분석 중: {proc_name} ({i+1}/{len(procs_with_summary)})")
        
        # LLM으로 상세 분석
        analysis = await analyze_procedure_with_llm(proc, llm, aggregates)
        
        # 프로시저가 속한 BC 찾기
        proc_bc = None
        for bc in bounded_contexts:
            if proc_name in bc.procedure_names:
                proc_bc = bc
                break
        
        if not proc_bc and bounded_contexts:
            proc_bc = bounded_contexts[0]  # 기본 BC
        
        bc_prefix = proc_bc.id.replace("BC-", "") if proc_bc else "DEFAULT"
        
        # 분석된 Command 추가
        for cmd_data in analysis.commands:
            cmd_name = cmd_data.get("name", _derive_command_name(proc_name))
            cmd_id = f"CMD-{bc_prefix}-{cmd_name.upper().replace(' ', '')}"
            
            # 쓰기 테이블에서 Aggregate 찾기
            writes = proc.get("writes_tables", [])
            agg_id = ""
            for table in writes:
                matching_agg = next(
                    (a for a in aggregates if a.source_table == table),
                    None
                )
                if matching_agg:
                    agg_id = matching_agg.id
                    break
            
            if not agg_id and aggregates:
                agg_id = aggregates[0].id
            
            commands.append(CommandCandidate(
                id=cmd_id,
                name=cmd_name,
                actor=cmd_data.get("actor", "system"),
                description=cmd_data.get("description", f"프로시저 {proc_name}에서 도출"),
                aggregate_id=agg_id,
                source_procedure=proc_name
            ))
        
        # 분석된 Event 추가
        for evt_data in analysis.events:
            evt_name = evt_data.get("name", "")
            if not evt_name:
                continue
            evt_id = f"EVT-{bc_prefix}-{evt_name.upper().replace(' ', '')}"
            
            # 관련 Command 찾기
            trigger_cmd = evt_data.get("trigger_command", "")
            related_cmd = next(
                (c for c in commands if trigger_cmd and trigger_cmd.lower() in c.name.lower()),
                commands[-1] if commands else None
            )
            cmd_id = related_cmd.id if related_cmd else ""
            
            events.append(EventCandidate(
                id=evt_id,
                name=evt_name,
                description=evt_data.get("description", f"프로시저 {proc_name}에서 도출"),
                command_id=cmd_id
            ))
        
        # 분석된 Policy 추가
        for pol_data in analysis.policies:
            pol_name = pol_data.get("name", "")
            if not pol_name:
                continue
            pol_id = f"POL-{bc_prefix}-{pol_name.upper().replace(' ', '')}"
            
            policies.append(PolicyCandidate(
                id=pol_id,
                name=pol_name,
                description=pol_data.get("description", ""),
                trigger_event=pol_data.get("when", ""),
                invoke_command=pol_data.get("then", ""),
                bc_id=proc_bc.id if proc_bc else ""
            ))
        
        # 짧은 대기 (API 속도 제한 대응)
        await asyncio.sleep(0.5)
    
    # Step 4: 프로시저 호출 관계에서 추가 Policy 도출
    if procedure_calls:
        for call in procedure_calls:
            caller = call.get("caller", "")
            callee = call.get("callee", "")
            caller_type = call.get("caller_type", "")
            
            # 트리거가 다른 프로시저를 호출하는 경우 Policy로
            if caller_type == "TRIGGER":
                pol_id = f"POL-TRIGGER-{caller.upper()}"
                pol_name = f"When{_derive_command_name(caller)}Then{_derive_command_name(callee)}"
                
                policies.append(PolicyCandidate(
                    id=pol_id,
                    name=pol_name,
                    description=f"트리거 {caller}가 {callee}를 호출",
                    trigger_event=caller,
                    invoke_command=callee,
                    bc_id=bounded_contexts[0].id if bounded_contexts else ""
                ))
    
    return LegacyAnalysisResult(
        bounded_contexts=bounded_contexts,
        aggregates=aggregates,
        commands=commands,
        events=events,
        policies=policies
    )


def _derive_command_name(proc_name: str) -> str:
    """프로시저 이름에서 Command 이름 도출"""
    # 일반적인 접두사 제거
    name = proc_name.upper()
    for prefix in ["SP_", "PROC_", "PKG_", "P_"]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    
    # 단어 분리 및 PascalCase 변환
    words = name.replace("_", " ").split()
    return "".join(word.capitalize() for word in words)


def _derive_event_name(cmd_name: str) -> str:
    """Command 이름에서 Event 이름 도출 (과거형)"""
    # 동사 → 과거형 변환 규칙
    if cmd_name.endswith("e"):
        return cmd_name + "d"
    elif cmd_name.endswith("y"):
        return cmd_name[:-1] + "ied"
    else:
        return cmd_name + "ed"


# =============================================================================
# Streaming Workflow
# =============================================================================


@dataclass
class LegacyAnalysisSession:
    """레거시 분석 세션"""
    id: str
    user_id: Optional[str] = None
    project_name: Optional[str] = None
    status: LegacyAnalysisPhase = LegacyAnalysisPhase.LOADING
    progress: int = 0
    events: list[dict] = field(default_factory=list)
    result: Optional[LegacyAnalysisResult] = None
    error: Optional[str] = None


_sessions: dict[str, LegacyAnalysisSession] = {}


async def run_legacy_analysis_workflow(
    session: LegacyAnalysisSession,
) -> AsyncGenerator[ProgressEvent, None]:
    """레거시 분석 워크플로우 실행 (개선된 버전 - 프로시저 summary 상세 분석)"""
    client = get_neo4j_client()
    
    # 진행 메시지를 위한 큐
    progress_messages = []
    
    async def progress_callback(message: str):
        progress_messages.append(message)
    
    try:
        # Phase 1: 테이블 정보 로드
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.LOADING,
            message="Neo4j에서 테이블 정보 조회 중...",
            progress=5
        )
        
        tables = get_legacy_tables(client, session.user_id, session.project_name)
        
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.ANALYZING_TABLES,
            message=f"{len(tables)}개 테이블 발견",
            progress=10,
            data={"table_count": len(tables)}
        )
        await asyncio.sleep(0.2)
        
        # Phase 2: 프로시저 정보 로드
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.ANALYZING_PROCEDURES,
            message="프로시저/함수 정보 조회 중...",
            progress=15
        )
        
        procedures = get_legacy_procedures(client, session.user_id, session.project_name)
        relationships = get_table_relationships(client, session.user_id, session.project_name)
        
        # 프로시저 호출 관계 조회
        procedure_calls = get_procedure_calls(client, session.user_id, session.project_name)
        
        procs_with_summary = len([p for p in procedures if p.get("summary")])
        
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.ANALYZING_PROCEDURES,
            message=f"{len(procedures)}개 프로시저 (summary 있음: {procs_with_summary}개), {len(relationships)}개 FK관계, {len(procedure_calls)}개 호출관계",
            progress=20,
            data={
                "procedure_count": len(procedures),
                "procedures_with_summary": procs_with_summary,
                "relationship_count": len(relationships),
                "call_count": len(procedure_calls)
            }
        )
        await asyncio.sleep(0.2)
        
        # 데이터가 없으면 에러
        if not tables and not procedures:
            yield ProgressEvent(
                phase=LegacyAnalysisPhase.ERROR,
                message="분석할 레거시 시스템 데이터가 없습니다. 먼저 robo-analyzer로 분석을 실행하세요.",
                progress=0
            )
            return
        
        # Phase 3: BC 식별
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.IDENTIFYING_BC,
            message="Bounded Context 식별 중...",
            progress=25
        )
        
        # Phase 4: 프로시저 summary 상세 분석으로 Event Storming 추출
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.ANALYZING_PROCEDURES,
            message=f"🔍 프로시저 summary 상세 분석 시작 ({procs_with_summary}개)...",
            progress=30
        )
        
        result = await extract_event_storming_from_legacy(
            tables, procedures, relationships, procedure_calls, progress_callback
        )
        session.result = result
        
        # BC 생성 알림
        for bc in result.bounded_contexts:
            yield ProgressEvent(
                phase=LegacyAnalysisPhase.IDENTIFYING_BC,
                message=f"BC 식별: {bc.name}",
                progress=45,
                data={"type": "BoundedContext", "object": bc.model_dump()}
            )
            await asyncio.sleep(0.15)
        
        # Aggregate 생성
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.EXTRACTING_AGGREGATES,
            message="Aggregate 추출 중...",
            progress=50
        )
        
        for agg in result.aggregates:
            yield ProgressEvent(
                phase=LegacyAnalysisPhase.EXTRACTING_AGGREGATES,
                message=f"Aggregate: {agg.name}",
                progress=55,
                data={"type": "Aggregate", "object": agg.model_dump()}
            )
            await asyncio.sleep(0.1)
        
        # Command 생성
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.EXTRACTING_COMMANDS,
            message="Command 추출 중...",
            progress=65
        )
        
        for cmd in result.commands:
            yield ProgressEvent(
                phase=LegacyAnalysisPhase.EXTRACTING_COMMANDS,
                message=f"Command: {cmd.name}",
                progress=70,
                data={"type": "Command", "object": cmd.model_dump()}
            )
            await asyncio.sleep(0.1)
        
        # Event 생성
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.EXTRACTING_EVENTS,
            message="Event 추출 중...",
            progress=80
        )
        
        for evt in result.events:
            yield ProgressEvent(
                phase=LegacyAnalysisPhase.EXTRACTING_EVENTS,
                message=f"Event: {evt.name}",
                progress=85,
                data={"type": "Event", "object": evt.model_dump()}
            )
            await asyncio.sleep(0.1)
        
        # Phase 4: Neo4j에 저장
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.SAVING,
            message="Event Storming 모델 저장 중...",
            progress=90
        )
        
        await save_event_storming_to_neo4j(client, result)
        
        # 완료
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.COMPLETE,
            message="✅ 레거시 분석 완료!",
            progress=100,
            data={
                "summary": {
                    "bounded_contexts": len(result.bounded_contexts),
                    "aggregates": len(result.aggregates),
                    "commands": len(result.commands),
                    "events": len(result.events),
                    "policies": len(result.policies)
                }
            }
        )
        
    except Exception as e:
        yield ProgressEvent(
            phase=LegacyAnalysisPhase.ERROR,
            message=f"❌ 오류 발생: {str(e)}",
            progress=0,
            data={"error": str(e)}
        )


async def save_event_storming_to_neo4j(client, result: LegacyAnalysisResult):
    """추출된 Event Storming 모델을 Neo4j에 저장"""
    
    # BC 저장
    for bc in result.bounded_contexts:
        client.create_bounded_context(
            id=bc.id,
            name=bc.name,
            description=bc.description
        )
    
    # Aggregate 저장
    for agg in result.aggregates:
        client.create_aggregate(
            id=agg.id,
            name=agg.name,
            bc_id=agg.bc_id,
            root_entity=agg.root_entity
        )
    
    # Command 저장
    for cmd in result.commands:
        client.create_command(
            id=cmd.id,
            name=cmd.name,
            aggregate_id=cmd.aggregate_id,
            actor=cmd.actor
        )
    
    # Event 저장
    for evt in result.events:
        client.create_event(
            id=evt.id,
            name=evt.name,
            command_id=evt.command_id
        )


# =============================================================================
# PRD Document Generation from Legacy System
# =============================================================================


async def generate_prd_from_legacy(
    tables: list[dict],
    procedures: list[dict],
    relationships: list[dict],
    procedure_calls: list[dict] = None,
) -> str:
    """레거시 시스템 정보에서 PRD(요구사항 문서) 생성"""
    from langchain_core.messages import HumanMessage, SystemMessage
    
    llm = get_llm()
    
    # 프로시저 상세 정보 구성 (summary 전체 포함)
    proc_details = []
    for p in procedures:
        name = p.get("name", "")
        ptype = p.get("type", "PROCEDURE")
        summary = p.get("summary", "") or ""
        reads = p.get("reads_tables", [])
        writes = p.get("writes_tables", [])
        
        if summary:  # summary가 있는 프로시저만 상세 분석
            proc_details.append(f"""
### [{ptype}] {name}
**기능 설명**: {summary[:3000]}
**읽기 테이블**: {', '.join(reads) if reads else '없음'}
**쓰기 테이블**: {', '.join(writes) if writes else '없음'}
""")
    
    # 테이블 정보 구성
    table_info = []
    for t in tables:
        name = t.get("name", "")
        desc = t.get("description", "")
        cols = t.get("columns", [])
        col_names = [c.get("name", "") for c in cols[:10]]
        table_info.append(f"- {name}: {desc} (컬럼: {', '.join(col_names)})")
    
    # 호출 관계 구성
    call_info = []
    if procedure_calls:
        for call in procedure_calls:
            caller = call.get("caller", "")
            callee = call.get("callee", "")
            call_info.append(f"- {caller} → {callee}")
    
    prompt = f"""당신은 레거시 시스템을 분석하여 현대적인 요구사항 문서(PRD)를 작성하는 전문가입니다.

## 레거시 시스템 정보

### 테이블 목록 ({len(tables)}개)
{chr(10).join(table_info[:30])}

### 프로시저 호출 관계
{chr(10).join(call_info) if call_info else '(호출 관계 없음)'}

### 프로시저/함수 상세 정보 ({len(proc_details)}개)
{chr(10).join(proc_details[:15])}

---

## 작업 지시

위 레거시 시스템 정보를 분석하여 **요구사항 문서(PRD)**를 작성하세요.

### 문서 형식

각 프로시저의 기능을 기반으로 다음 형식의 User Story와 Acceptance Criteria를 도출하세요:

```
## [기능 도메인명]

### US-XXX: [User Story 제목]
**As a** [역할],
**I want to** [원하는 기능/액션],
**So that** [기대 효과/이점]

**Acceptance Criteria:**
1. [검증 가능한 조건 1]
2. [검증 가능한 조건 2]
3. ...

**UI 요구사항:** (있는 경우)
- [화면 구성 설명]
- [입력 필드 및 버튼]

**비즈니스 규칙:**
- [프로시저에서 파악된 규칙 1]
- [프로시저에서 파악된 규칙 2]
```

### 도출 규칙
1. 프로시저의 summary에서 핵심 비즈니스 로직을 파악하여 User Story로 변환
2. 프로시저가 수행하는 데이터 집계, 검증, 변환 등의 로직을 Acceptance Criteria로 명시
3. 비즈니스 규칙(임계값, 조건부 처리, 예외 처리 등)을 명확히 기술
4. 테이블 간 관계와 데이터 흐름을 고려하여 연관된 기능 그룹핑
5. 프로시저 호출 관계를 기반으로 업무 시나리오 흐름 파악

### 주의사항
- 기술적 구현 세부사항보다는 **비즈니스 관점**의 요구사항으로 작성
- 프로시저에서 파악된 **비즈니스 규칙**을 반드시 포함
- 한국어로 작성하되, 도메인 용어는 원본 유지 가능

요구사항 문서를 작성하세요:
"""

    response = llm.invoke([
        SystemMessage(content="당신은 레거시 시스템 분석 및 현대화 전문가입니다. 레거시 시스템의 프로시저와 테이블 구조를 분석하여 비즈니스 관점의 요구사항 문서를 작성합니다."),
        HumanMessage(content=prompt)
    ])
    
    return response.content


class PRDGenerationRequest(BaseModel):
    """PRD 생성 요청"""
    user_id: Optional[str] = None
    project_name: Optional[str] = None


class PRDGenerationResponse(BaseModel):
    """PRD 생성 응답"""
    success: bool
    prd_content: str
    source_summary: dict
    message: str


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/generate-prd")
async def generate_prd(
    user_id: Optional[str] = Query(None, description="사용자 ID"),
    project_name: Optional[str] = Query(None, description="프로젝트 이름")
) -> PRDGenerationResponse:
    """
    레거시 시스템(테이블/SP) 정보를 분석하여 PRD 문서를 생성합니다.
    
    생성된 PRD는 기존 /api/ingest/upload의 text 파라미터로 전달하여
    Event Storming을 도출할 수 있습니다.
    
    **워크플로우:**
    1. 이 API 호출 → PRD 문서 생성
    2. 생성된 PRD를 /api/ingest/upload에 text로 전달
    3. 기존 ingestion 워크플로우로 Event Storming 도출
    """
    client = get_neo4j_client()
    
    try:
        # 레거시 데이터 조회
        tables = get_legacy_tables(client, user_id, project_name)
        procedures = get_legacy_procedures(client, user_id, project_name)
        relationships = get_table_relationships(client, user_id, project_name)
        procedure_calls = get_procedure_calls(client, user_id, project_name)
        
        if not tables and not procedures:
            return PRDGenerationResponse(
                success=False,
                prd_content="",
                source_summary={
                    "tables": 0,
                    "procedures": 0,
                    "procedures_with_summary": 0,
                    "relationships": 0
                },
                message="분석할 레거시 시스템 데이터가 없습니다. 먼저 robo-analyzer로 분석을 실행하세요."
            )
        
        procs_with_summary = len([p for p in procedures if p.get("summary")])
        
        # PRD 생성
        prd_content = await generate_prd_from_legacy(
            tables, procedures, relationships, procedure_calls
        )
        
        return PRDGenerationResponse(
            success=True,
            prd_content=prd_content,
            source_summary={
                "tables": len(tables),
                "procedures": len(procedures),
                "procedures_with_summary": procs_with_summary,
                "relationships": len(relationships),
                "procedure_calls": len(procedure_calls) if procedure_calls else 0
            },
            message=f"PRD 문서가 생성되었습니다. ({len(tables)}개 테이블, {procs_with_summary}개 프로시저 summary 분석)"
        )
        
    except Exception as e:
        return PRDGenerationResponse(
            success=False,
            prd_content="",
            source_summary={},
            message=f"PRD 생성 오류: {str(e)}"
        )


@router.get("/tables")
async def get_tables(
    user_id: Optional[str] = Query(None, description="사용자 ID"),
    project_name: Optional[str] = Query(None, description="프로젝트 이름")
) -> list[dict]:
    """
    Neo4j에서 테이블 정보 조회
    robo-analyzer에서 분석한 테이블 목록을 반환합니다.
    """
    client = get_neo4j_client()
    return get_legacy_tables(client, user_id, project_name)


@router.get("/procedures")
async def get_procedures(
    user_id: Optional[str] = Query(None, description="사용자 ID"),
    project_name: Optional[str] = Query(None, description="프로젝트 이름")
) -> list[dict]:
    """
    Neo4j에서 프로시저/함수 정보 조회
    robo-analyzer에서 분석한 스토어드 프로시저 목록을 반환합니다.
    """
    client = get_neo4j_client()
    return get_legacy_procedures(client, user_id, project_name)


@router.get("/relationships")
async def get_relationships(
    user_id: Optional[str] = Query(None, description="사용자 ID"),
    project_name: Optional[str] = Query(None, description="프로젝트 이름")
) -> list[dict]:
    """
    Neo4j에서 테이블 관계(FK) 조회
    """
    client = get_neo4j_client()
    return get_table_relationships(client, user_id, project_name)


@router.get("/summary")
async def get_legacy_summary(
    user_id: Optional[str] = Query(None, description="사용자 ID"),
    project_name: Optional[str] = Query(None, description="프로젝트 이름")
) -> dict:
    """
    레거시 시스템 요약 정보 조회
    테이블, 프로시저, 관계 수 등의 통계를 반환합니다.
    """
    client = get_neo4j_client()
    
    tables = get_legacy_tables(client, user_id, project_name)
    procedures = get_legacy_procedures(client, user_id, project_name)
    relationships = get_table_relationships(client, user_id, project_name)
    
    # 테이블 타입별 분류
    table_types = {}
    for t in tables:
        ttype = t.get("table_type", "UNKNOWN")
        table_types[ttype] = table_types.get(ttype, 0) + 1
    
    # 프로시저 타입별 분류
    proc_types = {}
    for p in procedures:
        ptype = p.get("type", "UNKNOWN")
        proc_types[ptype] = proc_types.get(ptype, 0) + 1
    
    return {
        "hasLegacyData": len(tables) > 0 or len(procedures) > 0,
        "tables": {
            "total": len(tables),
            "byType": table_types
        },
        "procedures": {
            "total": len(procedures),
            "byType": proc_types
        },
        "relationships": len(relationships)
    }


@router.post("/analyze")
async def start_legacy_analysis(
    user_id: Optional[str] = Query(None, description="사용자 ID"),
    project_name: Optional[str] = Query(None, description="프로젝트 이름")
) -> dict:
    """
    레거시 시스템 분석 시작
    테이블/SP 정보를 기반으로 Event Storming 모델을 자동 추출합니다.
    
    반환된 session_id로 /stream/{session_id}에 연결하여 진행상황을 스트리밍 받습니다.
    """
    session_id = str(uuid.uuid4())[:8]
    session = LegacyAnalysisSession(
        id=session_id,
        user_id=user_id,
        project_name=project_name
    )
    _sessions[session_id] = session
    
    return {
        "session_id": session_id,
        "message": "분석 시작. SSE 스트림에 연결하세요.",
        "stream_url": f"/api/legacy/stream/{session_id}"
    }


@router.get("/stream/{session_id}")
async def stream_analysis(session_id: str):
    """
    SSE 스트림으로 분석 진행상황 수신
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    async def event_generator():
        async for event in run_legacy_analysis_workflow(session):
            event_dict = event.model_dump()
            session.events.append(event_dict)
            yield {
                "event": "progress",
                "data": json.dumps(event_dict)
            }
    
    return EventSourceResponse(event_generator())


@router.get("/session/{session_id}/result")
async def get_session_result(session_id: str) -> dict:
    """
    분석 세션 결과 조회
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "status": session.status.value,
        "progress": session.progress,
        "result": session.result.model_dump() if session.result else None,
        "error": session.error
    }

