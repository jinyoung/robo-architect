// ============================================================
// Event Storming Impact Analysis - Node Types Definition
// ============================================================
// 각 노드 타입의 속성 정의 및 생성 패턴을 문서화합니다.
// ============================================================

// ############################################################
// 1. Requirement (요구사항)
// ############################################################
// 설명: 원본 요구사항 문서에서 추출한 요구사항
//
// 필수 속성:
//   - id: String (고유 식별자)
//   - title: String (요구사항 제목)
//
// 선택 속성:
//   - description: String (상세 설명)
//   - source: String (출처 문서명)
//   - createdAt: DateTime
//   - priority: String ("high", "medium", "low")
// ############################################################

CREATE (r:Requirement {
    id: "REQ-001",
    title: "주문 관리 기능",
    description: "고객이 주문을 생성, 조회, 취소할 수 있어야 한다",
    source: "기능요구사항서 v1.0",
    createdAt: datetime(),
    priority: "high"
});


// ############################################################
// 2. UserStory (사용자 스토리)
// ############################################################
// 설명: "As a [role], I want [action], so that [benefit]" 형식
// 관계: IMPLEMENTS → BoundedContext, Aggregate
//
// 필수 속성:
//   - id: String (고유 식별자)
//   - role: String (사용자 역할)
//   - action: String (원하는 행동)
//
// 선택 속성:
//   - benefit: String (기대 효과)
//   - priority: String
//   - status: String ("draft", "approved", "implemented")
//   - acceptanceCriteria: List<String>
// ############################################################

CREATE (us:UserStory {
    id: "US-001",
    role: "customer",
    action: "cancel my order",
    benefit: "I can get a refund if I change my mind",
    priority: "high",
    status: "approved"
});


// ############################################################
// 3. BoundedContext (바운디드 컨텍스트)
// ############################################################
// 설명: 전략적 설계 단위, 도메인의 논리적 경계
// 관계: 
//   - HAS_AGGREGATE → Aggregate
//   - HAS_POLICY → Policy
//   - DEPENDS_ON ↔ BoundedContext
//
// 필수 속성:
//   - id: String (고유 식별자)
//   - name: String (컨텍스트 이름)
//
// 선택 속성:
//   - description: String
//   - owner: String (담당 팀)
// ############################################################

CREATE (bc:BoundedContext {
    id: "BC-ORDER",
    name: "Order",
    description: "주문 생성, 수정, 취소 및 주문 상태 관리",
    owner: "Order Team"
});


// ############################################################
// 4. Aggregate (애그리게이트)
// ############################################################
// 설명: 전술적 설계 핵심, 트랜잭션 일관성 경계
// 관계:
//   - HAS_COMMAND → Command
//
// 필수 속성:
//   - id: String
//   - name: String
//
// 선택 속성:
//   - rootEntity: String
//   - invariants: List<String>
// ############################################################

CREATE (agg:Aggregate {
    id: "AGG-ORDER",
    name: "Order",
    rootEntity: "Order",
    invariants: [
        "주문 총액은 0보다 커야 함",
        "배송 시작 후에는 취소 불가"
    ]
});


// ############################################################
// 5. Command (커맨드)
// ############################################################
// 설명: 사용자의 의도를 표현하는 명령
// 관계:
//   - EMITS → Event
//
// 필수 속성:
//   - id: String
//   - name: String (동사형)
//
// 선택 속성:
//   - actor: String
//   - inputSchema: String (JSON)
// ############################################################

CREATE (cmd:Command {
    id: "CMD-CANCEL-ORDER",
    name: "CancelOrder",
    actor: "customer",
    inputSchema: '{"orderId": "string", "reason": "string"}'
});


// ############################################################
// 6. Event (이벤트)
// ############################################################
// 설명: 도메인에서 발생한 사실 (과거형)
// 관계:
//   - TRIGGERS → Policy (다른 BC의 Policy)
//
// 필수 속성:
//   - id: String
//   - name: String (과거형)
//   - version: String
//
// 선택 속성:
//   - schema: String (JSON)
//   - isBreaking: Boolean
// ############################################################

