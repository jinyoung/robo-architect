"""
Neo4j Client for Event Storming Graph Operations

This module provides CRUD operations for the Event Storming ontology:
- UserStory, BoundedContext, Aggregate, Command, Event, Policy
- All relationship types (IMPLEMENTS, HAS_AGGREGATE, HAS_COMMAND, etc.)
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""

    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "12345analyzer"))


class Neo4jClient:
    """Neo4j client for Event Storming graph operations."""

    def __init__(self, config: Neo4jConfig | None = None):
        self.config = config or Neo4jConfig()
        self._driver: Driver | None = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.config.uri, auth=(self.config.user, self.config.password)
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    @contextmanager
    def session(self):
        """Context manager for Neo4j sessions."""
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()

    def verify_connection(self) -> bool:
        """Verify Neo4j connection."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    # =========================================================================
    # User Story Operations
    # =========================================================================

    def get_all_user_stories(self) -> list[dict[str, Any]]:
        """Fetch all user stories from Neo4j."""
        query = """
        MATCH (us:UserStory)
        OPTIONAL MATCH (us)-[:IMPLEMENTS]->(target)
        WITH us, collect(DISTINCT {type: labels(target)[0], name: target.name, id: target.id}) as implemented_in
        RETURN {
            id: us.id,
            role: us.role,
            action: us.action,
            benefit: us.benefit,
            priority: us.priority,
            status: us.status,
            implemented_in: implemented_in
        } as user_story
        ORDER BY user_story.id
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["user_story"]) for record in result]

    def get_unprocessed_user_stories(self) -> list[dict[str, Any]]:
        """Fetch user stories not yet assigned to a Bounded Context."""
        query = """
        MATCH (us:UserStory)
        WHERE NOT (us)-[:IMPLEMENTS]->(:BoundedContext)
        RETURN us {.id, .role, .action, .benefit, .priority, .status} as user_story
        ORDER BY us.priority DESC, us.id
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["user_story"]) for record in result]

    def get_user_stories_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch user stories assigned to a specific Bounded Context."""
        query = """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext {id: $bc_id})
        RETURN us {.id, .role, .action, .benefit, .priority, .status} as user_story
        ORDER BY us.id
        """
        with self.session() as session:
            result = session.run(query, bc_id=bc_id)
            return [dict(record["user_story"]) for record in result]

    def create_user_story(
        self,
        id: str,
        role: str,
        action: str,
        benefit: str | None = None,
        priority: str = "medium",
        status: str = "draft",
        ui_description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new user story."""
        query = """
        CREATE (us:UserStory {
            id: $id,
            role: $role,
            action: $action,
            benefit: $benefit,
            priority: $priority,
            status: $status,
            uiDescription: $ui_description
        })
        RETURN us {.id, .role, .action, .benefit, .priority, .status, .uiDescription} as user_story
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                role=role,
                action=action,
                benefit=benefit,
                priority=priority,
                status=status,
                ui_description=ui_description or "",
            )
            return dict(result.single()["user_story"])

    # =========================================================================
    # Bounded Context Operations
    # =========================================================================

    def get_all_bounded_contexts(self) -> list[dict[str, Any]]:
        """Fetch all bounded contexts with their aggregates."""
        query = """
        MATCH (bc:BoundedContext)
        OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
        WITH bc, collect(DISTINCT agg {.id, .name}) as aggregates
        RETURN {
            id: bc.id,
            name: bc.name,
            description: bc.description,
            owner: bc.owner,
            aggregates: aggregates
        } as bounded_context
        ORDER BY bounded_context.name
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["bounded_context"]) for record in result]

    def create_bounded_context(
        self,
        id: str,
        name: str,
        description: str | None = None,
        owner: str | None = None,
    ) -> dict[str, Any]:
        """Create a new bounded context."""
        query = """
        MERGE (bc:BoundedContext {id: $id})
        SET bc.name = $name,
            bc.description = $description,
            bc.owner = $owner
        RETURN bc {.id, .name, .description, .owner} as bounded_context
        """
        with self.session() as session:
            result = session.run(
                query, id=id, name=name, description=description, owner=owner
            )
            return dict(result.single()["bounded_context"])

    def link_user_story_to_bc(
        self, user_story_id: str, bc_id: str, confidence: float = 0.9
    ) -> bool:
        """Link a user story to a bounded context via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (us)-[r:IMPLEMENTS]->(bc)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, bc.id
        """
        with self.session() as session:
            result = session.run(
                query, user_story_id=user_story_id, bc_id=bc_id, confidence=confidence
            )
            return result.single() is not None

    # =========================================================================
    # Aggregate Operations
    # =========================================================================

    def get_aggregates_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch aggregates belonging to a bounded context."""
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
        OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
        WITH agg, collect(DISTINCT cmd {.id, .name}) as commands
        RETURN {
            id: agg.id,
            name: agg.name,
            rootEntity: agg.rootEntity,
            invariants: agg.invariants,
            commands: commands
        } as aggregate
        ORDER BY aggregate.name
        """
        with self.session() as session:
            result = session.run(query, bc_id=bc_id)
            return [dict(record["aggregate"]) for record in result]

    def create_aggregate(
        self,
        id: str,
        name: str,
        bc_id: str,
        root_entity: str | None = None,
        invariants: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new aggregate and link it to a bounded context.
        
        IMPORTANT: One Aggregate belongs to exactly ONE Bounded Context.
        If an aggregate with the same ID already exists and belongs to a different BC,
        this will raise an error.
        """
        # First, check if aggregate exists and belongs to a different BC
        check_query = """
        OPTIONAL MATCH (existing:Aggregate {id: $id})<-[:HAS_AGGREGATE]-(otherBC:BoundedContext)
        WHERE otherBC.id <> $bc_id
        RETURN otherBC.id as existing_bc
        """
        with self.session() as session:
            check_result = session.run(check_query, id=id, bc_id=bc_id)
            record = check_result.single()
            if record and record["existing_bc"]:
                raise ValueError(
                    f"Aggregate {id} already belongs to BC {record['existing_bc']}. "
                    f"An Aggregate can only belong to ONE Bounded Context."
                )
        
        # Create or update the aggregate
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (agg:Aggregate {id: $id})
        SET agg.name = $name,
            agg.rootEntity = $root_entity,
            agg.invariants = $invariants
        MERGE (bc)-[:HAS_AGGREGATE {isPrimary: false}]->(agg)
        RETURN agg {.id, .name, .rootEntity, .invariants} as aggregate
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                bc_id=bc_id,
                root_entity=root_entity or name,
                invariants=invariants or [],
            )
            return dict(result.single()["aggregate"])

    def link_user_story_to_aggregate(
        self, user_story_id: str, aggregate_id: str, confidence: float = 0.9
    ) -> bool:
        """Link a user story to an aggregate via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (agg:Aggregate {id: $aggregate_id})
        MERGE (us)-[r:IMPLEMENTS]->(agg)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, agg.id
        """
        with self.session() as session:
            result = session.run(
                query, user_story_id=user_story_id, aggregate_id=aggregate_id, confidence=confidence
            )
            return result.single() is not None

    def link_user_story_to_command(
        self, user_story_id: str, command_id: str, confidence: float = 0.9
    ) -> bool:
        """Link a user story to a command via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (cmd:Command {id: $command_id})
        MERGE (us)-[r:IMPLEMENTS]->(cmd)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, cmd.id
        """
        with self.session() as session:
            result = session.run(
                query, user_story_id=user_story_id, command_id=command_id, confidence=confidence
            )
            return result.single() is not None

    def link_user_story_to_event(
        self, user_story_id: str, event_id: str, confidence: float = 0.9
    ) -> bool:
        """Link a user story to an event via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (evt:Event {id: $event_id})
        MERGE (us)-[r:IMPLEMENTS]->(evt)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, evt.id
        """
        with self.session() as session:
            result = session.run(
                query, user_story_id=user_story_id, event_id=event_id, confidence=confidence
            )
            return result.single() is not None

    def link_user_story_to_readmodel(
        self, user_story_id: str, readmodel_id: str, confidence: float = 0.9
    ) -> bool:
        """Link a user story to a ReadModel via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (rm:ReadModel {id: $readmodel_id})
        MERGE (us)-[r:IMPLEMENTS]->(rm)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, rm.id
        """
        with self.session() as session:
            result = session.run(
                query, user_story_id=user_story_id, readmodel_id=readmodel_id, confidence=confidence
            )
            return result.single() is not None

    # =========================================================================
    # Command Operations
    # =========================================================================

    def create_command(
        self,
        id: str,
        name: str,
        aggregate_id: str,
        actor: str = "user",
        input_schema: str | None = None,
    ) -> dict[str, Any]:
        """Create a new command and link it to an aggregate."""
        query = """
        MATCH (agg:Aggregate {id: $aggregate_id})
        MERGE (cmd:Command {id: $id})
        SET cmd.name = $name,
            cmd.actor = $actor,
            cmd.inputSchema = $input_schema
        MERGE (agg)-[:HAS_COMMAND]->(cmd)
        RETURN cmd {.id, .name, .actor, .inputSchema} as command
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                aggregate_id=aggregate_id,
                actor=actor,
                input_schema=input_schema,
            )
            return dict(result.single()["command"])

    def get_commands_by_aggregate(self, aggregate_id: str) -> list[dict[str, Any]]:
        """Fetch commands belonging to an aggregate."""
        query = """
        MATCH (agg:Aggregate {id: $aggregate_id})-[:HAS_COMMAND]->(cmd:Command)
        OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
        WITH cmd, collect(DISTINCT evt {.id, .name}) as emits
        RETURN {
            id: cmd.id,
            name: cmd.name,
            actor: cmd.actor,
            inputSchema: cmd.inputSchema,
            emits: emits
        } as command
        ORDER BY command.name
        """
        with self.session() as session:
            result = session.run(query, aggregate_id=aggregate_id)
            return [dict(record["command"]) for record in result]

    # =========================================================================
    # Event Operations
    # =========================================================================

    def create_event(
        self,
        id: str,
        name: str,
        command_id: str,
        version: str = "1.0.0",
        schema: str | None = None,
    ) -> dict[str, Any]:
        """Create a new event and link it to a command via EMITS."""
        query = """
        MATCH (cmd:Command {id: $command_id})
        MERGE (evt:Event {id: $id})
        SET evt.name = $name,
            evt.version = $version,
            evt.schema = $schema,
            evt.isBreaking = false
        MERGE (cmd)-[:EMITS {isGuaranteed: true}]->(evt)
        RETURN evt {.id, .name, .version, .schema} as event
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                command_id=command_id,
                version=version,
                schema=schema,
            )
            return dict(result.single()["event"])

    # =========================================================================
    # Policy Operations
    # =========================================================================

    def create_policy(
        self,
        id: str,
        name: str,
        bc_id: str,
        trigger_event_id: str,
        invoke_command_id: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a policy with TRIGGERS and INVOKES relationships."""
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MATCH (evt:Event {id: $trigger_event_id})
        MATCH (cmd:Command {id: $invoke_command_id})
        MERGE (pol:Policy {id: $id})
        SET pol.name = $name,
            pol.description = $description
        MERGE (bc)-[:HAS_POLICY]->(pol)
        MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
        MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
        RETURN pol {.id, .name, .description} as policy
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                bc_id=bc_id,
                trigger_event_id=trigger_event_id,
                invoke_command_id=invoke_command_id,
                description=description,
            )
            return dict(result.single()["policy"])

    # =========================================================================
    # Property Operations
    # =========================================================================

    def create_property(
        self,
        id: str,
        name: str,
        parent_id: str,
        parent_type: str,
        data_type: str = "String",
        description: str | None = None,
        is_required: bool = True,
    ) -> dict[str, Any]:
        """
        Create a Property node and link it to a parent (Aggregate, Command, or Event).
        
        Uses HAS_PROPERTY relationship.
        """
        # Determine the label of the parent
        parent_label = parent_type  # BoundedContext, Aggregate, Command, Event
        
        query = f"""
        MATCH (parent:{parent_label} {{id: $parent_id}})
        MERGE (prop:Property {{id: $id}})
        SET prop.name = $name,
            prop.type = $data_type,
            prop.description = $description,
            prop.isRequired = $is_required,
            prop.parentId = $parent_id,
            prop.parentType = $parent_type
        MERGE (parent)-[:HAS_PROPERTY]->(prop)
        RETURN prop {{.id, .name, .type, .description, .isRequired}} as property
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                parent_id=parent_id,
                data_type=data_type,
                description=description,
                is_required=is_required,
                parent_type=parent_type,
            )
            record = result.single()
            return dict(record["property"]) if record else {}

    def get_properties_by_parent(self, parent_id: str) -> list[dict[str, Any]]:
        """Fetch properties belonging to a parent node."""
        query = """
        MATCH (parent {id: $parent_id})-[:HAS_PROPERTY]->(prop:Property)
        RETURN prop {.id, .name, .type, .description, .isRequired} as property
        ORDER BY prop.name
        """
        with self.session() as session:
            result = session.run(query, parent_id=parent_id)
            return [dict(record["property"]) for record in result]

    # =========================================================================
    # ReadModel Operations (CQRS / Query Models)
    # =========================================================================

    def create_readmodel(
        self,
        id: str,
        name: str,
        bc_id: str,
        description: str | None = None,
        provisioning_type: str = "CQRS",
        cqrs_config: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a ReadModel node and link it to a Bounded Context.
        
        Uses HAS_READMODEL relationship.
        """
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (rm:ReadModel {id: $id})
        SET rm.name = $name,
            rm.description = $description,
            rm.provisioningType = $provisioning_type,
            rm.cqrsConfig = $cqrs_config
        MERGE (bc)-[:HAS_READMODEL]->(rm)
        RETURN rm {.id, .name, .description, .provisioningType} as readmodel
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                bc_id=bc_id,
                description=description,
                provisioning_type=provisioning_type,
                cqrs_config=cqrs_config,
            )
            record = result.single()
            return dict(record["readmodel"]) if record else {}

    def get_readmodels_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch ReadModels belonging to a bounded context."""
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_READMODEL]->(rm:ReadModel)
        OPTIONAL MATCH (rm)-[:HAS_PROPERTY]->(prop:Property)
        WITH rm, collect(DISTINCT prop {.id, .name, .type}) as properties
        RETURN {
            id: rm.id,
            name: rm.name,
            description: rm.description,
            provisioningType: rm.provisioningType,
            cqrsConfig: rm.cqrsConfig,
            properties: properties
        } as readmodel
        ORDER BY readmodel.name
        """
        with self.session() as session:
            result = session.run(query, bc_id=bc_id)
            return [dict(record["readmodel"]) for record in result]

    def link_event_to_readmodel(
        self,
        event_id: str,
        readmodel_id: str,
        action: str = "CREATE",
        mapping_config: str | None = None,
        where_condition: str | None = None,
    ) -> bool:
        """
        Link an Event to a ReadModel via POPULATES relationship.
        
        This represents the CQRS pattern where Events populate ReadModels.
        """
        query = """
        MATCH (evt:Event {id: $event_id})
        MATCH (rm:ReadModel {id: $readmodel_id})
        MERGE (evt)-[r:POPULATES]->(rm)
        SET r.action = $action,
            r.mappingConfig = $mapping_config,
            r.whereCondition = $where_condition
        RETURN evt.id, rm.id
        """
        with self.session() as session:
            result = session.run(
                query,
                event_id=event_id,
                readmodel_id=readmodel_id,
                action=action,
                mapping_config=mapping_config,
                where_condition=where_condition,
            )
            return result.single() is not None

    def link_readmodel_to_command(
        self,
        readmodel_id: str,
        command_id: str,
    ) -> bool:
        """
        Link a ReadModel to a Command via SUPPORTS relationship.
        
        This indicates that the ReadModel provides data needed for the Command.
        """
        query = """
        MATCH (rm:ReadModel {id: $readmodel_id})
        MATCH (cmd:Command {id: $command_id})
        MERGE (rm)-[r:SUPPORTS]->(cmd)
        RETURN rm.id, cmd.id
        """
        with self.session() as session:
            result = session.run(
                query,
                readmodel_id=readmodel_id,
                command_id=command_id,
            )
            return result.single() is not None

    def get_events_for_readmodel(self, readmodel_id: str) -> list[dict[str, Any]]:
        """Get all Events that populate a ReadModel."""
        query = """
        MATCH (evt:Event)-[r:POPULATES]->(rm:ReadModel {id: $readmodel_id})
        RETURN {
            id: evt.id,
            name: evt.name,
            action: r.action,
            mappingConfig: r.mappingConfig,
            whereCondition: r.whereCondition
        } as event_mapping
        ORDER BY evt.name
        """
        with self.session() as session:
            result = session.run(query, readmodel_id=readmodel_id)
            return [dict(record["event_mapping"]) for record in result]

    def get_commands_supported_by_readmodel(self, readmodel_id: str) -> list[dict[str, Any]]:
        """Get all Commands that a ReadModel supports."""
        query = """
        MATCH (rm:ReadModel {id: $readmodel_id})-[:SUPPORTS]->(cmd:Command)
        RETURN cmd {.id, .name, .actor} as command
        ORDER BY cmd.name
        """
        with self.session() as session:
            result = session.run(query, readmodel_id=readmodel_id)
            return [dict(record["command"]) for record in result]

    # =========================================================================
    # UI Wireframe Operations
    # =========================================================================

    def create_ui(
        self,
        id: str,
        name: str,
        bc_id: str,
        template: str | None = None,
        attached_to_id: str | None = None,
        attached_to_type: str | None = None,
        attached_to_name: str | None = None,
        user_story_id: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a UI wireframe node and link it to its attached Command/ReadModel.
        
        Uses ATTACHED_TO relationship to link UI to Command or ReadModel.
        Uses HAS_UI relationship to link BC to UI.
        """
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (ui:UI {id: $id})
        SET ui.name = $name,
            ui.template = $template,
            ui.attachedToId = $attached_to_id,
            ui.attachedToType = $attached_to_type,
            ui.attachedToName = $attached_to_name,
            ui.userStoryId = $user_story_id,
            ui.description = $description
        MERGE (bc)-[:HAS_UI]->(ui)
        RETURN ui {.id, .name, .template, .attachedToId, .attachedToType} as ui_node
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                bc_id=bc_id,
                template=template,
                attached_to_id=attached_to_id,
                attached_to_type=attached_to_type,
                attached_to_name=attached_to_name,
                user_story_id=user_story_id,
                description=description,
            )
            record = result.single()
            if record:
                # Also create ATTACHED_TO relationship if attached_to_id is provided
                if attached_to_id and attached_to_type:
                    self._link_ui_to_target(id, attached_to_id, attached_to_type)
                return dict(record["ui_node"])
            return {}

    def _link_ui_to_target(
        self,
        ui_id: str,
        target_id: str,
        target_type: str,
    ) -> bool:
        """Link UI to its target Command or ReadModel via ATTACHED_TO relationship."""
        query = f"""
        MATCH (ui:UI {{id: $ui_id}})
        MATCH (target:{target_type} {{id: $target_id}})
        MERGE (ui)-[:ATTACHED_TO]->(target)
        RETURN ui.id, target.id
        """
        with self.session() as session:
            result = session.run(query, ui_id=ui_id, target_id=target_id)
            return result.single() is not None

    def get_uis_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch UI wireframes belonging to a bounded context."""
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_UI]->(ui:UI)
        RETURN {
            id: ui.id,
            name: ui.name,
            template: ui.template,
            attachedToId: ui.attachedToId,
            attachedToType: ui.attachedToType,
            attachedToName: ui.attachedToName,
            userStoryId: ui.userStoryId,
            description: ui.description
        } as ui_node
        ORDER BY ui.name
        """
        with self.session() as session:
            result = session.run(query, bc_id=bc_id)
            return [dict(record["ui_node"]) for record in result]

    def update_ui_template(self, ui_id: str, template: str) -> bool:
        """Update the template of a UI wireframe."""
        query = """
        MATCH (ui:UI {id: $ui_id})
        SET ui.template = $template,
            ui.updatedAt = datetime()
        RETURN ui.id
        """
        with self.session() as session:
            result = session.run(query, ui_id=ui_id, template=template)
            return result.single() is not None

    # =========================================================================
    # CQRS Configuration Graph (CQRSConfig, CQRSOperation, CQRSMapping, CQRSWhere)
    # =========================================================================

    def create_cqrs_config(self, readmodel_id: str) -> dict[str, Any]:
        """
        Create a CQRSConfig node and link it to a ReadModel.
        
        Returns the created CQRSConfig.
        """
        cqrs_id = f"CQRS-{readmodel_id}"
        query = """
        MATCH (rm:ReadModel {id: $readmodel_id})
        MERGE (cqrs:CQRSConfig {id: $cqrs_id})
        SET cqrs.readmodelId = $readmodel_id
        MERGE (rm)-[:HAS_CQRS]->(cqrs)
        RETURN cqrs {.id, .readmodelId} as config
        """
        with self.session() as session:
            result = session.run(query, readmodel_id=readmodel_id, cqrs_id=cqrs_id)
            record = result.single()
            return dict(record["config"]) if record else {}

    def get_cqrs_config(self, readmodel_id: str) -> dict[str, Any]:
        """
        Get the full CQRS configuration for a ReadModel, including all operations,
        mappings, and where conditions.
        """
        query = """
        MATCH (rm:ReadModel {id: $readmodel_id})-[:HAS_CQRS]->(cqrs:CQRSConfig)
        OPTIONAL MATCH (cqrs)-[:HAS_OPERATION]->(op:CQRSOperation)
        OPTIONAL MATCH (op)-[:TRIGGERED_BY]->(evt:Event)
        OPTIONAL MATCH (op)-[:HAS_MAPPING]->(m:CQRSMapping)
        OPTIONAL MATCH (m)-[:SOURCE]->(srcProp:Property)
        OPTIONAL MATCH (m)-[:TARGET]->(tgtProp:Property)
        OPTIONAL MATCH (op)-[:HAS_WHERE]->(w:CQRSWhere)
        OPTIONAL MATCH (w)-[:TARGET]->(whereTgtProp:Property)
        OPTIONAL MATCH (w)-[:SOURCE_EVENT_FIELD]->(whereSrcProp:Property)
        WITH cqrs, op, evt, 
             collect(DISTINCT {
                 id: m.id,
                 sourceType: m.sourceType,
                 staticValue: m.staticValue,
                 sourcePropertyId: srcProp.id,
                 sourcePropertyName: srcProp.name,
                 targetPropertyId: tgtProp.id,
                 targetPropertyName: tgtProp.name
             }) as mappings,
             collect(DISTINCT {
                 id: w.id,
                 operator: w.operator,
                 targetPropertyId: whereTgtProp.id,
                 targetPropertyName: whereTgtProp.name,
                 sourceEventFieldId: whereSrcProp.id,
                 sourceEventFieldName: whereSrcProp.name
             }) as whereConditions
        WITH cqrs, collect(DISTINCT {
            id: op.id,
            operationType: op.operationType,
            triggerEventId: evt.id,
            triggerEventName: evt.name,
            mappings: mappings,
            whereConditions: whereConditions
        }) as operations
        RETURN {
            id: cqrs.id,
            readmodelId: cqrs.readmodelId,
            operations: operations
        } as config
        """
        with self.session() as session:
            result = session.run(query, readmodel_id=readmodel_id)
            record = result.single()
            if not record:
                return {}
            config = dict(record["config"])
            # Filter out null operations
            if config.get("operations"):
                config["operations"] = [
                    op for op in config["operations"]
                    if op.get("id") is not None
                ]
                # Filter out null mappings/whereConditions in each operation
                for op in config["operations"]:
                    if op.get("mappings"):
                        op["mappings"] = [m for m in op["mappings"] if m.get("id") is not None]
                    if op.get("whereConditions"):
                        op["whereConditions"] = [w for w in op["whereConditions"] if w.get("id") is not None]
            return config

    def delete_cqrs_config(self, readmodel_id: str) -> bool:
        """
        Delete a CQRSConfig and all related operations, mappings, and where conditions.
        """
        query = """
        MATCH (rm:ReadModel {id: $readmodel_id})-[:HAS_CQRS]->(cqrs:CQRSConfig)
        OPTIONAL MATCH (cqrs)-[:HAS_OPERATION]->(op:CQRSOperation)
        OPTIONAL MATCH (op)-[:HAS_MAPPING]->(m:CQRSMapping)
        OPTIONAL MATCH (op)-[:HAS_WHERE]->(w:CQRSWhere)
        DETACH DELETE cqrs, op, m, w
        RETURN count(cqrs) as deleted
        """
        with self.session() as session:
            result = session.run(query, readmodel_id=readmodel_id)
            record = result.single()
            return record["deleted"] > 0 if record else False

    def create_cqrs_operation(
        self,
        cqrs_config_id: str,
        operation_type: str,
        trigger_event_id: str,
    ) -> dict[str, Any]:
        """
        Create a CQRSOperation node and link it to a CQRSConfig and trigger Event.
        
        operation_type: "INSERT", "UPDATE", or "DELETE"
        """
        # Generate a unique operation ID
        op_id = f"CQRS-OP-{cqrs_config_id.replace('CQRS-', '')}-{operation_type}-{trigger_event_id.replace('EVT-', '')}"
        query = """
        MATCH (cqrs:CQRSConfig {id: $cqrs_config_id})
        MATCH (evt:Event {id: $trigger_event_id})
        MERGE (op:CQRSOperation {id: $op_id})
        SET op.operationType = $operation_type,
            op.cqrsConfigId = $cqrs_config_id,
            op.triggerEventId = $trigger_event_id
        MERGE (cqrs)-[:HAS_OPERATION]->(op)
        MERGE (op)-[:TRIGGERED_BY]->(evt)
        RETURN op {.id, .operationType, .cqrsConfigId, .triggerEventId} as operation
        """
        with self.session() as session:
            result = session.run(
                query,
                cqrs_config_id=cqrs_config_id,
                op_id=op_id,
                operation_type=operation_type,
                trigger_event_id=trigger_event_id,
            )
            record = result.single()
            return dict(record["operation"]) if record else {}

    def delete_cqrs_operation(self, operation_id: str) -> bool:
        """
        Delete a CQRSOperation and all its mappings and where conditions.
        """
        query = """
        MATCH (op:CQRSOperation {id: $operation_id})
        OPTIONAL MATCH (op)-[:HAS_MAPPING]->(m:CQRSMapping)
        OPTIONAL MATCH (op)-[:HAS_WHERE]->(w:CQRSWhere)
        DETACH DELETE op, m, w
        RETURN count(op) as deleted
        """
        with self.session() as session:
            result = session.run(query, operation_id=operation_id)
            record = result.single()
            return record["deleted"] > 0 if record else False

    def create_cqrs_mapping(
        self,
        operation_id: str,
        target_property_id: str,
        source_property_id: str | None = None,
        source_type: str = "event",
        static_value: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a CQRSMapping node for field mapping in a CQRS operation.
        
        source_type: "event" (use source_property_id) or "value" (use static_value)
        """
        # Generate a unique mapping ID
        import uuid
        mapping_id = f"CQRS-MAP-{uuid.uuid4().hex[:8]}"
        
        if source_type == "event" and source_property_id:
            query = """
            MATCH (op:CQRSOperation {id: $operation_id})
            MATCH (srcProp:Property {id: $source_property_id})
            MATCH (tgtProp:Property {id: $target_property_id})
            MERGE (m:CQRSMapping {id: $mapping_id})
            SET m.operationId = $operation_id,
                m.sourceType = $source_type,
                m.staticValue = null
            MERGE (op)-[:HAS_MAPPING]->(m)
            MERGE (m)-[:SOURCE]->(srcProp)
            MERGE (m)-[:TARGET]->(tgtProp)
            RETURN m {.id, .operationId, .sourceType} as mapping
            """
            params = {
                "operation_id": operation_id,
                "mapping_id": mapping_id,
                "source_property_id": source_property_id,
                "target_property_id": target_property_id,
                "source_type": source_type,
            }
        else:
            # Static value mapping
            query = """
            MATCH (op:CQRSOperation {id: $operation_id})
            MATCH (tgtProp:Property {id: $target_property_id})
            MERGE (m:CQRSMapping {id: $mapping_id})
            SET m.operationId = $operation_id,
                m.sourceType = $source_type,
                m.staticValue = $static_value
            MERGE (op)-[:HAS_MAPPING]->(m)
            MERGE (m)-[:TARGET]->(tgtProp)
            RETURN m {.id, .operationId, .sourceType, .staticValue} as mapping
            """
            params = {
                "operation_id": operation_id,
                "mapping_id": mapping_id,
                "target_property_id": target_property_id,
                "source_type": source_type,
                "static_value": static_value,
            }
        
        with self.session() as session:
            result = session.run(query, **params)
            record = result.single()
            return dict(record["mapping"]) if record else {}

    def delete_cqrs_mapping(self, mapping_id: str) -> bool:
        """Delete a CQRSMapping node."""
        query = """
        MATCH (m:CQRSMapping {id: $mapping_id})
        DETACH DELETE m
        RETURN count(m) as deleted
        """
        with self.session() as session:
            result = session.run(query, mapping_id=mapping_id)
            record = result.single()
            return record["deleted"] > 0 if record else False

    def create_cqrs_where(
        self,
        operation_id: str,
        target_property_id: str,
        source_event_field_id: str,
        operator: str = "=",
    ) -> dict[str, Any]:
        """
        Create a CQRSWhere node for UPDATE/DELETE conditions.
        
        operator: "=", "!=", ">", "<", ">=", "<="
        """
        import uuid
        where_id = f"CQRS-WHERE-{uuid.uuid4().hex[:8]}"
        
        query = """
        MATCH (op:CQRSOperation {id: $operation_id})
        MATCH (tgtProp:Property {id: $target_property_id})
        MATCH (srcProp:Property {id: $source_event_field_id})
        MERGE (w:CQRSWhere {id: $where_id})
        SET w.operationId = $operation_id,
            w.operator = $operator
        MERGE (op)-[:HAS_WHERE]->(w)
        MERGE (w)-[:TARGET]->(tgtProp)
        MERGE (w)-[:SOURCE_EVENT_FIELD]->(srcProp)
        RETURN w {.id, .operationId, .operator} as whereCondition
        """
        with self.session() as session:
            result = session.run(
                query,
                operation_id=operation_id,
                where_id=where_id,
                target_property_id=target_property_id,
                source_event_field_id=source_event_field_id,
                operator=operator,
            )
            record = result.single()
            return dict(record["whereCondition"]) if record else {}

    def delete_cqrs_where(self, where_id: str) -> bool:
        """Delete a CQRSWhere node."""
        query = """
        MATCH (w:CQRSWhere {id: $where_id})
        DETACH DELETE w
        RETURN count(w) as deleted
        """
        with self.session() as session:
            result = session.run(query, where_id=where_id)
            record = result.single()
            return record["deleted"] > 0 if record else False

    def get_events_for_cqrs(self, readmodel_id: str) -> list[dict[str, Any]]:
        """
        Get all available events that can be used for CQRS configuration.
        This includes events from all Bounded Contexts.
        """
        query = """
        MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
        OPTIONAL MATCH (evt)-[:HAS_PROPERTY]->(prop:Property)
        WITH bc, evt, collect(DISTINCT prop {.id, .name, .type}) as properties
        RETURN {
            id: evt.id,
            name: evt.name,
            bcId: bc.id,
            bcName: bc.name,
            properties: properties
        } as event
        ORDER BY bc.name, evt.name
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["event"]) for record in result]

    def get_readmodel_properties(self, readmodel_id: str) -> list[dict[str, Any]]:
        """
        Get all properties of a ReadModel for CQRS mapping configuration.
        """
        query = """
        MATCH (rm:ReadModel {id: $readmodel_id})-[:HAS_PROPERTY]->(prop:Property)
        RETURN prop {.id, .name, .type, .isRequired} as property
        ORDER BY prop.name
        """
        with self.session() as session:
            result = session.run(query, readmodel_id=readmodel_id)
            return [dict(record["property"]) for record in result]

    # =========================================================================
    # Graph Traversal & Analysis
    # =========================================================================

    def get_full_event_chain(self) -> list[dict[str, Any]]:
        """Get the full event chain: Command -> Event -> Policy -> Command."""
        query = """
        MATCH (cmd1:Command)-[:EMITS]->(evt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(cmd2:Command)
        MATCH (bc1:BoundedContext)-[:HAS_AGGREGATE]->(agg1:Aggregate)-[:HAS_COMMAND]->(cmd1)
        MATCH (bc2:BoundedContext)-[:HAS_POLICY]->(pol)
        RETURN {
            source_bc: bc1.name,
            source_command: cmd1.name,
            event: evt.name,
            target_bc: bc2.name,
            policy: pol.name,
            target_command: cmd2.name
        } as chain
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["chain"]) for record in result]

    def get_impact_analysis(self, event_name: str) -> dict[str, Any]:
        """Analyze the impact of changing a specific event."""
        query = """
        MATCH (evt:Event {name: $event_name})-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
        MATCH (pol)-[:INVOKES]->(cmd:Command)
        WITH evt, collect({bc: bc.name, policy: pol.name, command: cmd.name}) as impacts
        RETURN {
            event: evt.name,
            version: evt.version,
            affected_count: size(impacts),
            impacts: impacts
        } as analysis
        """
        with self.session() as session:
            result = session.run(query, event_name=event_name)
            record = result.single()
            return dict(record["analysis"]) if record else {}

    def get_graph_statistics(self) -> dict[str, int]:
        """Get statistics about the current graph."""
        query = """
        MATCH (n)
        WITH labels(n)[0] as label, count(n) as count
        RETURN collect({label: label, count: count}) as nodes
        """
        with self.session() as session:
            result = session.run(query)
            nodes = result.single()["nodes"]
            return {item["label"]: item["count"] for item in nodes}


# Singleton instance
_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """Get the singleton Neo4j client instance."""
    global _client
    if _client is None:
        _client = Neo4jClient()
    return _client

