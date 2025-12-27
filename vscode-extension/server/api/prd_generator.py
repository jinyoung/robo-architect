"""
PRD Generator API

Generates PRD (Product Requirements Document) and .claude folder structure
for vibe coding with Claude Code and Cursor.

Supports:
- Multiple tech stacks (Spring Boot, Node.js, Python FastAPI, Go)
- Messaging platforms (Kafka, RabbitMQ, In-memory for monolith)
- Per-microservice separated specs for agent context isolation
- Zip file download
"""

from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime
from enum import Enum
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

load_dotenv()

# Neo4j Configuration (independent to avoid circular import)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345msaez")

_driver = None

def get_driver():
    """Get or create Neo4j driver."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver

def get_session():
    """Get a Neo4j session."""
    return get_driver().session()

router = APIRouter(prefix="/api/prd", tags=["PRD Generator"])


# =============================================================================
# Enums and Models
# =============================================================================

class Language(str, Enum):
    JAVA = "java"
    KOTLIN = "kotlin"
    TYPESCRIPT = "typescript"
    PYTHON = "python"
    GO = "go"


class Framework(str, Enum):
    SPRING_BOOT = "spring-boot"
    SPRING_WEBFLUX = "spring-webflux"
    NESTJS = "nestjs"
    EXPRESS = "express"
    FASTAPI = "fastapi"
    GIN = "gin"
    FIBER = "fiber"


class MessagingPlatform(str, Enum):
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS_STREAMS = "redis-streams"
    PULSAR = "pulsar"
    IN_MEMORY = "in-memory"  # For monolith - uses internal event bus


class DeploymentStyle(str, Enum):
    MICROSERVICES = "microservices"
    MODULAR_MONOLITH = "modular-monolith"


class Database(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    H2 = "h2"  # For development


class TechStackConfig(BaseModel):
    language: Language = Language.JAVA
    framework: Framework = Framework.SPRING_BOOT
    messaging: MessagingPlatform = MessagingPlatform.KAFKA
    deployment: DeploymentStyle = DeploymentStyle.MICROSERVICES
    database: Database = Database.POSTGRESQL
    project_name: str = Field(default="my-project", description="Project name for the generated code")
    package_name: str = Field(default="com.example", description="Base package name (for Java/Kotlin)")
    include_docker: bool = True
    include_kubernetes: bool = False
    include_tests: bool = True


class PRDGenerationRequest(BaseModel):
    node_ids: list[str] = Field(..., description="List of node IDs from canvas")
    tech_stack: TechStackConfig = Field(default_factory=TechStackConfig)


# =============================================================================
# Template Generators
# =============================================================================

def get_framework_details(config: TechStackConfig) -> dict:
    """Get framework-specific implementation details."""
    
    details = {
        Framework.SPRING_BOOT: {
            "event_bus": {
                MessagingPlatform.KAFKA: "Spring Kafka with @KafkaListener",
                MessagingPlatform.RABBITMQ: "Spring AMQP with @RabbitListener",
                MessagingPlatform.IN_MEMORY: "AbstractAggregateRoot + ApplicationEventPublisher",
            },
            "project_structure": """
src/
├── main/
│   ├── java/{{package}}/
│   │   ├── {{bc_name}}/
│   │   │   ├── aggregate/
│   │   │   ├── command/
│   │   │   ├── event/
│   │   │   ├── policy/
│   │   │   └── repository/
│   │   └── infra/
│   └── resources/
│       └── application.yml
└── test/
""",
            "dependencies": ["spring-boot-starter-web", "spring-boot-starter-data-jpa", "lombok"],
        },
        Framework.NESTJS: {
            "event_bus": {
                MessagingPlatform.KAFKA: "@nestjs/microservices with Kafka transport",
                MessagingPlatform.RABBITMQ: "@nestjs/microservices with RabbitMQ transport",
                MessagingPlatform.IN_MEMORY: "CQRS module with EventBus",
            },
            "project_structure": """
src/
├── {{bc_name}}/
│   ├── aggregates/
│   ├── commands/
│   ├── events/
│   ├── policies/
│   ├── {{bc_name}}.module.ts
│   └── {{bc_name}}.controller.ts
├── shared/
│   └── events/
└── main.ts
""",
            "dependencies": ["@nestjs/common", "@nestjs/cqrs", "@nestjs/microservices"],
        },
        Framework.FASTAPI: {
            "event_bus": {
                MessagingPlatform.KAFKA: "aiokafka with async consumers",
                MessagingPlatform.RABBITMQ: "aio-pika with async consumers",
                MessagingPlatform.IN_MEMORY: "Python asyncio Queue / blinker signals",
            },
            "project_structure": """