CREATE (evt:Event {
    id: "EVT-ORDER-CANCELLED",
    name: "OrderCancelled",
    version: "1.0.0",
    schema: '{"orderId": "string", "cancelledAt": "datetime", "reason": "string"}',
    isBreaking: false
});


// ############################################################
// 7. Policy (폴리시)
// ############################################################
// 설명: 다른 BC의 이벤트에 반응하여 자신의 Command를 호출
//       "When [Event] then [Command]" 패턴
// 관계:
//   - INVOKES → Command (자신의 BC에 있는)
//
// 필수 속성:
//   - id: String
//   - name: String
//
// 선택 속성:
//   - condition: String (트리거 조건)
//   - description: String
// ############################################################

CREATE (pol:Policy {
    id: "POL-REFUND-ON-CANCEL",
    name: "RefundOnOrderCancellation",
    condition: "OrderCancelled received",
    description: "주문 취소 이벤트 수신 시 환불 처리"
});


// ############################################################
// 8. Property (속성/필드)
// ############################################################
// 설명: DDD 객체(Aggregate, Command, Event)의 멤버 필드
// 관계:
//   - HAS_PROPERTY ← Aggregate / Command / Event
//
// 필수 속성:
//   - id: String
//   - name: String (필드명)
//   - type: String (데이터 타입)
//
// 선택 속성:
//   - description: String
//   - isRequired: Boolean
//   - parentId: String (부모 객체 ID)
//   - parentType: String ("Aggregate", "Command", "Event")
// ############################################################

CREATE (prop:Property {
    id: "PROP-AGG-ORDER-ORDERID",
    name: "orderId",
    type: "String",
    description: "주문 고유 식별자",
    isRequired: true,
    parentId: "AGG-ORDER",
    parentType: "Aggregate"
});

CREATE (prop2:Property {
    id: "PROP-AGG-ORDER-TOTALAMOUNT",
    name: "totalAmount",
    type: "Money",
    description: "주문 총액",
    isRequired: true,
    parentId: "AGG-ORDER",
    parentType: "Aggregate"
});

CREATE (prop3:Property {
    id: "PROP-CMD-CANCEL-ORDER-REASON",
    name: "reason",
    type: "String",
    description: "취소 사유",
    isRequired: false,
    parentId: "CMD-CANCEL-ORDER",
    parentType: "Command"
});

CREATE (prop4:Property {
    id: "PROP-EVT-ORDER-CANCELLED-CANCELLEDAT",
    name: "cancelledAt",
    type: "DateTime",
    description: "취소 시각",
    isRequired: true,
    parentId: "EVT-ORDER-CANCELLED",
    parentType: "Event"
});


// ############################################################
// 9. ReadModel (읽기 모델 - 녹색 스티커)
// ############################################################
// 설명: CQRS 패턴에서 Query를 위한 Materialized View
//       다른 BC의 이벤트를 구독하여 데이터를 복제/조인하여 저장
//       User Story에서 "데이터를 읽고 Command를 수행" 시나리오 지원
// 관계:
//   - HAS_READMODEL ← BoundedContext
//   - POPULATES ← Event (이벤트로부터 데이터 적재)
//   - SUPPORTS → Command (이 ReadModel 데이터로 Command 수행 가능)
//   - HAS_PROPERTY → Property
//
// 필수 속성:
//   - id: String (고유 식별자, RM-BCNAME-NAME 형식)
//   - name: String (ReadModel 이름)
//
// 선택 속성:
//   - description: String
//   - provisioningType: String ("CQRS", "API", "GraphQL", "SharedDB")
//   - cqrsConfig: String (JSON) - CQRS 설정 (CREATE/UPDATE WHEN 규칙)
// ############################################################

