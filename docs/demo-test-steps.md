# Continuous State Governance Demo Test Steps

## UI Demo

1. Open the demo UI:

   ```text
   http://127.0.0.1:5002
   ```

2. Click `Restore All`.

3. Click `Capture State`.

4. Confirm the baseline:
   - Healthy: `4`
   - Drifted: `0`
   - Unknown: `0`
   - All four controls show `MATCH`.

5. Test REST/API drift:
   - Click `Apply Drift` under `REST/API Drift`.
   - Click `Capture State`.
   - Confirm `API - Session timeout` is `DRIFT`.
   - Expected: `30`
   - Observed: `60`

6. Restore REST/API drift:
   - Click `Restore` under `REST/API Drift`.
   - Click `Capture State`.
   - Confirm `API - Session timeout` returns to `MATCH`.
   - Recent events should show `DRIFT_RESTORED`.

7. Test direct-file drift:
   - Click `Apply Drift` under `Direct File Drift`.
   - Click `Capture State`.
   - Confirm `File - TLS enabled` is `DRIFT`.
   - Expected: `true`
   - Observed: `false`

8. Restore direct-file drift:
   - Click `Restore` under `Direct File Drift`.
   - Click `Capture State`.
   - Confirm it returns to `MATCH`.

9. Test database drift:
   - Click `Start MySQL`.
   - Click `Apply Drift` under `Database Drift`.
   - Click `Capture State`.
   - Confirm `MySQL - Max connections app setting` is `DRIFT`.
   - Expected: `"200"`
   - Observed: `"350"`

10. Restore database drift:
    - Click `Restore` under `Database Drift`.
    - Click `Capture State`.
    - Confirm it returns to `MATCH`.

11. Test IAM/LDAP drift:
    - Click `Apply Drift` under `IAM Drift`.
    - Click `Capture State`.
    - Confirm `LDAP - app-admins membership` is `DRIFT`.
    - Observed value should include:

      ```text
      uid=carol,ou=people,dc=demo,dc=local
      ```

12. Restore IAM/LDAP drift:
    - Click `Restore` under `IAM Drift`.
    - Click `Capture State`.
    - Confirm Carol is removed and the control returns to `MATCH`.

13. Test collector-health failure:
    - Click `Stop MySQL` under `Collector Health`.
    - Click `Capture State`.
    - Confirm the DB control becomes:
      - Status: `UNKNOWN`
      - Collector status: `ERROR`
    - It should not show `DRIFT`.

14. Restore collector health:
    - Click `Start MySQL`.
    - Click `Capture State`.
    - Confirm the DB control returns to `MATCH`.
    - Recent events should show `COLLECTOR_RESTORED`.

15. Test multiple drifts together:
    - Click `Apply Drift` under `REST/API Drift`.
    - Click `Apply Drift` under `Direct File Drift`.
    - Click `Apply Drift` under `Database Drift`.
    - Click `Apply Drift` under `IAM Drift`.
    - Click `Capture State`.
    - Confirm Healthy: `0`, Drifted: `4`, Unknown: `0`.

16. Restore everything:
    - Click `Restore All`.
    - Click `Capture State`.
    - Confirm Healthy: `4`, Drifted: `0`, Unknown: `0`.

17. Test CSV export:
    - Click `Export CSV`.
    - Confirm the success message shows a file under `output/`, for example:

      ```text
      output/state-YYYYMMDD-HHMMSS.csv
      ```

## Codex MCP Demo

1. Restart Codex from this repo:

   ```bash
   cd /Users/hassanaltamash/git/continuous-state-poc
   codex
   ```

2. Ask Codex:

   ```text
   Use the continuous-state-governance tools to capture the current state of demo-web-app. Tell me which controls are healthy, drifted, or unverifiable.
   ```

3. Ask Codex:

   ```text
   Use the continuous-state-governance tools to show recent drift events.
   ```

4. Ask Codex:

   ```text
   Use the continuous-state-governance tools to show the history of iam-app-admins and explain the membership changes without altering anything.
   ```

5. Ask Codex:

   ```text
   Use the continuous-state-governance tools to run a new state capture, then export the current state as CSV evidence.
   ```

## Notes

- The browser UI mutates only the local lab state.
- The state engine remains the source of truth for comparison.
- Codex MCP calls use the same `src/state_engine.py` functions as the CLI and dashboard.
- If the DB control shows `UNKNOWN`, click `Start MySQL`, wait for the page to return, and run `Capture State` again.
