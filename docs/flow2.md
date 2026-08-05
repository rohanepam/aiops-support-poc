flowchart TD

A["Unified Request Context<br/><br/>
Input:<br/>
• Form Fields<br/>
• Summary<br/>
• Description<br/>
• Attachment Text<br/>
• User Feedback (Comments)"]

--> B

B["Request Intelligence Orchestrator<br/><br/>
Responsibilities:<br/>
• Request Classification<br/>
• Domain Detection (Layer 1)<br/>
• Technology Detection (Layer 2)<br/>
• Module Selection"]

B --> DB
B --> CMP
B -. Future Expansion .-> FUTURE

%% =====================================================
%% Database Module (Reference Implementation)
%% =====================================================

subgraph DB["Database Module"]
direction TB

DB1["Intent Resolution<br/><br/>
Responsibilities:<br/>
• Identify Layer 3 operation<br/>
• Understand database request intent"]

-->

DB2["Entity Extraction<br/><br/>
Responsibilities:<br/>
• Extract hostname<br/>
• Database<br/>
• Username<br/>
• Schema<br/>
• Instance<br/>
• Tenant<br/>
• Domain-specific entities"]

-->

DB3["Entity Resolution & Enrichment<br/><br/>
Responsibilities:<br/>
• Validate extracted entities<br/>
• Enterprise context lookup<br/>
&nbsp;&nbsp;(CMDB / DB Inventory / Cloud APIs)<br/>
• Enrich metadata<br/>
• Correct invalid values<br/>
• Resolve ambiguities<br/>
• Determine canonical values<br/>
• Calculate confidence"]

-->

DB4["Domain Context Builder<br/><br/>
Responsibilities:<br/>
• Build resolved domain context<br/>
• Produce module-specific request model"]

end

%% =====================================================
%% Compute Module
%% =====================================================

CMP["Compute Module<br/><br/>
(Same Internal Architecture)<br/><br/>
• Intent Resolution<br/>
• Entity Extraction<br/>
• Entity Resolution & Enrichment<br/>
• Domain Context Builder"]

%% =====================================================
%% Future Modules
%% =====================================================

FUTURE["Future Domain Modules<br/><br/>
Examples:<br/>
• Storage<br/>
• Network<br/>
• Middleware<br/>
• SaaS"]

%% =====================================================
%% Common Output
%% =====================================================

DB --> N
CMP --> N
FUTURE -.-> N

N["Request Model Builder<br/><br/>
Responsibilities:<br/>
• Convert module output to platform schema<br/>
• Build normalized request<br/>
• Preserve confidence metadata"]

-->

O["Normalized Request<br/><br/>
Output:<br/>
• Layer 1<br/>
• Layer 2<br/>
• Layer 3<br/>
• Resolved Entities<br/>
• Confidence Metadata"]

%%=====================================================
%% Styling
%%=====================================================

%% Input Artifact
classDef input fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20;

%% Output Artifact
classDef artifact fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1;

%% Orchestrator
classDef orchestrator fill:#F5F5F5,stroke:#616161,stroke-width:2px,color:#212121;

%% Domain Module Container
classDef module fill:#FFFDF5,stroke:#F9A825,stroke-width:2px,color:#7F6000;

%% AI / Reasoning Components
classDef reasoning fill:#FFF3CD,stroke:#F9A825,stroke-width:2px,color:#7F6000;

%% Processing Components
classDef processing fill:#FFFFFF,stroke:#757575,stroke-width:1.5px,color:#212121;

class A input;
class B orchestrator;

class DB,CMP,FUTURE module;

class DB1,DB3 reasoning;

class DB2,DB4,N processing;

class O artifact;