CREATE (rm:ReadModel {
    id: "RM-MYPAGE-ORDER-STATUS",
    name: "MyPageOrderStatus",
    description: "마이페이지에서 주문 및 배송 상태를 조회하기 위한 읽기 모델",
    provisioningType: "CQRS",
    cqrsConfig: '{
        "rules": [
            {
                "action": "CREATE",
                "whenEvent": "EVT-ORDER-PLACED",
                "setMappings": [
                    {"readModelField": "orderId", "operator": "=", "source": "event", "eventField": "id"},
                    {"readModelField": "productId", "operator": "=", "source": "event", "eventField": "productId"},
                    {"readModelField": "orderStatus", "operator": "=", "source": "value", "value": "주문됨"}
                ]
            },
            {
                "action": "UPDATE",
                "whenEvent": "EVT-DELIVERY-STARTED",
                "setMappings": [
                    {"readModelField": "deliveryStatus", "operator": "=", "source": "value", "value": "배송됨"}
                ],
                "whereCondition": {
                    "readModelField": "orderId",
                    "operator": "=",
                    "eventField": "orderId"
                }
            }
        ]
    }'
});

CREATE (prop_rm1:Property {
    id: "PROP-RM-MYPAGE-ORDERID",
    name: "orderId",
    type: "Long",
    description: "주문 ID",
    isRequired: true,
    parentId: "RM-MYPAGE-ORDER-STATUS",
    parentType: "ReadModel"
});

CREATE (prop_rm2:Property {
    id: "PROP-RM-MYPAGE-PRODUCTID",
    name: "productId",
    type: "String",
    description: "상품 ID",
    isRequired: true,
    parentId: "RM-MYPAGE-ORDER-STATUS",
    parentType: "ReadModel"
});

CREATE (prop_rm3:Property {
    id: "PROP-RM-MYPAGE-ORDERSTATUS",
    name: "orderStatus",
    type: "String",
    description: "주문 상태",
    isRequired: true,
    parentId: "RM-MYPAGE-ORDER-STATUS",
    parentType: "ReadModel"
});

CREATE (prop_rm4:Property {
    id: "PROP-RM-MYPAGE-DELIVERYSTATUS",
    name: "deliveryStatus",
    type: "String",
    description: "배송 상태",
    isRequired: false,
    parentId: "RM-MYPAGE-ORDER-STATUS",
    parentType: "ReadModel"
});


// ############################################################
// 10. UI (UI 와이어프레임 - 흰색 스티커)
// ############################################################
// 설명: Command 또는 ReadModel에 부착되는 UI 화면 와이어프레임
//       User Story에서 UI에 대한 서술이 있는 경우 생성
//       Vue template HTML 형태로 wireframe 저장
// 관계:
//   - HAS_UI ← BoundedContext
//   - ATTACHED_TO → Command / ReadModel
//
// 필수 속성:
//   - id: String (고유 식별자, UI-BCNAME-NAME 형식)
//   - name: String (화면 이름)
//
// 선택 속성:
//   - description: String (화면 설명)
//   - template: String (Vue template HTML)
//   - attachedToId: String (연결된 Command/ReadModel ID)
//   - attachedToType: String ("Command", "ReadModel")
//   - attachedToName: String (연결된 객체 이름)
//   - userStoryId: String (원본 User Story ID)
// ############################################################

CREATE (ui:UI {
    id: "UI-ORDER-CANCELORDER",
    name: "주문 취소 화면",
    description: "고객이 주문을 취소하기 위한 화면",
    attachedToId: "CMD-CANCEL-ORDER",
    attachedToType: "Command",
    attachedToName: "CancelOrder",
    userStoryId: "US-001",
    template: '
<div class="wireframe">
  <h2>주문 취소</h2>
  <form class="form">
    <div class="form-group">
      <label>주문 번호</label>
      <input type="text" placeholder="주문 번호 입력" readonly />
    </div>
    <div class="form-group">
      <label>취소 사유</label>
      <select>
        <option>단순 변심</option>
        <option>배송 지연</option>
        <option>상품 정보 상이</option>
        <option>기타</option>
      </select>
    </div>
    <div class="form-group">
      <label>상세 사유 (선택)</label>
      <textarea placeholder="상세 사유를 입력하세요"></textarea>
    </div>
    <div class="btn-group">
      <button type="submit">취소 신청</button>
      <button type="button">돌아가기</button>
    </div>
  </form>
</div>
    '
});