src/
├── {{bc_name}}/
│   ├── domain/
│   │   ├── aggregates.py
│   │   ├── commands.py
│   │   ├── events.py
│   │   └── policies.py
│   ├── api/
│   │   └── routes.py
│   └── repository.py
├── shared/
│   └── event_bus.py
└── main.py
""",
            "dependencies": ["fastapi", "uvicorn", "pydantic", "sqlalchemy"],
        },
    }
    
    return details.get(config.framework, details[Framework.SPRING_BOOT])


def generate_bc_spec(bc_data: dict, config: TechStackConfig) -> str:
    """Generate a detailed specification for a single Bounded Context."""
    
    bc_name = bc_data.get("name", "Unknown")
    bc_id = bc_data.get("id", "")
    aggregates = bc_data.get("aggregates", [])
    policies = bc_data.get("policies", [])
    
    framework_details = get_framework_details(config)
    event_mechanism = framework_details["event_bus"].get(
        config.messaging, 
        "Event-driven messaging"
    )
    
    spec = f"""# {bc_name} Bounded Context Specification

## Overview
- **BC ID**: {bc_id}
- **Description**: {bc_data.get("description", "No description provided")}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value} ({event_mechanism})

## Domain Model

"""
    
    # Aggregates section
    if aggregates:
        spec += "### Aggregates\n\n"
        for agg in aggregates:
            spec += f"#### {agg.get('name', 'Unknown')}\n"
            spec += f"- **ID**: `{agg.get('id', '')}`\n"
            if agg.get('rootEntity'):
                spec += f"- **Root Entity**: `{agg['rootEntity']}`\n"
            
            # Commands
            commands = agg.get("commands", [])
            if commands:
                spec += "\n**Commands:**\n"
                for cmd in commands:
                    spec += f"- `{cmd.get('name', 'Unknown')}`: {cmd.get('actor', 'User')} action\n"
            
            # Events
            events = agg.get("events", [])
            if events:
                spec += "\n**Events Emitted:**\n"
                for evt in events:
                    spec += f"- `{evt.get('name', 'Unknown')}` (v{evt.get('version', '1')})\n"
            
            spec += "\n"
    
    # Policies section
    if policies:
        spec += "### Policies (Event Handlers)\n\n"
        for pol in policies:
            spec += f"#### {pol.get('name', 'Unknown')}\n"
            spec += f"- **ID**: `{pol.get('id', '')}`\n"
            if pol.get('triggerEventId'):
                spec += f"- **Triggered by Event**: `{pol['triggerEventId']}`\n"
            if pol.get('invokeCommandId'):
                spec += f"- **Invokes Command**: `{pol['invokeCommandId']}`\n"
            spec += f"- **Description**: {pol.get('description', 'No description')}\n\n"
    
    # Implementation guidance
    spec += f"""
## Implementation Guidance

### Project Structure
```
{framework_details["project_structure"].replace("{{bc_name}}", bc_name.lower().replace(" ", "_")).replace("{{package}}", config.package_name.replace(".", "/"))}
```

### Event Handling
- **Mechanism**: {event_mechanism}
"""
    
    if config.messaging == MessagingPlatform.IN_MEMORY:
        if config.framework == Framework.SPRING_BOOT:
            spec += """
- Use `AbstractAggregateRoot` for domain events
- Register domain events with `registerDomainEvent()`
- Events are published after `@Transactional` commit
- Use `@TransactionalEventListener` for policies

```java
@Entity
public class OrderAggregate extends AbstractAggregateRoot<OrderAggregate> {
    
    public void placeOrder(PlaceOrderCommand cmd) {
        // business logic
        registerDomainEvent(new OrderPlacedEvent(this.id, cmd.items()));
    }
}
```
"""
        elif config.framework == Framework.NESTJS:
            spec += """
- Use NestJS CQRS module's `EventBus`
- Aggregate extends `AggregateRoot`
- Events published via `this.apply(new Event())`

```typescript
@Injectable()
export class OrderAggregate extends AggregateRoot {
    placeOrder(cmd: PlaceOrderCommand) {
        // business logic
        this.apply(new OrderPlacedEvent(this.id, cmd.items));
    }
}
```
"""
    else:
        spec += f"""
