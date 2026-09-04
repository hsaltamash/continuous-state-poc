# Continuous State Governance PoC — Mac

This PoC demonstrates one application composed of four governed controls collected by four mechanisms:

- REST/JSON via a small Flask mock API
- Local JSON file
- MySQL query using a read-only DB account
- OpenLDAP group membership using a lab bind account

All observations are normalized into a canonical state record, stored in SQLite, compared deterministically to expected values in `config/onboarding.yaml`, exposed through a Flask dashboard, exportable to CSV, callable on demand through MCP, and runnable continuously with macOS `launchd`.

## 0. Architecture

An editable Mermaid architecture diagram is available in
[`docs/architecture.md`](docs/architecture.md).

```text
Codex MCP prompt -------> Python MCP server ----┐
                                                  |
macOS launchd (5 min) ----------------------------+--> State Engine
                                                       |
                +----------------+---------------------+------------------+
                |                |                     |                  |
             REST API        JSON file              MySQL             OpenLDAP
                |                |                     |                  |
                +----------------+----------+----------+------------------+
                                           |
                                      Normalize
                                           |
                                Expected <-> Observed
                                           |
                              SQLite snapshots/events
                                   |             |
                              Dashboard       CSV export
```

The scheduler and MCP path both invoke the same state engine. Codex is not the source of truth and does not perform the deterministic comparison.

## 1. Prerequisites

You need:

1. macOS
2. Python 3.11+ recommended
3. Docker Desktop
4. Codex for the MCP portion
5. Optional: Node 22.19+ only if you want to use the MCP Inspector

Check what is already installed:

```bash
python3 --version
docker --version
docker compose version
```

If Docker Desktop is not installed, install it from Docker's official Mac installer and start Docker Desktop before continuing.

## 2. Create the Python environment

From this repository directory:

```bash
cd /ABSOLUTE/PATH/TO/continuous-state-poc
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Verify imports:

```bash
python -c "import flask,yaml,requests,mysql.connector,ldap3,mcp; print('Python dependencies OK')"
```

## 3. Start MySQL and OpenLDAP

```bash
docker compose up -d
```

Watch startup:

```bash
docker compose ps
docker compose logs -f mysql openldap
```

Press Ctrl-C to stop following logs; the containers remain running.

Expected ports:

- MySQL: `127.0.0.1:3306`
- LDAP: `127.0.0.1:1389`

Check MySQL:

```bash
docker exec csg-mysql mysql -ustate_reader -pdemo_readonly_pw demoapp \
  -e "SELECT * FROM app_config;"
```

Check LDAP membership:

```bash
docker exec csg-openldap ldapsearch -x \
  -H ldap://127.0.0.1:389 \
  -D 'cn=admin,dc=demo,dc=local' \
  -w admin_demo_pw \
  -b 'cn=app-admins,ou=groups,dc=demo,dc=local' member
```

## 4. Start the mock application API

Open Terminal A:

```bash
cd /ABSOLUTE/PATH/TO/continuous-state-poc
source .venv/bin/activate
python src/mock_api.py
```

It listens on `http://127.0.0.1:5001`.

Test it from another terminal:

```bash
curl -s http://127.0.0.1:5001/config | python3 -m json.tool
```

The API intentionally reads `config/mock_app_config.json`, so editing that file changes both the API-returned state and the direct-file state where applicable.

## 5. Inspect the onboarding definition

Open:

```text
config/onboarding.yaml
```

The PoC starts with four controls:

| Control | Collector | Expected state |
|---|---|---|
| `api-session-timeout` | REST JSON | `30` |
| `file-tls-enabled` | JSON file | `true` |
| `db-max-connections` | MySQL SELECT | `"200"` |
| `iam-app-admins` | LDAP group query | Alice + Bob |

Credentials are not embedded in the onboarding YAML. The YAML references environment-variable names and `.env` contains the PoC secrets. The LDAP collector uses the lab admin bind in this local demo because the container image's default ACL does not grant the demo reader account group-read access. A real implementation should use a read-only service account with explicit LDAP ACLs and replace `.env` with a secrets manager/vault.

## 6. Capture the first known-good state

Open Terminal B:

```bash
cd /ABSOLUTE/PATH/TO/continuous-state-poc
source .venv/bin/activate
python src/state_engine.py capture
```

All four controls should return `MATCH` with collector status `OK`.

Show latest state:

```bash
python src/state_engine.py current
```

Show state transitions/events:

```bash
python src/state_engine.py events
```

SQLite is created at:

```text
data/state.db
```

## 7. Start the guided demo dashboard

Open Terminal C:

