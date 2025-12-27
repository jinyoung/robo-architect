"""
LLM Prompts for Event Storming Workflow

These prompts guide the LLM to generate Event Storming artifacts
from User Stories in a structured, domain-driven design approach.
"""

# =============================================================================
# System Prompts
# =============================================================================

SYSTEM_PROMPT = """You are an expert Domain-Driven Design (DDD) consultant specializing in Event Storming.
Your role is to help decompose software requirements into:
- Bounded Contexts (BC): Strategic design boundaries
- Aggregates: Tactical design units with transaction consistency
- Commands: Actions that change state
- Events: Facts that happened (past tense)
- Policies: Reactions to events that trigger commands
- ReadModels: Query models for CQRS pattern (Materialized Views)

Follow these principles:
1. Each Bounded Context should have a single, cohesive purpose
2. Aggregates enforce business invariants within a BC
3. Commands represent user intentions (verb form: CreateOrder)
4. Events represent completed actions (past tense: OrderCreated)
5. Policies connect BCs via event-driven communication
6. ReadModels provide query data from external BCs for Commands

When identifying Bounded Contexts, consider:
- Domain expertise differences (different teams, different knowledge)
- Scaling requirements (different load patterns)
- Data ownership (who owns what data)
- Business capability boundaries

Use consistent naming conventions:
- BC IDs: BC-NAME (e.g., BC-ORDER, BC-PAYMENT)
- Aggregate IDs: AGG-NAME (e.g., AGG-ORDER)
- Command IDs: CMD-VERB-NOUN (e.g., CMD-CANCEL-ORDER)
- Event IDs: EVT-NOUN-PASTVERB (e.g., EVT-ORDER-CANCELLED)
- Policy IDs: POL-ACTION-ON-TRIGGER (e.g., POL-REFUND-ON-CANCEL)
- ReadModel IDs: RM-BCNAME-NAME (e.g., RM-MYPAGE-ORDERSTATUS)
"""

# =============================================================================
# Bounded Context Identification
# =============================================================================

IDENTIFY_BC_PROMPT = """Analyze the following User Story and identify which Bounded Context(s) it belongs to.

User Story:
{user_story}

Existing Bounded Contexts in the system:
{existing_bcs}

Guidelines:
1. If the user story fits an existing BC, assign it there
2. If it requires a new BC, propose one with clear rationale
3. Consider if the story crosses multiple BCs (rare, but possible)
4. Don't create too many BCs - group related functionality

A user story typically belongs to ONE primary Bounded Context.
Consider the domain expertise, data ownership, and business capability.

Respond with:
1. The recommended Bounded Context (existing or new)
2. Your rationale for this assignment
3. Any concerns or alternatives to consider"""

IDENTIFY_BC_FROM_STORIES_PROMPT = """Analyze the following User Stories and identify candidate Bounded Contexts.

User Stories:
{user_stories}

Guidelines for identifying Bounded Contexts:
1. Group related functionality that shares domain concepts
2. Consider organizational boundaries (different teams)
3. Consider scaling requirements (different load patterns)
4. Consider data ownership (who owns what data)
5. Don't create too fine-grained BCs - they become microservices later

For each Bounded Context candidate, provide:
- A unique ID (BC-NAME, e.g., BC-ORDER)
- A descriptive name
- What it's responsible for
- Which user stories belong to it
- Rationale for why it should be separate

Output should be a list of BoundedContextCandidate objects."""

# =============================================================================
# User Story Breakdown
# =============================================================================

BREAKDOWN_USER_STORY_PROMPT = """Break down the following User Story into detailed components for Event Storming.

User Story:
{user_story}

Bounded Context: {bc_name}

Analyze this user story and identify:
1. Sub-tasks: What specific steps are needed to fulfill this story?
2. Domain Concepts: What key entities/concepts are involved?
3. Potential Aggregates: What consistency boundaries exist?
4. Potential Commands: What actions can users take?

Be specific and domain-focused. Think about:
- What data needs to be managed together (aggregate roots)
- What invariants must be maintained
- What events would be published when actions complete

Output should be a UserStoryBreakdown object."""

# =============================================================================
# Aggregate Extraction
# =============================================================================