- Topic/Queue naming: `{bc_name.lower().replace(" ", "-")}.events`
- Use JSON serialization for events
- Include event metadata (timestamp, correlation ID, causation ID)
"""
    
    return spec


def generate_main_prd(bcs: list[dict], config: TechStackConfig) -> str:
    """Generate the main PRD document."""
    
    project_name = config.project_name
    
    prd = f"""# {project_name} - Product Requirements Document

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Project Overview

This document describes an event-driven {"microservices" if config.deployment == DeploymentStyle.MICROSERVICES else "modular monolith"} architecture generated from Event Storming model.

### Technology Stack

| Component | Choice |
|-----------|--------|
| **Language** | {config.language.value} |
| **Framework** | {config.framework.value} |
| **Messaging** | {config.messaging.value} |
| **Database** | {config.database.value} |
| **Deployment** | {config.deployment.value} |

## System Architecture

"""
    
    if config.deployment == DeploymentStyle.MICROSERVICES:
        prd += """
### Microservices Architecture

Each Bounded Context is deployed as an independent microservice:

```
                    ┌─────────────────┐
                    │   API Gateway   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
"""
        for bc in bcs[:3]:  # Show first 3 for diagram
            prd += f"   [{bc.get('name', 'BC')}]"
        prd += """
        │                    │                    │
        └────────────────────┴────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Message Broker │
"""
        prd += f"                    │   ({config.messaging.value})   │\n"
        prd += """                    └─────────────────┘
```

"""
    else:
        prd += """
### Modular Monolith Architecture

All Bounded Contexts are deployed as modules within a single application:

```
┌──────────────────────────────────────────────────────────┐
│                    Application                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  Module  │  │  Module  │  │  Module  │   ...         │
│  │   (BC1)  │  │   (BC2)  │  │   (BC3)  │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       │             │             │                      │
│       └─────────────┴─────────────┘                      │
│                     │                                    │
│            ┌────────▼────────┐                          │
│            │  Internal Event │                          │
│            │      Bus        │                          │
│            └─────────────────┘                          │
└──────────────────────────────────────────────────────────┘
```

"""
    
    # Bounded Contexts Summary
    prd += "## Bounded Contexts\n\n"
    prd += "| BC Name | Aggregates | Commands | Events | Policies |\n"
    prd += "|---------|------------|----------|--------|----------|\n"
    
    for bc in bcs:
        aggs = bc.get("aggregates", [])
        cmds = sum(len(a.get("commands", [])) for a in aggs)
        evts = sum(len(a.get("events", [])) for a in aggs)
        pols = len(bc.get("policies", []))
        prd += f"| {bc.get('name', 'Unknown')} | {len(aggs)} | {cmds} | {evts} | {pols} |\n"
    
    # Event Flow
    prd += "\n## Cross-BC Event Flows\n\n"
    prd += "See individual BC specs for detailed event flows.\n\n"
    
    # Implementation Phases
    prd += """
## Implementation Phases

### Phase 1: Core Domain (Week 1-2)
- Set up project structure
- Implement Aggregates and Commands
- Set up local development environment

### Phase 2: Event Handling (Week 3)
- Implement Event publishing
- Set up message broker
- Implement Policies (event handlers)

### Phase 3: Integration (Week 4)
- Cross-BC communication testing
- API Gateway setup
- End-to-end testing

### Phase 4: Production Ready (Week 5+)
- Add monitoring and observability
- Performance optimization
- Documentation

"""
    
    return prd


def generate_claude_md(bcs: list[dict], config: TechStackConfig) -> str:
    """Generate CLAUDE.md for Claude Code context."""
    
    return f"""# CLAUDE.md - AI Assistant Context

## Project Context

This is an event-driven {"microservices" if config.deployment == DeploymentStyle.MICROSERVICES else "modular monolith"} project.

### Tech Stack
- **Language**: {config.language.value}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value}
- **Database**: {config.database.value}

### Architecture Principles

1. **Domain-Driven Design**: Each Bounded Context is a separate domain boundary
2. **Event Sourcing Ready**: All state changes emit domain events
3. **CQRS Pattern**: Commands modify state, Queries read state
4. **Eventual Consistency**: Cross-BC communication is async via events

### Key Patterns