```bash
cd /ABSOLUTE/PATH/TO/continuous-state-poc
source .venv/bin/activate
python src/dashboard.py
```

Open:

```text
http://127.0.0.1:5002
```

The dashboard is also the demo console. Use its buttons to:

- capture current state
- apply and restore REST/API drift
- apply and restore direct-file drift
- apply and restore MySQL drift
- apply and restore LDAP/IAM drift
- stop and start MySQL to demonstrate collector health
- restore all local lab values
- export CSV evidence

Refresh is not required after using the buttons; each action redirects back to the latest state view.

## 8. Demonstrate REST/API drift

Change the session timeout in:

```text
config/mock_app_config.json
```

From:

```json
"session_timeout_minutes": 30
```

to:

```json
"session_timeout_minutes": 60
```

Then run:

```bash
python src/state_engine.py capture
python src/state_engine.py history api-session-timeout
```

Expected result: `api-session-timeout` becomes `DRIFT`, with `30` expected and `60` observed.

Restore it to `30`, capture again, and the event history should record `DRIFT_RESTORED`.

## 9. Demonstrate direct-file drift

Change:

```json
"tls_enabled": true
```

to:

```json
"tls_enabled": false
```

Run:

```bash
python src/state_engine.py capture
python src/state_engine.py history file-tls-enabled
```

Expected: `file-tls-enabled` becomes `DRIFT`.

Restore it afterwards if desired.

## 10. Demonstrate database drift

The monitoring account is SELECT-only. Use the lab root account deliberately to simulate an administrator changing application configuration:

```bash
docker exec csg-mysql mysql -uroot -proot_demo_pw demoapp \
  -e "UPDATE app_config SET config_value='350' WHERE config_key='max_connections';"
```

Capture:

```bash
python src/state_engine.py capture
python src/state_engine.py history db-max-connections
```

Expected: `"200" -> "350"`, status `DRIFT`.

Restore:

```bash
docker exec csg-mysql mysql -uroot -proot_demo_pw demoapp \
  -e "UPDATE app_config SET config_value='200' WHERE config_key='max_connections';"
python src/state_engine.py capture
```

## 11. Demonstrate IAM/group-membership drift

Add Carol to the privileged mock group with the lab LDAP admin identity:

```bash
cat <<'LDIF' | docker exec -i csg-openldap ldapmodify -x \
  -H ldap://127.0.0.1:389 \
  -D 'cn=admin,dc=demo,dc=local' \
  -w admin_demo_pw

dn: cn=app-admins,ou=groups,dc=demo,dc=local
changetype: modify
add: member
member: uid=carol,ou=people,dc=demo,dc=local
LDIF
```

Capture:

```bash
python src/state_engine.py capture
python src/state_engine.py history iam-app-admins
```

Expected: the membership list contains Carol and the control becomes `DRIFT`.

Restore:

```bash
cat <<'LDIF' | docker exec -i csg-openldap ldapmodify -x \
  -H ldap://127.0.0.1:389 \
  -D 'cn=admin,dc=demo,dc=local' \
  -w admin_demo_pw

dn: cn=app-admins,ou=groups,dc=demo,dc=local
changetype: modify
delete: member
member: uid=carol,ou=people,dc=demo,dc=local
LDIF

python src/state_engine.py capture
```

## 12. Demonstrate collector-health != drift

This is an important part of the PoC.

Stop MySQL:

```bash
docker stop csg-mysql
python src/state_engine.py capture
```

The DB control should become:

```text
status = UNKNOWN
collector_status = ERROR
```

It must **not** claim that the DB configuration value drifted. The framework is saying, "I can no longer attest to this control."

Bring MySQL back:

```bash
docker start csg-mysql
```

Wait until it is ready, then:

```bash
python src/state_engine.py capture
```

The event stream should show collector restoration.

## 13. Export audit evidence to CSV

```bash
python src/state_engine.py export-csv
```

The command prints the generated file path under `output/`.

## 14. Test the MCP server before Codex

The current MCP reference Inspector runs through `npx` and requires Node 22.19+.

If Node is installed:

```bash
node --version
npx @modelcontextprotocol/inspector .venv/bin/python src/mcp_server.py
```

Use the Inspector to list/call these tools:

- `run_state_capture`
- `get_current_state`
- `get_control_history`
- `get_recent_drift_events`
- `export_current_state_csv`

For an stdio MCP server, do not add `print()` calls to `mcp_server.py`; stdout is reserved for MCP protocol traffic.

## 15. Register the MCP server in Codex

This repo includes a project-scoped Codex MCP config at:

```text
.codex/config.toml
```

Codex supports MCP server configuration in `config.toml` using `mcp_servers.<id>.command`, `args`, `cwd`, and `env`.