EXTRACT_AGGREGATES_PROMPT = """Based on the User Story breakdown, identify Aggregates for this Bounded Context.

Bounded Context: {bc_name} (ID: {bc_id})
Description: {bc_description}

User Story Breakdowns (ONLY for this BC):
{breakdowns}

CRITICAL RULES:
1. An Aggregate belongs to EXACTLY ONE Bounded Context - never shared across BCs
2. Only consider the user stories listed above (which belong to THIS BC only)
3. If similar concepts exist in other BCs, they are DIFFERENT aggregates with DIFFERENT IDs
4. Aggregate IDs MUST include the BC name for uniqueness (e.g., AGG-{bc_id_short}-ORDER)

Guidelines for identifying Aggregates:
1. An Aggregate is a cluster of domain objects treated as a single unit
2. One entity is the Aggregate Root (entry point for all operations)
3. Aggregates enforce consistency boundaries (transactions)
4. Invariants (business rules) are checked within an aggregate
5. Other aggregates (even in other BCs) are referenced by ID only

For each Aggregate, provide:
- A unique ID: AGG-{bc_id_short}-NAME (e.g., AGG-ORDER-CART, AGG-INVENTORY-STOCK)
- The aggregate name (unique within this BC)
- The root entity name
- Key invariants it enforces
- A description of what it manages
- user_story_ids: List of User Story IDs that this aggregate implements (IMPORTANT for traceability!)

Example for Order BC:
- AGG-ORDER-CART: Shopping cart management, implements [US-001]
- AGG-ORDER-ORDER: Order lifecycle management, implements [US-001, US-002, US-003]

Example for Inventory BC:
- AGG-INVENTORY-STOCK: Stock level management, implements [US-009, US-010]

IMPORTANT: Each aggregate must list which user stories from this BC it implements.
This creates traceability from requirements to implementation.

Output should be a list of AggregateCandidate objects."""

# =============================================================================
# Command Extraction
# =============================================================================

EXTRACT_COMMANDS_PROMPT = """Identify Commands for the given Aggregate based on user story requirements.

Aggregate: {aggregate_name}
Aggregate ID: {aggregate_id}
Bounded Context: {bc_name}

User Stories for this Aggregate:
{user_story_context}

Guidelines for identifying Commands:
1. Commands represent user/system intentions to change state
2. Name commands as imperative verbs (CreateOrder, CancelOrder)
3. Each command should map to a user action or system trigger
4. Commands are handled by exactly one aggregate
5. IMPORTANT: Track which user story each command implements

For each Command, provide:
- A unique ID: CMD-BCNAME-VERB-NOUN (e.g., CMD-ORDER-CANCEL-ORDER)
- The command name in PascalCase
- Who/what triggers this command (user, system, policy)
- A description of what the command does
- user_story_ids: List of User Story IDs that this command directly implements

Example:
- CMD-ORDER-PLACE-ORDER: PlaceOrder, implements [US-001]
- CMD-ORDER-CANCEL-ORDER: CancelOrder, implements [US-002]

This creates traceability: UserStory -> Command

Output should be a list of CommandCandidate objects."""

# =============================================================================
# Event Extraction
# =============================================================================

EXTRACT_EVENTS_PROMPT = """Identify Events emitted by Commands in this Aggregate.

Aggregate: {aggregate_name}
Bounded Context: {bc_name}
Commands (with their user stories):
{commands}

Guidelines for identifying Events:
1. Events represent facts that happened (past tense)
2. Name events as NounPastVerb (OrderCreated, PaymentProcessed)
3. Every command should emit at least one event on success
4. Events are immutable facts - they cannot be changed
5. IMPORTANT: Inherit user_story_ids from the command that emits this event

For each Event, provide:
- A unique ID: EVT-BCNAME-NOUN-PASTVERB (e.g., EVT-ORDER-ORDER-CANCELLED)
- The event name in PascalCase
- A description of what happened
- user_story_ids: List of User Story IDs (inherited from the emitting command)

Example:
- EVT-ORDER-ORDER-PLACED: OrderPlaced, implements [US-001]
- EVT-ORDER-ORDER-CANCELLED: OrderCancelled, implements [US-002]

This creates traceability: UserStory -> Command -> Event

Output should be a list of EventCandidate objects."""

# =============================================================================
# Policy Identification
# =============================================================================