{"#### Spring Boot + In-Memory Events" if config.framework == Framework.SPRING_BOOT and config.messaging == MessagingPlatform.IN_MEMORY else ""}
{"- Use `AbstractAggregateRoot` for domain event registration" if config.framework == Framework.SPRING_BOOT and config.messaging == MessagingPlatform.IN_MEMORY else ""}
{"- Events are auto-published after @Transactional commit" if config.framework == Framework.SPRING_BOOT and config.messaging == MessagingPlatform.IN_MEMORY else ""}
{"- Use `@TransactionalEventListener` for policies" if config.framework == Framework.SPRING_BOOT and config.messaging == MessagingPlatform.IN_MEMORY else ""}

{"#### Kafka Event Streaming" if config.messaging == MessagingPlatform.KAFKA else ""}
{"- Topic per aggregate: `<bc-name>.<aggregate-name>.events`" if config.messaging == MessagingPlatform.KAFKA else ""}
{"- Use Avro/JSON schema for events" if config.messaging == MessagingPlatform.KAFKA else ""}
{"- Consumer groups per BC for scaling" if config.messaging == MessagingPlatform.KAFKA else ""}

## Bounded Contexts

{chr(10).join([f"- **{bc.get('name')}**: See `specs/{bc.get('name').lower().replace(' ', '_')}_spec.md`" for bc in bcs])}

## Commands for Development

```bash
# Run locally
{"./mvnw spring-boot:run" if config.framework in [Framework.SPRING_BOOT, Framework.SPRING_WEBFLUX] else ""}
{"npm run start:dev" if config.framework in [Framework.NESTJS, Framework.EXPRESS] else ""}
{"uvicorn main:app --reload" if config.framework == Framework.FASTAPI else ""}
{"go run main.go" if config.framework in [Framework.GIN, Framework.FIBER] else ""}

# Run tests
{"./mvnw test" if config.framework in [Framework.SPRING_BOOT, Framework.SPRING_WEBFLUX] else ""}
{"npm test" if config.framework in [Framework.NESTJS, Framework.EXPRESS] else ""}
{"pytest" if config.framework == Framework.FASTAPI else ""}
{"go test ./..." if config.framework in [Framework.GIN, Framework.FIBER] else ""}
```

## Important Notes

1. **DO NOT** modify event schemas without versioning
2. **Always** include correlation IDs in events for tracing
3. **Test** cross-BC event flows in integration tests
4. **Document** any new events in the BC spec files
"""


def generate_agent_config(bc: dict, config: TechStackConfig) -> str:
    """Generate agent configuration for a specific BC."""
    
    bc_name = bc.get("name", "Unknown").lower().replace(" ", "_")
    
    return f"""# Agent Configuration: {bc.get('name', 'Unknown')}

## Context
This agent is responsible for the {bc.get('name', 'Unknown')} Bounded Context.

## Scope
- Only modify files in the `{bc_name}/` directory
- Respect the event contracts defined in `specs/{bc_name}_spec.md`
- Follow {config.framework.value} conventions

## Key Files
- `{bc_name}/aggregate/` - Domain aggregates
- `{bc_name}/command/` - Command handlers
- `{bc_name}/event/` - Domain events
- `{bc_name}/policy/` - Event handlers (policies)
- `{bc_name}/repository/` - Data access layer

## Constraints
1. **Event Schema**: Never modify existing event fields, only add new optional fields
2. **Commands**: Each command should emit at least one event
3. **Policies**: Must be idempotent (handle duplicate events)
4. **Database**: Use the shared database but separate tables/collections per BC

## Testing Requirements
- Unit tests for all command handlers
- Integration tests for policy handlers
- Event contract tests (schema validation)

## Related BCs
{chr(10).join([f"- {p.get('triggerEventId', 'External Event')} -> {p.get('name')}" for p in bc.get('policies', [])])}
"""


def generate_cursor_rules(config: TechStackConfig) -> str:
    """Generate .cursorrules file for Cursor IDE."""
    
    framework_rules = {
        Framework.SPRING_BOOT: """
- Use constructor injection over field injection
- Prefer records for DTOs and Events
- Use @Transactional at service layer
- Follow package-by-feature structure
""",
        Framework.NESTJS: """
- Use DTOs with class-validator decorators
- Prefer constructor injection
- Use NestJS interceptors for cross-cutting concerns
- Follow module-per-BC structure
""",
        Framework.FASTAPI: """
