// ============================================================
// Event Storming Impact Analysis - Relationship Types
// ============================================================
// 7가지 관계 타입의 의미, 속성 및 생성 패턴을 정의합니다.
// 
// 핵심 패턴:
//   Event가 발생하면 → 다른 BC의 Policy가 반응 → 해당 BC의 Command 호출
// ============================================================

// ############################################################
// 1. IMPLEMENTS
// ############################################################
// 방향: UserStory → BoundedContext / Aggregate
// 의미: UserStory가 특정 BC 또는 Aggregate에서 구현됨
//
// 속성:
//   - createdAt: DateTime
//   - confidence: Float (AI 추론 신뢰도, 0.0 ~ 1.0)
// ############################################################

MATCH (us:UserStory {id: "US-001"})
MATCH (bc:BoundedContext {id: "BC-ORDER"})
CREATE (us)-[:IMPLEMENTS {
    createdAt: datetime(),
    confidence: 0.95
}]->(bc);


// ############################################################
// 2. HAS_AGGREGATE
// ############################################################
// 방향: BoundedContext → Aggregate
// 의미: BC가 해당 Aggregate를 포함함
//
// 속성:
//   - isPrimary: Boolean (주요 Aggregate 여부)
// ############################################################

MATCH (bc:BoundedContext {id: "BC-ORDER"})
MATCH (agg:Aggregate {id: "AGG-ORDER"})
CREATE (bc)-[:HAS_AGGREGATE {
    isPrimary: true
}]->(agg);


// ############################################################
// 3. HAS_POLICY
// ############################################################
// 방향: BoundedContext → Policy
// 의미: BC가 해당 Policy를 소유함
//       Policy는 외부 Event에 반응하여 자신의 Command를 호출
// ############################################################

