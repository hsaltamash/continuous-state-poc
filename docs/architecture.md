# Continuous State Governance PoC Architecture

```mermaid
flowchart TB
  subgraph Users["Users and Automation"]
    Claude["Claude Desktop"]
    Launchd["macOS launchd<br/>5 minute schedule"]
    Operator["Operator CLI"]
    Browser["Browser"]
  end

  subgraph EntryPoints["Entry Points"]
    MCP["Python MCP server<br/>src/mcp_server.py"]
    CLI["State engine CLI<br/>src/state_engine.py"]
    Dashboard["Flask dashboard<br/>src/dashboard.py"]
  end

  subgraph Core["Authoritative State Engine"]
    Engine["Capture and compare<br/>collect, normalize, compare"]
    Baseline["Expected baselines<br/>config/onboarding.yaml"]
    Canonical["Canonical JSON values<br/>stable deterministic comparison"]
  end

  subgraph Collectors["Read-only Collectors"]
    RestCollector["REST JSON collector"]
    FileCollector["Local JSON collector"]
    MySQLCollector["MySQL query collector"]
    LDAPCollector["OpenLDAP group collector"]
  end

  subgraph Sources["Observed State Sources"]
    MockAPI["Mock app API<br/>127.0.0.1:5001/config"]
    ConfigFile["Mock app config<br/>config/mock_app_config.json"]
    MySQL["MySQL demoapp<br/>app_config"]
    LDAP["OpenLDAP<br/>app-admins group"]
  end

  subgraph Evidence["Evidence and Views"]
    SQLite["SQLite state store<br/>data/state.db"]
    Snapshots["snapshots"]
    Events["drift_events"]
    Runs["collector_runs"]
    CSV["CSV evidence export<br/>output/*.csv"]
  end

  Claude --> MCP
  Launchd --> CLI
  Operator --> CLI
  Browser --> Dashboard

  MCP --> Engine
  CLI --> Engine
  Dashboard --> SQLite

  Engine --> Baseline
  Engine --> Canonical
  Engine --> RestCollector
  Engine --> FileCollector
  Engine --> MySQLCollector
  Engine --> LDAPCollector

  RestCollector --> MockAPI
  FileCollector --> ConfigFile
  MySQLCollector --> MySQL
  LDAPCollector --> LDAP

  Engine --> SQLite
  SQLite --> Snapshots
  SQLite --> Events
  SQLite --> Runs
  Engine --> CSV

  classDef user fill:#e8f2ff,stroke:#3b82f6,color:#172033;
  classDef entry fill:#f0fdf4,stroke:#22c55e,color:#172033;
  classDef core fill:#fff7ed,stroke:#f97316,color:#172033;
  classDef source fill:#fef2f2,stroke:#ef4444,color:#172033;
  classDef evidence fill:#f8fafc,stroke:#64748b,color:#172033;

  class Claude,Launchd,Operator,Browser user;
  class MCP,CLI,Dashboard entry;
  class Engine,Baseline,Canonical,RestCollector,FileCollector,MySQLCollector,LDAPCollector core;
  class MockAPI,ConfigFile,MySQL,LDAP source;
  class SQLite,Snapshots,Events,Runs,CSV evidence;
```

## Flow

1. A capture is triggered by the CLI, macOS `launchd`, or an MCP tool call from Claude Desktop.
2. `src/state_engine.py` loads expected baselines from `config/onboarding.yaml`.
3. The state engine invokes each configured read-only collector.
4. Collector outputs are normalized into canonical JSON strings.
5. The normalized observed value is compared deterministically with the expected value.
6. The run is stored in SQLite as snapshots, drift events, and collector-run health records.
7. The dashboard reads the latest SQLite state directly; it does not run collectors.
8. CSV export writes current evidence files under `output/`.

## Status Model

- `MATCH`: collector succeeded and observed state equals the expected baseline.
- `DRIFT`: collector succeeded and observed state differs from the expected baseline.
- `UNKNOWN`: collector failed, so the system cannot attest to the control.

`UNKNOWN` is intentionally separate from `DRIFT`. A failed collector does not prove that the underlying control changed.