- Use Pydantic models for request/response
- Use dependency injection with Depends()
- Prefer async/await for I/O operations
- Follow router-per-BC structure
"""
    }
    
    return f"""# Cursor Rules for {config.project_name}

## Project Type
Event-driven {config.deployment.value} using {config.framework.value}

## Code Style
{framework_rules.get(config.framework, "")}

## DDD Patterns
- Aggregates contain business logic
- Commands are the API to aggregates
- Events are facts that happened
- Policies react to events from other BCs

## Event-Driven Rules
- Events are immutable
- Always include: eventId, timestamp, aggregateId, version
- Use past tense for event names (OrderPlaced, not PlaceOrder)
- Commands use imperative mood (PlaceOrder, not OrderPlaced)

## Messaging Rules ({config.messaging.value})
{"- Use AbstractAggregateRoot.registerDomainEvent()" if config.messaging == MessagingPlatform.IN_MEMORY and config.framework == Framework.SPRING_BOOT else ""}
{"- Topics: <bc-name>.<aggregate-name>.events" if config.messaging in [MessagingPlatform.KAFKA, MessagingPlatform.RABBITMQ] else ""}

## File Naming Conventions
- Aggregates: *Aggregate.{config.language.value.replace('typescript', 'ts').replace('javascript', 'js').replace('python', 'py')}
- Commands: *Command.{config.language.value.replace('typescript', 'ts').replace('javascript', 'js').replace('python', 'py')}
- Events: *Event.{config.language.value.replace('typescript', 'ts').replace('javascript', 'js').replace('python', 'py')}
- Policies: *Policy.{config.language.value.replace('typescript', 'ts').replace('javascript', 'js').replace('python', 'py')}
"""


# =============================================================================
# Data Fetching
# =============================================================================

async def fetch_bc_data(bc_id: str) -> dict | None:
    """Fetch full BC data from Neo4j."""
    
    query = """
    MATCH (bc:BoundedContext {id: $bc_id})
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    WITH bc, agg, 
         collect(DISTINCT {id: cmd.id, name: cmd.name, actor: cmd.actor}) as commands,
         collect(DISTINCT {id: evt.id, name: evt.name, version: evt.version}) as events
    WITH bc, collect(DISTINCT {
        id: agg.id, 
        name: agg.name, 
        rootEntity: agg.rootEntity,
        commands: commands,
        events: events
    }) as aggregates
    
    OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol:Policy)
    OPTIONAL MATCH (triggerEvt:Event)-[:TRIGGERS]->(pol)
    OPTIONAL MATCH (pol)-[:INVOKES]->(invokeCmd:Command)
    WITH bc, aggregates, collect(DISTINCT {
        id: pol.id,
        name: pol.name,
        description: pol.description,
        triggerEventId: triggerEvt.id,
        triggerEventName: triggerEvt.name,
        invokeCommandId: invokeCmd.id,
        invokeCommandName: invokeCmd.name
    }) as policies
    
    RETURN {
        id: bc.id,
        name: bc.name,
        description: bc.description,
        aggregates: [a IN aggregates WHERE a.id IS NOT NULL],
        policies: [p IN policies WHERE p.id IS NOT NULL]
    } as bc_data
    """
    
    with get_session() as session:
        result = session.run(query, bc_id=bc_id)
        record = result.single()
        if record:
            return dict(record["bc_data"])
    return None


async def get_bcs_from_nodes(node_ids: list[str]) -> list[dict]:
    """Get all BCs that contain or are the specified nodes."""
    
    query = """
    // Direct BC nodes
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext {id: nodeId})
    WITH collect(DISTINCT bc.id) as directBCs
    
    // BCs containing the nodes
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY*1..3]->(n {id: nodeId})
    WITH directBCs, collect(DISTINCT bc.id) as containingBCs
    
    // BCs for Commands (via Aggregate)
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command {id: nodeId})
    WITH directBCs, containingBCs, collect(DISTINCT bc.id) as cmdBCs
    
    // BCs for Events (via Command)
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event {id: nodeId})
    WITH directBCs, containingBCs, cmdBCs, collect(DISTINCT bc.id) as evtBCs
    
    WITH directBCs + containingBCs + cmdBCs + evtBCs as allBCIds
    UNWIND allBCIds as bcId
    WITH DISTINCT bcId WHERE bcId IS NOT NULL
    RETURN collect(bcId) as bc_ids
    """
    
    with get_session() as session:
        result = session.run(query, node_ids=node_ids)
        record = result.single()
        if record:
            bc_ids = record["bc_ids"]
            
            # Fetch full data for each BC
            bcs = []
            for bc_id in bc_ids:
                bc_data = await fetch_bc_data(bc_id)
                if bc_data:
                    bcs.append(bc_data)
            return bcs
    return []


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/tech-stacks")
async def get_available_tech_stacks():
    """Get all available technology stack options."""
    
    return {
        "languages": [{"value": l.value, "label": l.name.title()} for l in Language],
        "frameworks": [
            {"value": f.value, "label": f.value.replace("-", " ").title(), 
             "languages": _get_framework_languages(f)} 
            for f in Framework
        ],
        "messaging": [
            {"value": m.value, "label": m.value.replace("-", " ").title(),
             "description": _get_messaging_description(m)} 
            for m in MessagingPlatform
        ],
        "deployments": [{"value": d.value, "label": d.value.replace("-", " ").title()} for d in DeploymentStyle],
        "databases": [{"value": d.value, "label": d.value.title()} for d in Database],
    }


def _get_framework_languages(framework: Framework) -> list[str]:
    """Get compatible languages for a framework."""
    mapping = {
        Framework.SPRING_BOOT: ["java", "kotlin"],
        Framework.SPRING_WEBFLUX: ["java", "kotlin"],
        Framework.NESTJS: ["typescript"],
        Framework.EXPRESS: ["typescript", "javascript"],
        Framework.FASTAPI: ["python"],
        Framework.GIN: ["go"],
        Framework.FIBER: ["go"],
    }
    return mapping.get(framework, [])


def _get_messaging_description(messaging: MessagingPlatform) -> str:
    """Get description for messaging platform."""
    descriptions = {
        MessagingPlatform.KAFKA: "Distributed event streaming, best for microservices",
        MessagingPlatform.RABBITMQ: "Message broker with flexible routing",
        MessagingPlatform.REDIS_STREAMS: "Lightweight, good for simpler use cases",
        MessagingPlatform.PULSAR: "Multi-tenant, geo-replication support",
        MessagingPlatform.IN_MEMORY: "For modular monolith, uses internal event bus",
    }
    return descriptions.get(messaging, "")


@router.post("/generate")
async def generate_prd(request: PRDGenerationRequest):
    """
    Generate PRD and .claude folder structure.
    Returns a preview of what will be generated.
    """
    
    if not request.node_ids:
        raise HTTPException(status_code=400, detail="node_ids cannot be empty")
    
    # Get BC data from Neo4j
    bcs = await get_bcs_from_nodes(request.node_ids)
    
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")
    
    config = request.tech_stack
    
    # Generate preview
    files_to_generate = [
        "CLAUDE.md",
        "PRD.md",
        ".cursorrules",
    ]
    
    # Add BC-specific files
    for bc in bcs:
        bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
        files_to_generate.append(f".claude/agents/{bc_name}_agent.md")
        files_to_generate.append(f"specs/{bc_name}_spec.md")
    
    if config.include_docker:
        files_to_generate.append("docker-compose.yml")
        files_to_generate.append("Dockerfile")
    
    if config.include_kubernetes:
        files_to_generate.append("k8s/deployment.yaml")
        files_to_generate.append("k8s/service.yaml")
    
    return {
        "success": True,
        "bounded_contexts": [{"id": bc.get("id"), "name": bc.get("name")} for bc in bcs],
        "tech_stack": config.dict(),
        "files_to_generate": files_to_generate,
        "download_url": "/api/prd/download"
    }


@router.post("/generate-files")
async def generate_prd_files(request: PRDGenerationRequest):
    """
    Generate PRD files and return them as JSON array.
    Used by VS Code extension to save files directly to workspace.
    """
    
    if not request.node_ids:
        raise HTTPException(status_code=400, detail="node_ids cannot be empty")
    
    # Get BC data from Neo4j
    bcs = await get_bcs_from_nodes(request.node_ids)
    
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")
    
    config = request.tech_stack
    
    # Generate files as list of {path, content}
    files = []
    
    # Main files
    files.append({"path": "CLAUDE.md", "content": generate_claude_md(bcs, config)})
    files.append({"path": "PRD.md", "content": generate_main_prd(bcs, config)})
    files.append({"path": ".cursorrules", "content": generate_cursor_rules(config)})
    files.append({"path": "README.md", "content": generate_readme(bcs, config)})
    
    # BC-specific files
    for bc in bcs:
        bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
        
        # BC spec file
        files.append({
            "path": f"specs/{bc_name}_spec.md",
            "content": generate_bc_spec(bc, config)
        })
        
        # Agent config
        files.append({
            "path": f".claude/agents/{bc_name}_agent.md",
            "content": generate_agent_config(bc, config)
        })
    
    # Docker files
    if config.include_docker:
        files.append({"path": "docker-compose.yml", "content": generate_docker_compose(bcs, config)})
        files.append({"path": "Dockerfile", "content": generate_dockerfile(config)})
    
    # Kubernetes files
    if config.include_kubernetes:
        for bc in bcs:
            bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
            files.append({
                "path": f"k8s/{bc_name}/deployment.yaml",
                "content": generate_k8s_deployment(bc, config)
            })
            files.append({
                "path": f"k8s/{bc_name}/service.yaml",
                "content": generate_k8s_service(bc, config)
            })
    
    return files


@router.post("/download")
async def download_prd_zip(request: PRDGenerationRequest):
    """
    Generate and download PRD as a zip file.
    """
    
    if not request.node_ids:
        raise HTTPException(status_code=400, detail="node_ids cannot be empty")
    
    # Get BC data from Neo4j
    bcs = await get_bcs_from_nodes(request.node_ids)
    
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")
    
    config = request.tech_stack
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Generate main files
        zip_file.writestr("CLAUDE.md", generate_claude_md(bcs, config))
        zip_file.writestr("PRD.md", generate_main_prd(bcs, config))
        zip_file.writestr(".cursorrules", generate_cursor_rules(config))
        
        # Generate BC-specific files
        for bc in bcs:
            bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
            
            # BC spec file
            zip_file.writestr(
                f"specs/{bc_name}_spec.md",
                generate_bc_spec(bc, config)
            )
            
            # Agent config
            zip_file.writestr(
                f".claude/agents/{bc_name}_agent.md",
                generate_agent_config(bc, config)
            )
        
        # Docker files
        if config.include_docker:
            zip_file.writestr("docker-compose.yml", generate_docker_compose(bcs, config))
            zip_file.writestr("Dockerfile", generate_dockerfile(config))
        
        # Kubernetes files
        if config.include_kubernetes:
            for bc in bcs:
                bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
                zip_file.writestr(
                    f"k8s/{bc_name}/deployment.yaml",
                    generate_k8s_deployment(bc, config)
                )
                zip_file.writestr(
                    f"k8s/{bc_name}/service.yaml",
                    generate_k8s_service(bc, config)
                )
        
        # README
        zip_file.writestr("README.md", generate_readme(bcs, config))
    
    zip_buffer.seek(0)
    
    filename = f"{config.project_name}_prd_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# =============================================================================
# Additional Template Generators
# =============================================================================

def generate_docker_compose(bcs: list[dict], config: TechStackConfig) -> str:
    """Generate docker-compose.yml."""
    
    services = {}
    
    # Add database
    if config.database == Database.POSTGRESQL:
        services["postgres"] = """
    image: postgres:15
    environment:
      POSTGRES_DB: ${DB_NAME:-app}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