MATCH (bc:BoundedContext {id: "BC-PAYMENT"})
MATCH (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
CREATE (bc)-[:HAS_POLICY]->(pol);


// ############################################################
// 4. HAS_COMMAND
// ############################################################
// 방향: Aggregate → Command
// 의미: Aggregate가 해당 Command를 처리함
//
// 속성:
//   - isIdempotent: Boolean
// ############################################################

MATCH (agg:Aggregate {id: "AGG-ORDER"})
MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
CREATE (agg)-[:HAS_COMMAND {
    isIdempotent: true
}]->(cmd);


// ############################################################
// 5. EMITS
// ############################################################
// 방향: Command → Event
// 의미: Command 실행 결과로 Event가 발생함
//
// 속성:
//   - isGuaranteed: Boolean
// ############################################################

MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"})
CREATE (cmd)-[:EMITS {
    isGuaranteed: true
}]->(evt);


// ############################################################
// 6. TRIGGERS
// ############################################################
// 방향: Event → Policy (다른 BC의 Policy)
// 의미: Event 발생 시 다른 BC의 Policy가 반응
//
// 이것이 Event Storming의 핵심 Cross-BC 통신 패턴:
//   BC-A의 Event → BC-B의 Policy → BC-B의 Command
//
// 속성:
//   - priority: Integer
//   - isEnabled: Boolean
// ############################################################

MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"})
MATCH (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
CREATE (evt)-[:TRIGGERS {
    priority: 1,
    isEnabled: true
}]->(pol);


// ############################################################
// 7. INVOKES
// ############################################################
// 방향: Policy → Command (같은 BC 내의 Command)
// 의미: Policy가 자신의 BC에 있는 Command를 호출
//
// 속성:
//   - isAsync: Boolean
// ############################################################

MATCH (pol:Policy {id: "POL-REFUND-ON-CANCEL"})
MATCH (cmd:Command {id: "CMD-PROCESS-REFUND"})
CREATE (pol)-[:INVOKES {
    isAsync: true
}]->(cmd);


// ############################################################
// 8. DEPENDS_ON (BC간 의존성)
// ############################################################
// 방향: BoundedContext → BoundedContext
// 의미: BC 간의 이벤트 기반 의존 관계
//       (Event → Policy 관계에서 자동 유추 가능)
//
// 속성:
//   - integrationPattern: String ("event", "sync")
// ############################################################

MATCH (bc1:BoundedContext {id: "BC-ORDER"})
MATCH (bc2:BoundedContext {id: "BC-PAYMENT"})
CREATE (bc1)-[:DEPENDS_ON {
    integrationPattern: "event"
}]->(bc2);


// ############################################################
// 9. HAS_PROPERTY
// ############################################################
// 방향: Aggregate / Command / Event → Property
// 의미: DDD 객체가 해당 속성을 가짐
//       - Aggregate: Root Entity의 멤버 필드
//       - Command: Request Body 속성
//       - Event: Payload 속성
// ############################################################

MATCH (agg:Aggregate {id: "AGG-ORDER"})
MATCH (prop:Property {id: "PROP-AGG-ORDER-ORDERID"})
CREATE (agg)-[:HAS_PROPERTY]->(prop);

MATCH (agg:Aggregate {id: "AGG-ORDER"})
MATCH (prop:Property {id: "PROP-AGG-ORDER-TOTALAMOUNT"})
CREATE (agg)-[:HAS_PROPERTY]->(prop);

MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
MATCH (prop:Property {id: "PROP-CMD-CANCEL-ORDER-REASON"})
CREATE (cmd)-[:HAS_PROPERTY]->(prop);

MATCH (evt:Event {id: "EVT-ORDER-CANCELLED"})
MATCH (prop:Property {id: "PROP-EVT-ORDER-CANCELLED-CANCELLEDAT"})
CREATE (evt)-[:HAS_PROPERTY]->(prop);


// ############################################################
// 10. HAS_READMODEL
// ############################################################
// 방향: BoundedContext → ReadModel
// 의미: BC가 해당 ReadModel을 소유함
//       ReadModel은 다른 BC의 Event를 구독하여 Query용 데이터 저장
// ############################################################

MATCH (bc:BoundedContext {id: "BC-MYPAGE"})
MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
CREATE (bc)-[:HAS_READMODEL]->(rm);


// ############################################################
// 11. POPULATES
// ############################################################
// 방향: Event → ReadModel
// 의미: Event가 ReadModel에 데이터를 적재함 (CQRS 패턴)
//       CREATE/UPDATE/DELETE 규칙에 따라 ReadModel 갱신
//
// 속성:
//   - action: String ("CREATE", "UPDATE", "DELETE")
//   - mappingConfig: String (JSON) - 필드 매핑 설정
// ############################################################

MATCH (evt:Event {id: "EVT-ORDER-PLACED"})
MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
CREATE (evt)-[:POPULATES {
    action: "CREATE",
    mappingConfig: '{"orderId": "id", "productId": "productId", "orderStatus": "주문됨"}'
}]->(rm);

MATCH (evt:Event {id: "EVT-DELIVERY-STARTED"})
MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
CREATE (evt)-[:POPULATES {
    action: "UPDATE",
    mappingConfig: '{"deliveryStatus": "배송됨"}',
    whereCondition: '{"orderId": "orderId"}'
}]->(rm);


// ############################################################
// 12. SUPPORTS
// ############################################################
// 방향: ReadModel → Command
// 의미: ReadModel이 해당 Command 수행에 필요한 데이터를 제공
//       User가 ReadModel 조회 후 Command 실행하는 시나리오
// ############################################################

MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
CREATE (rm)-[:SUPPORTS]->(cmd);


// ReadModel에 대한 HAS_PROPERTY 관계
MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
MATCH (prop:Property {id: "PROP-RM-MYPAGE-ORDERID"})
CREATE (rm)-[:HAS_PROPERTY]->(prop);

MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
MATCH (prop:Property {id: "PROP-RM-MYPAGE-PRODUCTID"})
CREATE (rm)-[:HAS_PROPERTY]->(prop);

MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
MATCH (prop:Property {id: "PROP-RM-MYPAGE-ORDERSTATUS"})
CREATE (rm)-[:HAS_PROPERTY]->(prop);

MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
MATCH (prop:Property {id: "PROP-RM-MYPAGE-DELIVERYSTATUS"})
CREATE (rm)-[:HAS_PROPERTY]->(prop);


// ############################################################
// 13. HAS_UI
// ############################################################
// 방향: BoundedContext → UI
// 의미: BC가 해당 UI 와이어프레임을 소유함
//       UI는 Command 또는 ReadModel에 부착되어 화면 구조 정의
// ############################################################

MATCH (bc:BoundedContext {id: "BC-ORDER"})
MATCH (ui:UI {id: "UI-ORDER-CANCELORDER"})
CREATE (bc)-[:HAS_UI]->(ui);


// ############################################################
// 14. ATTACHED_TO
// ############################################################
// 방향: UI → Command / ReadModel
// 의미: UI가 특정 Command 또는 ReadModel에 부착됨
//       UI는 해당 Command의 입력 폼 또는 ReadModel의 조회 화면
// ############################################################

MATCH (ui:UI {id: "UI-ORDER-CANCELORDER"})
MATCH (cmd:Command {id: "CMD-CANCEL-ORDER"})
CREATE (ui)-[:ATTACHED_TO]->(cmd);


// ############################################################
// 15. HAS_CQRS
// ############################################################
// 방향: ReadModel → CQRSConfig
// 의미: ReadModel의 CQRS 설정 연결
// ############################################################

// Example:
// MATCH (rm:ReadModel {id: "RM-MYPAGE-ORDER-STATUS"})
// MATCH (cqrs:CQRSConfig {id: "CQRS-RM-MYPAGE-ORDER-STATUS"})
// CREATE (rm)-[:HAS_CQRS]->(cqrs);


// ############################################################
// 16. HAS_OPERATION
// ############################################################
// 방향: CQRSConfig → CQRSOperation
// 의미: CQRS 설정이 포함하는 작업 (INSERT/UPDATE/DELETE)
// ############################################################

// Example:
// MATCH (cqrs:CQRSConfig {id: "CQRS-RM-MYPAGE-ORDER-STATUS"})
// MATCH (op:CQRSOperation {id: "CQRS-OP-RM-MYPAGE-INSERT-ORDERPLACED"})
// CREATE (cqrs)-[:HAS_OPERATION]->(op);


// ############################################################
// 17. TRIGGERED_BY
// ############################################################
// 방향: CQRSOperation → Event
// 의미: 이 작업을 트리거하는 이벤트
// ############################################################

// Example:
// MATCH (op:CQRSOperation {id: "CQRS-OP-RM-MYPAGE-INSERT-ORDERPLACED"})
// MATCH (evt:Event {id: "EVT-ORDER-PLACED"})
// CREATE (op)-[:TRIGGERED_BY]->(evt);


// ############################################################
// 18. HAS_MAPPING
// ############################################################
// 방향: CQRSOperation → CQRSMapping
// 의미: 작업에 포함된 필드 매핑
// ############################################################

// Example:
// MATCH (op:CQRSOperation {id: "CQRS-OP-RM-MYPAGE-INSERT-ORDERPLACED"})
// MATCH (m:CQRSMapping {id: "CQRS-MAP-RM-MYPAGE-ORDERID"})
// CREATE (op)-[:HAS_MAPPING]->(m);


// ############################################################
// 19. HAS_WHERE
// ############################################################
// 방향: CQRSOperation → CQRSWhere
// 의미: UPDATE/DELETE 작업의 조건절
// ############################################################

// Example:
// MATCH (op:CQRSOperation {id: "CQRS-OP-RM-MYPAGE-UPDATE-DELIVERYSTARTED"})
// MATCH (w:CQRSWhere {id: "CQRS-WHERE-RM-MYPAGE-UPDATE-ORDERID"})
// CREATE (op)-[:HAS_WHERE]->(w);


// ############################################################
// 20. SOURCE (for CQRSMapping)
// ############################################################
// 방향: CQRSMapping → Property (Event의 속성)
// 의미: 매핑의 소스 필드 (이벤트에서 가져올 값)
// ############################################################

// Example:
// MATCH (m:CQRSMapping {id: "CQRS-MAP-RM-MYPAGE-ORDERID"})
// MATCH (prop:Property {id: "PROP-EVT-ORDER-ID"})
// CREATE (m)-[:SOURCE]->(prop);


// ############################################################
// 21. TARGET (for CQRSMapping and CQRSWhere)
// ############################################################
// 방향: CQRSMapping/CQRSWhere → Property (ReadModel의 속성)
// 의미: 매핑의 타겟 필드 또는 WHERE 조건의 비교 필드
// ############################################################

// Example:
// MATCH (m:CQRSMapping {id: "CQRS-MAP-RM-MYPAGE-ORDERID"})
// MATCH (prop:Property {id: "PROP-RM-MYPAGE-ORDERID"})
// CREATE (m)-[:TARGET]->(prop);


// ============================================================
// Event Storming Flow 시각화
// ============================================================
//
//  ┌─────────────────────────────────────────────────────────┐
//  │  BC: Order                                              │
//  │  ┌───────────┐    ┌─────────────┐    ┌──────────────┐  │
//  │  │ Aggregate │───>│   Command   │───>│    Event     │  │
//  │  │   Order   │    │ CancelOrder │    │OrderCancelled│──┼──┐
//  │  └───────────┘    └─────────────┘    └──────────────┘  │  │
//  └─────────────────────────────────────────────────────────┘  │
//                                                               │
//  ┌─────────────────────────────────────────────────────────┐  │
//  │  BC: Payment                                            │  │
//  │  ┌──────────────────┐    ┌───────────────┐              │  │
//  │  │      Policy      │<───┤   (Event)     │<─────────────┼──┘
//  │  │RefundOnCancel    │    │               │              │
//  │  └────────┬─────────┘    └───────────────┘              │
//  │           │                                             │
//  │           ▼                                             │
//  │  ┌───────────────┐    ┌──────────────────┐              │
//  │  │    Command    │───>│      Event       │              │
//  │  │ ProcessRefund │    │ RefundProcessed  │              │
//  │  └───────────────┘    └──────────────────┘              │
//  └─────────────────────────────────────────────────────────┘
//
// ============================================================
