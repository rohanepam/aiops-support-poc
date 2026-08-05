flowchart TD

%%=====================================================
%% Runtime Flow
%%=====================================================

A["Jira Service Management<br/><br/>
Contains:<br/>
• Request Form<br/>
• Attachments"]

--> B

B["Input Processing<br/><br/>
Responsibilities:<br/>
• Read request inputs<br/>
• Parse attachments<br/>
• OCR images (if required)<br/>
• Normalize content into a Unified Request Context"]

--> C

C["Request Intelligence Engine<br/><br/>
Responsibilities:<br/>
• Understand the request<br/>
• Detect domain & technology<br/>
• Identify request intent<br/>
• Extract & resolve entities<br/>
• Build normalized request"]

-->|Normalized Request + Confidence Metadata| D

D["Request Validation & Readiness<br/><br/>
Responsibilities:<br/>
• Validate mandatory attributes<br/>
• Evaluate confidence thresholds<br/>
• Check automation readiness<br/>
• Determine clarification required"]

D -->|Clarification Required| E

E["Human Clarification<br/><br/>
Responsibilities:<br/>
• Comment on JSM request<br/>
• Request missing information<br/>
• Capture user feedback"]

E -. User Feedback .-> C

D -->|Automation Ready| F

F["Catalog Resolver<br/><br/>
Responsibilities:<br/>
• Match request to catalog<br/>
• Select catalog item<br/>
• Generate execution plan"]

-->|Execution Plan| G

G["Policy Engine<br/><br/>
Responsibilities:<br/>
• Evaluate execution policies<br/>
• Human-in-the-loop (HITL)<br/>
• Approval workflows<br/>
• Automation eligibility"]

-->|Approved Execution Plan| H

H["Jenkins Execution<br/><br/>
Responsibilities:<br/>
• Trigger Jenkins pipeline<br/>
• Pass execution parameters<br/>
• Monitor execution<br/>
• Capture execution result"]

--> I

I["Update Jira Service Management<br/><br/>
Responsibilities:<br/>
• Update request status<br/>
• Add execution comments<br/>
• Close or re-route request"]

%%=====================================================
%% Supporting Components
%%=====================================================

R["Catalog Repository<br/><br/>
Contains:<br/>
• Catalog Descriptors (YAML)<br/>
• Layer 1 / Layer 2 / Layer 3<br/>
• Supported Intents<br/>
• Required Parameters<br/>
• Execution Configuration"]

F -. Query Catalog .-> R
R -. Matching Catalog Descriptor .-> F

X["Execution History<br/><br/>
Stores:<br/>
• Request Metadata<br/>
• Catalog Item<br/>
• Execution Parameters<br/>
• Execution Status<br/>
• Duration<br/>
• Audit Trail<br/>
• Execution Artifacts"]

H -. Persist Execution Metadata .-> X

%%=====================================================
%% Styling
%%=====================================================

classDef user fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20;
classDef governance fill:#FFF8E1,stroke:#F9A825,stroke-width:2px,color:#7F6000;
classDef repository fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1;

class A,E user;
class D,G governance;
class R,X repository;