"""
    elif config.database == Database.MONGODB:
        services["mongodb"] = """
    image: mongo:6
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
"""
    
    # Add messaging
    if config.messaging == MessagingPlatform.KAFKA:
        services["zookeeper"] = """
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
"""
        services["kafka"] = """
    image: confluentinc/cp-kafka:7.4.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
"""
    elif config.messaging == MessagingPlatform.RABBITMQ:
        services["rabbitmq"] = """
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
"""
    
    # Add microservices if applicable
    if config.deployment == DeploymentStyle.MICROSERVICES:
        for bc in bcs:
            bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
            services[bc_name] = f"""
    build:
      context: ./{bc_name}
      dockerfile: Dockerfile
    ports:
      - "${{PORT_{bc_name.upper()}:-808{bcs.index(bc)}}}:8080"
    environment:
      - SPRING_PROFILES_ACTIVE=docker
    depends_on:
      - {"kafka" if config.messaging == MessagingPlatform.KAFKA else "rabbitmq" if config.messaging == MessagingPlatform.RABBITMQ else "postgres" if config.database == Database.POSTGRESQL else "mongodb"}
"""
    
    # Build YAML
    yml = f"""version: '3.8'

services:
"""
    
    for name, definition in services.items():
        yml += f"  {name}:{definition}\n"
    
    yml += """