Use **absolute paths** for this local PoC. First find this repository's absolute path:

```bash
pwd
```

Then make sure `.codex/config.toml` points at your local checkout and virtual environment:

```toml
[mcp_servers.continuous-state-governance]
command = "/ABSOLUTE/PATH/TO/continuous-state-poc/.venv/bin/python"
args = ["/ABSOLUTE/PATH/TO/continuous-state-poc/src/mcp_server.py"]
cwd = "/ABSOLUTE/PATH/TO/continuous-state-poc"

[mcp_servers.continuous-state-governance.env]
DB_PASSWORD = "demo_readonly_pw"
LDAP_BIND_PASSWORD = "admin_demo_pw"
```

Restart Codex after changing project MCP configuration.

Suggested prompts:

```text
Use the continuous-state-governance tools to capture the current state of demo-web-app. Tell me which controls are healthy, drifted, or unverifiable.
```

```text
Use the continuous-state-governance tools to show me everything that changed in demo-web-app since its last healthy state.
```

```text
Use the continuous-state-governance tools to show the history of iam-app-admins and explain the membership changes without altering anything.
```

```text
Use the continuous-state-governance tools to run a new state capture, then export the current state as CSV evidence.
```

## 16. Add continuous scheduled capture with macOS launchd

The included job runs every 300 seconds (5 minutes) and once when loaded.

Install:

```bash
./scripts/install_launchd.sh
```

Check it:

```bash
launchctl print "gui/$(id -u)/com.demo.continuous-state-capture"
```

Logs:

```bash
tail -f data/launchd.out.log data/launchd.err.log
```

Uninstall it:

```bash
./scripts/uninstall_launchd.sh
```

For the PoC, credentials are included in the generated launchd environment. This is deliberately simple for a local lab; do not use that pattern for production secrets.

## 17. End-to-end demo script

For a click-by-click validation runbook, see
[`docs/demo-test-steps.md`](docs/demo-test-steps.md).

A clean demo sequence is:

1. Start Docker containers and Flask API.
2. Open the guided dashboard and click Capture State — dashboard shows 4 healthy controls.
3. Use the dashboard to apply REST/API drift: session timeout 30 -> 60.
4. Use the dashboard to add Carol to `app-admins`.
5. Use the dashboard to change MySQL `max_connections` app setting 200 -> 350.
6. Click Capture State manually or wait for launchd.
7. Dashboard shows three drifts.
8. Ask Codex, "Use the continuous-state-governance tools to show recent drift events."
9. Stop MySQL and capture again to demonstrate `UNKNOWN`, not false drift.
10. Restore all values.
11. Ask Codex to revalidate.
12. Show `DRIFT_RESTORED` / collector-restored events.
13. Export CSV evidence.

That demonstrates heterogeneous collection, deterministic comparison, on-demand MCP invocation, scheduled capture, state history, IAM drift, application drift, DB drift, collector health, visualization and evidence export.

## 18. Reset the lab

Stop services:

```bash
docker compose down
```

Reset MySQL data and start completely fresh:

```bash
docker compose down -v
rm -f data/state.db
rm -f output/*.csv

docker compose up -d
```

If LDAP bootstrap changes do not reset as expected, `docker compose down` and recreate the LDAP container; its data is not persisted in this PoC.

## 18. Docker-only demo stack

The full local demo stack can also run through Docker Compose: MySQL, OpenLDAP,
the mock API, the dashboard, and an on-demand state capture CLI.

Make sure `.env` exists first:

```bash
cp .env.example .env
```

Start everything:

```bash
docker compose up -d --build
```

Open the dashboard:

```text
http://127.0.0.1:5002
```

Run a capture from inside the Compose network:

```bash
docker compose --profile tools run --rm state-cli capture
```

The Docker services use `config/onboarding.docker.yaml`, where collectors refer
to Compose service names such as `mock-api`, `mysql`, and `openldap`. The
dashboard container mounts `/var/run/docker.sock` so its demo buttons can still
run `docker exec`, `docker stop`, and `docker start` against the lab containers.
Use that socket mount only for this local demo setup.

## 19. What this PoC deliberately does NOT build yet

- AI-based risk scoring
- CMDB integration
- ITSM ticket creation/update
- production-grade secrets vault
- immutable/WORM evidence storage
- approval workflow
- policy exceptions
- ownership/manager escalation
- write/remediation actions
- RBAC UI
- event-triggered collectors

Those are v0.2+ concerns. v0.1 proves the underlying assertion first: heterogeneous controls can be represented as an expected state, an observed authoritative state, and a deterministic difference with provenance and timestamps.