IDENTIFY_POLICIES_PROMPT = """Identify Policies for cross-Bounded Context communication.

Available Events in the system:
{events}

Available Commands in each BC:
{commands_by_bc}

Bounded Contexts:
{bounded_contexts}

Guidelines for identifying Policies:
1. Policies react to Events from OTHER Bounded Contexts
2. A Policy triggers a Command in its OWN Bounded Context
3. Pattern: "When [Event] then [Command]"
4. Policies enable loose coupling between BCs

For each Policy, provide:
- A unique ID (POL-ACTION-ON-TRIGGER, e.g., POL-REFUND-ON-CANCEL)
- A descriptive name
- The triggering event (from another BC)
- The target BC where this policy lives
- The command it invokes (in the same BC as the policy)
- A description in "When X then Y" format

Common patterns:
- When OrderPlaced → ProcessPayment (Payment BC)
- When OrderCancelled → ProcessRefund (Payment BC)
- When OrderCancelled → RestoreStock (Inventory BC)

Output should be a list of PolicyCandidate objects."""

# =============================================================================
# Review Prompts
# =============================================================================

REVIEW_BC_PROMPT = """Review the proposed Bounded Contexts for this Event Storming session.

Proposed Bounded Contexts:
{bc_candidates}

Original User Stories:
{user_stories}

Please review and provide feedback:
1. Are the BC boundaries appropriate?
2. Are any BCs too large (should be split)?
3. Are any BCs too small (should be merged)?
4. Are user stories correctly assigned?

If approved, respond with "APPROVED".
If changes needed, describe the changes."""

REVIEW_AGGREGATES_PROMPT = """Review the proposed Aggregates for Bounded Context: {bc_name}

Proposed Aggregates:
{aggregates}

Please review and provide feedback:
1. Are aggregate boundaries correct?
2. Are invariants properly identified?
3. Should any aggregates be merged or split?

If approved, respond with "APPROVED".
If changes needed, describe the changes."""

REVIEW_POLICIES_PROMPT = """Review the proposed Policies for cross-BC communication.

Proposed Policies:
{policies}

Please review and provide feedback:
1. Are the event-to-command mappings correct?
2. Are there missing policies?
3. Are there unnecessary policies?

If approved, respond with "APPROVED".
If changes needed, describe the changes."""

# =============================================================================
# Property Extraction Prompts
# =============================================================================

EXTRACT_AGGREGATE_PROPERTIES_PROMPT = """Identify the member fields (properties) for the Aggregate Root.

Aggregate: {aggregate_name} (ID: {aggregate_id})
Bounded Context: {bc_name}
Root Entity: {root_entity}
Description: {description}
Invariants: {invariants}

Related User Stories:
{user_stories}

Guidelines for identifying Aggregate Root properties:
1. Include identity fields (e.g., orderId, customerId)
2. Include state fields that enforce invariants
3. Include value objects as nested types
4. Include timestamps (createdAt, updatedAt) where appropriate
5. Use appropriate data types (String, Integer, Long, Date, Money, List<T>, etc.)

For each Property, provide:
- A unique ID: PROP-AGGREGATE_ID-FIELDNAME (e.g., PROP-AGG-ORDER-ORDERID)
- Field name in camelCase (e.g., orderId, totalAmount)
- Data type (String, Integer, Long, Double, Date, Boolean, Money, List<ItemType>, etc.)
- Whether it's required (true/false)
- Brief description

Output should be a list of PropertyCandidate objects."""

EXTRACT_COMMAND_PROPERTIES_PROMPT = """Identify the request body fields (properties) for the Command.

Command: {command_name} (ID: {command_id})
Aggregate: {aggregate_name}
Bounded Context: {bc_name}
Actor: {actor}
Description: {description}

Related User Stories:
{user_stories}

Guidelines for identifying Command request body properties:
1. Include all input parameters needed to execute this command
2. Do NOT include identity fields that are in the URL path (e.g., orderId in /orders/{{orderId}}/cancel)
3. Include payload data from the actor's input
4. Use appropriate data types

For each Property, provide:
- A unique ID: PROP-COMMAND_ID-FIELDNAME (e.g., PROP-CMD-PLACE-ORDER-ITEMS)
- Field name in camelCase (e.g., items, quantity, shippingAddress)
- Data type (String, Integer, Long, Double, Date, Boolean, List<ItemType>, etc.)
- Whether it's required (true/false)
- Brief description

Output should be a list of PropertyCandidate objects."""