volumes:
  postgres_data:
  mongo_data:
"""
    
    return yml


def generate_dockerfile(config: TechStackConfig) -> str:
    """Generate Dockerfile based on framework."""
    
    if config.framework in [Framework.SPRING_BOOT, Framework.SPRING_WEBFLUX]:
        return """FROM eclipse-temurin:17-jdk-alpine as builder
WORKDIR /app
COPY . .
RUN ./mvnw clean package -DskipTests

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
"""
    elif config.framework in [Framework.NESTJS, Framework.EXPRESS]:
        return """FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
EXPOSE 3000
CMD ["node", "dist/main"]
"""
    elif config.framework == Framework.FASTAPI:
        return """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    elif config.framework in [Framework.GIN, Framework.FIBER]:
        return """FROM golang:1.21-alpine as builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/main .
EXPOSE 8080
CMD ["./main"]
"""
    
    return "# Dockerfile template\n"


def generate_k8s_deployment(bc: dict, config: TechStackConfig) -> str:
    """Generate Kubernetes deployment YAML."""
    
    bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
    
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {bc_name}
  labels:
    app: {bc_name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {bc_name}
  template:
    metadata:
      labels:
        app: {bc_name}
    spec:
      containers:
      - name: {bc_name}
        image: ${{IMAGE_REGISTRY}}/{config.project_name}/{bc_name}:${{IMAGE_TAG:-latest}}
        ports:
        - containerPort: 8080
        env:
        - name: SPRING_PROFILES_ACTIVE
          value: kubernetes
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
"""


def generate_k8s_service(bc: dict, config: TechStackConfig) -> str:
    """Generate Kubernetes service YAML."""
    
    bc_name = bc.get("name", "unknown").lower().replace(" ", "_")
    
    return f"""apiVersion: v1
kind: Service
metadata:
  name: {bc_name}
  labels:
    app: {bc_name}
spec:
  type: ClusterIP
  ports:
  - port: 8080
    targetPort: 8080
    protocol: TCP
    name: http
  selector:
    app: {bc_name}
"""


def generate_readme(bcs: list[dict], config: TechStackConfig) -> str:
    """Generate README.md."""
    
    return f"""# {config.project_name}

Event-driven {"microservices" if config.deployment == DeploymentStyle.MICROSERVICES else "modular monolith"} generated from Event Storming model.

## Technology Stack

- **Language**: {config.language.value}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value}
- **Database**: {config.database.value}