EXTRACT_EVENT_PROPERTIES_PROMPT = """Identify the payload attributes (properties) for the Event.

Event: {event_name} (ID: {event_id})
Aggregate: {aggregate_name}
Bounded Context: {bc_name}
Triggered by Command: {command_name}

Command Request Properties:
{command_properties}

Aggregate Properties:
{aggregate_properties}

Guidelines for identifying Event payload properties:
1. Include data that downstream consumers need
2. Include the aggregate identity (e.g., orderId)
3. Include relevant state changes that occurred
4. Events should be self-contained - include enough context
5. Include timestamp of when the event occurred

For each Property, provide:
- A unique ID: PROP-EVENT_ID-FIELDNAME (e.g., PROP-EVT-ORDER-PLACED-ORDERID)
- Field name in camelCase (e.g., orderId, status, changedAt)
- Data type (String, Integer, Long, Double, Date, Boolean, etc.)
- Whether it's required (true/false)
- Brief description

Output should be a list of PropertyCandidate objects."""

# =============================================================================
# ReadModel Extraction Prompts (CQRS / Query Model)
# =============================================================================

EXTRACT_READMODELS_PROMPT = """Identify ReadModels (Query Models / Materialized Views) needed for the Commands in this BC.

Bounded Context: {bc_name} (ID: {bc_id})
Description: {bc_description}

Commands in this BC (with their required data):
{commands}

Other Bounded Contexts and their Events:
{other_bc_events}

User Stories:
{user_stories}

WHAT IS A READMODEL?
A ReadModel is needed when a Command requires data from OTHER Bounded Contexts to execute.
For example:
- "PlaceOrder" command needs product information from Product BC
- "CreateInvoice" command needs customer and order details from multiple BCs

WHEN TO CREATE A READMODEL:
1. User needs to VIEW data before executing a Command
2. Command requires data that doesn't exist in the current BC
3. Data needs to be queried/joined from multiple sources
4. Performance requires pre-computed/cached data

PROVISIONING TYPES:
- CQRS: Subscribe to Events and maintain a local copy (Materialized View)
- API: Call other BC's API at query time
- GraphQL: Use GraphQL federation
- SharedDB: Direct DB access (anti-pattern, use only for legacy)

For each ReadModel, provide:
- A unique ID: RM-BCNAME-NAME (e.g., RM-ORDER-PRODUCTCATALOG)
- A descriptive name in PascalCase
- What data it provides
- Provisioning type (default: CQRS)
- source_bc_ids: Which BCs the data comes from
- source_event_ids: Which Events populate this ReadModel (for CQRS)
- supports_command_ids: Which Commands use this data
- user_story_ids: Which User Stories require this data

Example for MyPage BC:
- RM-MYPAGE-ORDERSTATUS: Aggregates order and delivery status
  - Sources: BC-ORDER (OrderPlaced), BC-DELIVERY (DeliveryStarted, DeliveryCompleted)
  - Supports: CMD-MYPAGE-VIEW-ORDERS

IMPORTANT: Only create ReadModels when there's a clear need for external data.
Don't create ReadModels for data that already exists in the local BC.

NOTE: Do NOT generate cqrs_config in this step. Leave it as null/None.
CQRS configuration will be added later through the UI after properties are defined.

Output should be a list of ReadModelCandidate objects with the following fields:
- id: Unique ID like RM-BCNAME-NAME
- name: ReadModel name in PascalCase
- description: What data this ReadModel provides
- provisioning_type: One of 'CQRS', 'API', 'GraphQL', 'SharedDB' (default: 'CQRS')
- source_bc_ids: List of BC IDs where data comes from
- source_event_ids: List of Event IDs (can be empty, will be configured later)
- supports_command_ids: List of Command IDs this ReadModel supports
- user_story_ids: List of User Story IDs
- cqrs_config: null (will be configured later via UI)"""