## Bounded Contexts

{chr(10).join([f"- **{bc.get('name')}**: {bc.get('description', 'No description')}" for bc in bcs])}

## Getting Started

### Prerequisites

- {"JDK 17+" if config.language in [Language.JAVA, Language.KOTLIN] else ""}
- {"Node.js 18+" if config.language == Language.TYPESCRIPT else ""}
- {"Python 3.11+" if config.language == Language.PYTHON else ""}
- {"Go 1.21+" if config.language == Language.GO else ""}
- Docker (for local development)

### Local Development

1. Start infrastructure:
```bash
docker-compose up -d {"kafka" if config.messaging == MessagingPlatform.KAFKA else "rabbitmq" if config.messaging == MessagingPlatform.RABBITMQ else "postgres"}
```

2. Run the application:
```bash
{"./mvnw spring-boot:run" if config.framework in [Framework.SPRING_BOOT, Framework.SPRING_WEBFLUX] else ""}
{"npm run start:dev" if config.framework in [Framework.NESTJS, Framework.EXPRESS] else ""}
{"uvicorn main:app --reload" if config.framework == Framework.FASTAPI else ""}
{"go run main.go" if config.framework in [Framework.GIN, Framework.FIBER] else ""}
```

## Documentation

- [PRD.md](./PRD.md) - Product Requirements Document
- [CLAUDE.md](./CLAUDE.md) - AI Assistant Context
- `specs/` - Bounded Context specifications
- `.claude/agents/` - Agent configurations for each BC

## Architecture

See [PRD.md](./PRD.md) for detailed architecture documentation.

## AI-Assisted Development

This project is optimized for vibe coding with AI assistants:

1. **Claude Code**: Use the `.claude/` folder for context
2. **Cursor**: Use the `.cursorrules` for IDE integration
3. **Per-BC agents**: Each BC has its own agent context in `.claude/agents/`

When working on a specific BC, point your AI assistant to the relevant agent file for focused context.
"""