EXTRACT_READMODEL_PROPERTIES_PROMPT = """Identify the properties (fields) for the ReadModel.

ReadModel: {readmodel_name} (ID: {readmodel_id})
Bounded Context: {bc_name}
Description: {description}
Provisioning Type: {provisioning_type}

Source Events (for CQRS):
{source_events}

Commands this ReadModel supports:
{supported_commands}

User Stories:
{user_stories}

Guidelines for identifying ReadModel properties:
1. Include fields needed by the supported Commands
2. Include identifier fields for correlation (e.g., orderId, customerId)
3. Include status/state fields that users need to see
4. Include fields from source events that will populate this ReadModel
5. Use appropriate data types (String, Long, Date, etc.)

For CQRS, consider:
- Which fields come from which source events
- Which fields are set on CREATE vs UPDATE
- Which fields are used as WHERE conditions

For each Property, provide:
- A unique ID: PROP-READMODEL_ID-FIELDNAME (e.g., PROP-RM-MYPAGE-ORDERID)
- Field name in camelCase (e.g., orderId, productName, orderStatus)
- Data type (String, Long, Integer, Date, Boolean, etc.)
- Whether it's required (true/false)
- Brief description

Output should be a list of PropertyCandidate objects."""

EXTRACT_CQRS_CONFIG_PROMPT = """Generate CQRS configuration for the ReadModel.

ReadModel: {readmodel_name} (ID: {readmodel_id})
Bounded Context: {bc_name}
Description: {description}

ReadModel Properties:
{readmodel_properties}

Source Events (with their properties):
{source_events_with_properties}

Generate CQRS rules that define:
1. CREATE WHEN [Event]: Which event creates a new record in the ReadModel
2. UPDATE WHEN [Event]: Which events update existing records
3. For each rule, define SET mappings: readModelField = eventField or static value
4. For UPDATE rules, define WHERE condition: readModelField = eventField

Example Configuration:
{{
  "rules": [
    {{
      "action": "CREATE",
      "whenEvent": "EVT-ORDER-PLACED",
      "setMappings": [
        {{"readModelField": "orderId", "operator": "=", "source": "event", "eventField": "id"}},
        {{"readModelField": "productId", "operator": "=", "source": "event", "eventField": "productId"}},
        {{"readModelField": "orderStatus", "operator": "=", "source": "value", "value": "주문됨"}}
      ]
    }},
    {{
      "action": "UPDATE",
      "whenEvent": "EVT-DELIVERY-STARTED",
      "setMappings": [
        {{"readModelField": "deliveryStatus", "operator": "=", "source": "value", "value": "배송됨"}}
      ],
      "whereCondition": {{
        "readModelField": "orderId",
        "operator": "=",
        "eventField": "orderId"
      }}
    }}
  ]
}}

Output should be a CQRSConfig object."""

# =============================================================================
# UI Wireframe Generation Prompts
# =============================================================================

GENERATE_UI_PROMPT = """Generate a UI wireframe for the Command or ReadModel based on User Story requirements.

Target: {target_type} - {target_name} (ID: {target_id})
Bounded Context: {bc_name}
Description: {description}

User Story (with UI requirements):
{user_story}

Command/ReadModel Properties:
{properties}

Related Aggregate:
{aggregate_info}

Guidelines for generating UI wireframe:
1. Create a simple, clean wireframe using Vue template HTML
2. Use semantic HTML elements (form, input, button, label, etc.)
3. Map properties to appropriate form fields
4. Add placeholder text and labels in Korean
5. Include action buttons (submit, cancel) for Commands
6. Include data display sections for ReadModels
7. Use CSS classes for styling: form-group, btn-group, etc.

Template structure for COMMAND (input form):
- Title/header showing the action
- Form fields for each input property
- Submit and Cancel buttons

Template structure for READMODEL (data display):
- Title/header showing what data is displayed
- Data fields/sections
- Refresh or action buttons if needed

Generate a Vue template HTML string that can be rendered as a wireframe.
The template should be self-contained and use only standard HTML elements.
Do NOT include <script> or <style> tags - only template content.

Example for PlaceOrder Command:
<div class="wireframe">
  <h2>주문하기</h2>
  <form class="form">
    <div class="form-group">
      <label>상품</label>
      <input type="text" placeholder="상품 선택" />
    </div>
    <div class="form-group">
      <label>수량</label>
      <input type="number" placeholder="1" />
    </div>
    <div class="btn-group">
      <button type="submit">주문</button>
      <button type="button">취소</button>
    </div>
  </form>
</div>

Output should be a UICandidate object with a valid 'template' field containing Vue template HTML."""

