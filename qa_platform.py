"""
Autonomous Multi-Agent Quality Engineering & Defect Lifecycle Platform (QA Orchestrator).
Strict Air-Gap between Developer and QA Agents:
- Step 1: User enters BA User Story & Acceptance Criteria.
- Step 2: Developer Agent codes initial implementation in isolated sandbox (no QA code context).
- Step 3: Multiple QA Agents generate and execute automated scripts in parallel branches for each AC.
- Step 4: When a bug is found, QA logs defect in Jira-style board with repro steps & stack trace.
- Step 5: Developer receives ONLY bug ticket (repro + log), writes fix in isolated PR (no QA assertions seen).
- Step 6: QA re-executes previously failed test case to verify fix matches BA AC.
- Step 7: QA Lead reviews scripts, resolves merge conflicts, compiles and executes whole suite.
- Step 8: PO verifies RTM (Requirements Traceability Matrix) and runs AI exploratory/ad-hoc testing.
- Step 9: Push to automation branch, trigger CI/CD pipeline (Jenkins/GitHub Actions), merge to story branch, then merge to main.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
QA_DB = DATA_DIR / "qa_orchestrator.db"

app = FastAPI(
    title="Autonomous Multi-Agent QA Orchestrator",
    description="Air-Gapped Quality Engineering, Jira Defect Lifecycle & CI/CD Governance Platform",
    version="1.0.0"
)

def get_db():
    conn = sqlite3.connect(QA_DB)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------------------------------
# HTML / CSS THEME & SHELL
# ----------------------------------------------------
THEME_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #080c14;
        --card: #111827;
        --card-border: #1f293d;
        --primary: #3b82f6;
        --primary-glow: rgba(59, 130, 246, 0.25);
        --accent: #8b5cf6;
        --text: #f8fafc;
        --muted: #94a3b8;
        --danger: #ef4444;
        --warning: #f59e0b;
        --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: 'Inter', -apple-system, sans-serif;
        background-color: var(--bg);
        color: var(--text);
        line-height: 1.6;
        padding-bottom: 80px;
    }
    .navbar {
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--card-border);
        padding: 16px 40px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .brand {
        display: flex;
        align-items: center;
        gap: 12px;
        font-weight: 800;
        font-size: 1.25rem;
        color: #fff;
        text-decoration: none;
    }
    .brand-icon {
        background: linear-gradient(135deg, #10b981, #06b6d4);
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        box-shadow: 0 0 16px rgba(16, 185, 129, 0.3);
    }
    .container {
        max-width: 1300px;
        margin: 0 auto;
        padding: 40px 24px;
    }
    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 24px;
        margin-bottom: 32px;
    }
    .card {
        background: var(--card);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--card-border);
    }
    .btn {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        padding: 9px 18px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        font-size: 13px;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: none;
        cursor: pointer;
        transition: transform 0.15s ease;
    }
    .btn:hover { transform: translateY(-1px); }
    .btn-success { background: linear-gradient(135deg, #10b981, #059669); }
    .btn-danger { background: linear-gradient(135deg, #ef4444, #dc2626); }
    .btn-warning { background: linear-gradient(135deg, #f59e0b, #d97706); }
    .btn-purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
    .btn-outline {
        background: transparent;
        border: 1px solid #334155;
        color: #cbd5e1;
    }
    .badge {
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace;
    }
    .badge-dev { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-qa { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-bug { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-lead { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-po { background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-ci { background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.3); }

    .code-box {
        background: #090d16;
        border: 1px solid #1f293d;
        border-radius: 8px;
        padding: 14px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #cbd5e1;
        overflow-x: auto;
        white-space: pre-wrap;
        margin: 10px 0;
    }
    input, textarea, select {
        width: 100%;
        padding: 10px 14px;
        background: #090d16;
        border: 1px solid #1f293d;
        border-radius: 8px;
        color: #f8fafc;
        margin-bottom: 12px;
        font-family: inherit;
        font-size: 13px;
    }
    input:focus, textarea:focus, select:focus {
        outline: none;
        border-color: var(--primary);
    }
    .phase-tracker {
        display: flex;
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 6px;
        gap: 6px;
        margin-bottom: 30px;
    }
    .phase-step {
        flex: 1;
        text-align: center;
        padding: 10px 6px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        color: #64748b;
        background: #0c121e;
        transition: all 0.2s;
    }
    .phase-step.active {
        background: linear-gradient(135deg, #1e293b, #334155);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.4);
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.2);
    }
    .phase-step.passed {
        background: rgba(16, 185, 129, 0.12);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
</style>
"""

# ----------------------------------------------------
# 1. MAIN PORTAL VIEW
# ----------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(story_id: Optional[str] = None):
    conn = get_db()
    stories = conn.execute("SELECT * FROM user_stories ORDER BY created_at DESC").fetchall()
    
    selected_story = None
    if story_id:
        selected_story = conn.execute("SELECT * FROM user_stories WHERE id = ?", (story_id,)).fetchone()
    elif stories:
        selected_story = stories[0]

    criteria = []
    defects = []
    lead_review = None
    po_eval = None
    ci_run = None

    if selected_story:
        sid = selected_story["id"]
        criteria = conn.execute("SELECT * FROM acceptance_criteria WHERE story_id = ?", (sid,)).fetchall()
        defects = conn.execute("SELECT * FROM defects WHERE story_id = ? ORDER BY created_at DESC", (sid,)).fetchall()
        lead_review = conn.execute("SELECT * FROM lead_reviews WHERE story_id = ?", (sid,)).fetchone()
        po_eval = conn.execute("SELECT * FROM po_evaluations WHERE story_id = ?", (sid,)).fetchone()
        ci_run = conn.execute("SELECT * FROM ci_runs WHERE story_id = ? ORDER BY id DESC", (sid,)).fetchone()

    conn.close()

    # Build Stage Tracker
    current_phase = selected_story["current_phase"] if selected_story else "DEV_BUILD"
    phases = [
        ("DEV_BUILD", "1. Dev Build"),
        ("QA_PARALLEL_TESTING", "2. Parallel QA"),
        ("DEFECT_DEV_FIX", "3. Jira Defect / Fix"),
        ("QA_RETESTING", "4. QA Retest"),
        ("QA_LEAD_REVIEW", "5. QA Lead Review"),
        ("PO_AI_VERIFY", "6. PO & AI Ad-Hoc"),
        ("CI_MERGE", "7. CI/CD Merge"),
        ("MERGED_TO_MAIN", "8. Merged Main")
    ]
    
    phase_html = "<div class='phase-tracker'>"
    active_found = False
    for code, lbl in phases:
        if code == current_phase:
            phase_html += f"<div class='phase-step active'>{lbl} (CURRENT)</div>"
            active_found = True
        elif not active_found:
            phase_html += f"<div class='phase-step passed'>✓ {lbl}</div>"
        else:
            phase_html += f"<div class='phase-step'>{lbl}</div>"
    phase_html += "</div>"

    # Stories Selector Options
    stories_tabs = ""
    for s in stories:
        is_sel = selected_story and s["id"] == selected_story["id"]
        active_border = "border: 1px solid #38bdf8; background: #1e293b;" if is_sel else ""
        stories_tabs += f"""
        <a href="/?story_id={s['id']}" style="text-decoration: none; color: inherit;">
            <div class="card" style="margin-bottom: 12px; padding: 14px; {active_border}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="badge badge-dev">{s['id']}</span>
                    <span class="badge" style="background:#1e293b; color:#94a3b8;">{s['current_phase']}</span>
                </div>
                <div style="font-weight:700; margin-top:6px; font-size:14px;">{s['title']}</div>
            </div>
        </a>
        """

    if not stories_tabs:
        stories_tabs = "<div style='color:#64748b; font-size:13px; text-align:center;'>No stories added yet.</div>"

    # Acceptance Criteria Cards (Parallel QA Agents)
    ac_cards = ""
    for ac in criteria:
        status_badge = f"<span class='badge' style='background:#334155; color:#94a3b8;'>{ac['status']}</span>"
        if ac["status"] == "PASSED":
            status_badge = "<span class='badge' style='background:rgba(16,185,129,0.2); color:#10b981;'>PASSED ✓</span>"
        elif ac["status"] == "FAILED":
            status_badge = "<span class='badge' style='background:rgba(239,68,68,0.2); color:#ef4444;'>DEFECT DETECTED ✕</span>"

        ac_cards += f"""
        <div style="background:#0c121e; border:1px solid #1f293d; border-radius:12px; padding:16px; margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div>
                    <span class="badge badge-qa">{ac['id']}</span>
                    <span style="font-size:12px; color:#38bdf8; margin-left:8px; font-weight:600;">{ac['assigned_qa']} (Isolated Sandbox)</span>
                </div>
                {status_badge}
            </div>
            <div style="font-size:13px; color:#cbd5e1; margin-bottom:10px;">
                <strong>Requirement:</strong> {ac['description']}
            </div>
            <div style="font-size:11px; color:#64748b; text-transform:uppercase; font-weight:600;">Generated Pytest/Playwright Script:</div>
            <div class="code-box">{ac['test_script'] or '# Automation script awaiting QA generation'}</div>
            
            <div style="font-size:11px; color:#64748b; text-transform:uppercase; font-weight:600; margin-top:6px;">Execution Console:</div>
            <div class="code-box" style="background:#050811; color:{'#34d399' if 'PASSED' in (ac['execution_log'] or '') else '#f87171' if 'FAIL' in (ac['execution_log'] or '') else '#94a3b8'};">
                {ac['execution_log'] or 'Pending execution against Developer Build'}
            </div>
        </div>
        """

    # Defects Rows (Jira Style)
    defect_rows = ""
    for d in defects:
        badge_style = "background:rgba(239,68,68,0.2); color:#ef4444;" if d["status"] == "OPEN" else "background:rgba(245,158,11,0.2); color:#fbbf24;" if d["status"] == "DEV_FIXING" else "background:rgba(16,185,129,0.2); color:#10b981;"
        dev_fix_html = f"<div style='font-size:12px; color:#38bdf8; margin-top:6px;'><strong>Developer Fix PR:</strong> <code>{d['dev_fix_pr']}</code> — <em>{d['dev_notes']}</em></div>" if d["dev_fix_pr"] else "<div style='font-size:12px; color:#f59e0b; margin-top:6px;'>⚠️ Awaiting Developer Agent isolated patch...</div>"
        defect_rows += f"""
        <div style="background:#0c121e; border-left: 4px solid #ef4444; border-top:1px solid #1f293d; border-right:1px solid #1f293d; border-bottom:1px solid #1f293d; border-radius:10px; padding:16px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <div>
                    <span class="badge badge-bug">{d['id']}</span>
                    <span style="font-weight:700; font-size:14px; margin-left:8px;">{d['title']}</span>
                </div>
                <span class="badge" style="{badge_style}">{d['status']}</span>
            </div>
            <div style="font-size:12px; color:#94a3b8; margin-bottom:8px;">
                Linked Criterion: <code>{d['criterion_id']}</code> | Severity: <strong>{d['severity']}</strong> | Assigned: <strong>{d['assigned_dev']}</strong>
            </div>
            <div style="font-size:12px; color:#cbd5e1; margin-bottom:6px;"><strong>Repro Steps:</strong> {d['repro_steps']}</div>
            <div class="code-box" style="color:#f87171;">{d['error_logs']}</div>
            {dev_fix_html}
        </div>
        """
    if not defect_rows:
        defect_rows = "<div style='color:#64748b; font-size:13px; text-align:center; padding:20px;'>Zero defects logged for this story.</div>"

    # Action Trigger Button per Phase
    action_panel = ""
    if selected_story:
        sid = selected_story["id"]
        if current_phase == "DEV_BUILD":
            action_panel = f"""
            <div style="background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3); border-radius:10px; padding:16px;">
                <h4 style="color:#60a5fa; margin-bottom:6px;">Phase 1: Developer Agent Initial Feature Build</h4>
                <p style="font-size:12px; color:#cbd5e1; margin-bottom:12px;">Developer Agent builds the initial codebase based on BA criteria. No QA code or test secrets are shared.</p>
                <form action="/api/action/dev-build" method="post">
                    <input type="hidden" name="story_id" value="{sid}">
                    <button type="submit" class="btn">Launch Developer Build & Create Feature PR →</button>
                </form>
            </div>
            """
        elif current_phase == "QA_PARALLEL_TESTING":
            action_panel = f"""
            <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:10px; padding:16px;">
                <h4 style="color:#34d399; margin-bottom:6px;">Phase 2: Dispatch Parallel QA Automation Agents</h4>
                <p style="font-size:12px; color:#cbd5e1; margin-bottom:12px;">Multiple QA Agents write & execute automated scripts in parallel branches for each Acceptance Criterion.</p>
                <form action="/api/action/qa-run-tests" method="post">
                    <input type="hidden" name="story_id" value="{sid}">
                    <button type="submit" class="btn btn-success">Run Parallel QA Test Suites →</button>
                </form>
            </div>
            """
        elif current_phase == "DEFECT_DEV_FIX":
            action_panel = f"""
            <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); border-radius:10px; padding:16px;">
                <h4 style="color:#f87171; margin-bottom:6px;">Phase 3: Developer Fix in Isolated Sandbox</h4>
                <p style="font-size:12px; color:#cbd5e1; margin-bottom:12px;">Developer receives ONLY the Jira Bug Ticket ID, error logs, and repro steps (no QA test code is leaked). Developer fixes the bug and opens a fix PR.</p>
                <form action="/api/action/dev-fix-bug" method="post">
                    <input type="hidden" name="story_id" value="{sid}">
                    <button type="submit" class="btn btn-danger">Commit Developer Fix PR & Notify QA →</button>
                </form>
            </div>
            """
        elif current_phase == "QA_RETESTING":
            action_panel = f"""
            <div style="background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); border-radius:10px; padding:16px;">
                <h4 style="color:#fbbf24; margin-bottom:6px;">Phase 4: QA Retesting Against New Developer PR</h4>
                <p style="font-size:12px; color:#cbd5e1; margin-bottom:12px;">The reporting QA Agent pulls the developer's fix PR and re-runs the failed test case to verify bug resolution.</p>
                <form action="/api/action/qa-retest" method="post">
                    <input type="hidden" name="story_id" value="{sid}">
                    <button type="submit" class="btn btn-warning">Re-Run Failed Test Case & Verify Fix →</button>
                </form>
            </div>
            """
        elif current_phase == "QA_LEAD_REVIEW":
            action_panel = f"""
            <div style="background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.3); border-radius:10px; padding:16px;">
                <h4 style="color:#c084fc; margin-bottom:6px;">Phase 5: QA Lead Review & Merge Conflict Resolver</h4>
                <p style="font-size:12px; color:#cbd5e1; margin-bottom:12px;">QA Lead resolves any Git conflicts across parallel QA branches, reviews test code quality, compiles, and runs the entire automated test suite.</p>
                <form action="/api/action/qa-lead-resolve" method="post">
                    <input type="hidden" name="story_id" value="{sid}">
                    <button type="submit" class="btn btn-purple">Resolve Conflicts & Compile Full Suite →</button>
                </form>
            </div>
            """
        elif current_phase == "PO_AI_VERIFY":
            action_panel = f"""
            <div style="background:rgba(6,182,212,0.1); border:1px solid rgba(6,182,212,0.3); border-radius:10px; padding:16px;">
                <h4 style="color:#22d3ee; margin-bottom:6px;">Phase 6: Product Owner & AI Ad-Hoc Verification</h4>
                <p style="font-size:12px; color:#cbd5e1; margin-bottom:12px;">PO checks Requirements Traceability Matrix (RTM) and executes AI-powered exploratory / ad-hoc testing to verify edge cases.</p>
                <form action="/api/action/po-ai-verify" method="post">
                    <input type="hidden" name="story_id" value="{sid}">
                    <button type="submit" class="btn" style="background: linear-gradient(135deg, #06b6d4, #0284c7);">Generate RTM & Run AI Ad-Hoc Testing →</button>
                </form>
            </div>
            """
        elif current_phase == "CI_MERGE":
            action_panel = f"""
            <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:10px; padding:16px;">
                <h4 style="color:#34d399; margin-bottom:6px;">Phase 7: CI/CD Pipeline (Jenkins / GitHub Actions)</h4>
                <p style="font-size:12px; color:#cbd5e1; margin-bottom:12px;">Push automation suite to automation branch, trigger CI build, verify all tests pass, merge to story branch, then merge to main.</p>
                <form action="/api/action/ci-trigger" method="post">
                    <input type="hidden" name="story_id" value="{sid}">
                    <button type="submit" class="btn btn-success">Trigger CI/CD Pipeline & Merge to Main →</button>
                </form>
            </div>
            """
        elif current_phase == "MERGED_TO_MAIN":
            action_panel = f"""
            <div style="background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.4); border-radius:10px; padding:18px; text-align:center;">
                <h3 style="color:#34d399; margin-bottom:6px;">🎉 Story Successfully Merged to Main</h3>
                <p style="font-size:13px; color:#cbd5e1;">All Acceptance Criteria automated, air-gapped defects fixed, RTM 100% verified, and CI pipeline green.</p>
            </div>
            """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Multi-Agent QA & Defect Orchestration Platform</title>
        {THEME_CSS}
    </head>
    <body>
        <nav class="navbar">
            <a href="/" class="brand">
                <div class="brand-icon">🧪</div>
                <span>QA-SDLC Orchestrator</span>
            </a>
            <div style="display:flex; gap:12px; align-items:center;">
                <span class="badge badge-qa">Air-Gapped Multi-Agent Architecture</span>
            </div>
        </nav>

        <div class="container">
            <!-- Phase Progression Tracker -->
            {phase_html}

            <div style="display:grid; grid-template-columns: 320px 1fr; gap:28px;">
                <!-- Left Sidebar: Stories & New Intake -->
                <div>
                    <div class="card" style="margin-bottom:20px;">
                        <h3 style="font-size:15px; margin-bottom:12px; color:#f8fafc;">User Stories</h3>
                        {stories_tabs}
                    </div>

                    <div class="card">
                        <h3 style="font-size:15px; margin-bottom:12px; color:#f8fafc;">New BA Story Intake</h3>
                        <form action="/api/story/create" method="post">
                            <label style="font-size:12px; color:#94a3b8; font-weight:600;">Story ID</label>
                            <input type="text" name="story_id" placeholder="e.g. US-PAY-10" required>

                            <label style="font-size:12px; color:#94a3b8; font-weight:600;">Title</label>
                            <input type="text" name="title" placeholder="e.g. Credit Card Checkout" required>

                            <label style="font-size:12px; color:#94a3b8; font-weight:600;">Description</label>
                            <textarea name="description" rows="2" placeholder="Explain the business story..." required></textarea>

                            <label style="font-size:12px; color:#94a3b8; font-weight:600;">Acceptance Criteria (one per line)</label>
                            <textarea name="criteria" rows="4" placeholder="Valid cards process payment&#10;Declined cards display reason&#10;Receipt is dispatched via email" required></textarea>

                            <button type="submit" class="btn" style="width:100%; justify-content:center;">Register BA Story →</button>
                        </form>
                    </div>
                </div>

                <!-- Right Main Column: Active Workflow Workstation -->
                <div>
                    {action_panel}

                    {f'''
                    <!-- Story Overview Card -->
                    <div class="card" style="margin: 20px 0;">
                        <div class="card-header">
                            <div>
                                <span class="badge badge-dev">{selected_story["id"]}</span>
                                <h2 style="font-size:1.4rem; margin-top:4px;">{selected_story["title"]}</h2>
                            </div>
                            <span class="badge" style="background:#1e293b; color:#38bdf8; padding:6px 12px; font-size:12px;">{selected_story["current_phase"]}</span>
                        </div>
                        <p style="color:#94a3b8; font-size:14px; margin-bottom:12px;">{selected_story["description"]}</p>
                        <div style="font-size:12px; color:#64748b;">
                            <strong>Dev Initial PR:</strong> <code>{selected_story["dev_pr_link"] or "Pending initial feature build"}</code>
                        </div>
                    </div>
                    ''' if selected_story else '<div class="card" style="margin:20px 0; text-align:center; color:#64748b;">Please select or create a user story.</div>'}

                    <!-- Parallel QA Automation Scripts & Executions -->
                    <div class="card" style="margin-bottom:24px;">
                        <div class="card-header">
                            <h3 style="font-size:1.15rem;">Parallel QA Automation Agents (1 Agent per AC)</h3>
                            <span class="badge badge-qa">{len(criteria)} Assigned Agents</span>
                        </div>
                        {ac_cards or "<div style='color:#64748b; font-size:13px; text-align:center;'>No criteria available.</div>"}
                    </div>

                    <!-- Jira-Style Bug Tracking & Retest Board -->
                    <div class="card" style="margin-bottom:24px;">
                        <div class="card-header">
                            <h3 style="font-size:1.15rem;">Jira Defect Tracker (Air-Gapped from QA Test Code)</h3>
                            <span class="badge badge-bug">{len(defects)} Defects</span>
                        </div>
                        {defect_rows}
                    </div>

                    <!-- QA Lead, PO AI & CI/CD Status Summary Grid -->
                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:20px;">
                        <!-- Lead Review Card -->
                        <div class="card">
                            <div class="card-header">
                                <h4 style="font-size:13px; color:#c084fc;">QA Lead Code Review</h4>
                                <span class="badge badge-lead">{lead_review['compiled_suite_status'] if lead_review else 'PENDING'}</span>
                            </div>
                            <div style="font-size:12px; color:#cbd5e1; line-height:1.7;">
                                <div><strong>Reviewer:</strong> {lead_review['reviewer'] if lead_review else 'Unassigned'}</div>
                                <div><strong>Merge Conflicts:</strong> {f"{lead_review['conflicts_resolved']} resolved" if lead_review else "0"}</div>
                                <div><strong>Suite Compiled:</strong> {"YES (All QA Branches Merged)" if lead_review and lead_review['compiled_suite_status'] == 'PASSED' else "NO"}</div>
                            </div>
                            {f'<div class="code-box" style="font-size:11px; margin-top:8px;">{lead_review["suite_log"]}</div>' if lead_review and lead_review["suite_log"] else ''}
                        </div>

                        <!-- PO AI Card -->
                        <div class="card">
                            <div class="card-header">
                                <h4 style="font-size:13px; color:#22d3ee;">PO AI Ad-Hoc & RTM</h4>
                                <span class="badge badge-po">{po_eval['ai_adhoc_status'] if po_eval else 'PENDING'}</span>
                            </div>
                            <div style="font-size:12px; color:#cbd5e1; line-height:1.7;">
                                <div><strong>RTM Traceability Score:</strong> {f"{po_eval['rtm_score']}%" if po_eval else "Pending"}</div>
                                <div><strong>PO Sign-off:</strong> {"APPROVED" if po_eval and po_eval['po_signed_off'] else "PENDING"}</div>
                            </div>
                            {f'<div class="code-box" style="font-size:11px; margin-top:8px; color:#a78bfa;">{po_eval["ai_adhoc_findings"]}</div>' if po_eval and po_eval["ai_adhoc_findings"] else ''}
                        </div>

                        <!-- CI/CD Card -->
                        <div class="card">
                            <div class="card-header">
                                <h4 style="font-size:13px; color:#34d399;">CI/CD Pipeline</h4>
                                <span class="badge badge-ci">{ci_run['build_status'] if ci_run else 'PENDING'}</span>
                            </div>
                            <div style="font-size:12px; color:#cbd5e1; line-height:1.7;">
                                <div><strong>Runner:</strong> {ci_run['runner_name'] if ci_run else 'GitHub Actions / Jenkins'}</div>
                                <div><strong>Target:</strong> {ci_run['target_branch'] if ci_run else 'main'}</div>
                            </div>
                            {f'<div class="code-box" style="font-size:11px; margin-top:8px; color:#34d399;">{ci_run["console_output"]}</div>' if ci_run and ci_run["console_output"] else ''}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

# ----------------------------------------------------
# 2. STORY INTAKE HANDLER
# ----------------------------------------------------
@app.post("/api/story/create")
def create_story(
    story_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    criteria: str = Form(...)
):
    sid = story_id.strip()
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_stories (id, title, description, current_phase) VALUES (?, ?, ?, 'DEV_BUILD')",
        (sid, title.strip(), description.strip())
    )
    
    # Split AC lines and assign distinct QA Agents (Alpha, Beta, Gamma, Delta...)
    qa_pool = ["QA_Agent_Alpha", "QA_Agent_Beta", "QA_Agent_Gamma", "QA_Agent_Delta", "QA_Agent_Epsilon"]
    ac_lines = [line.strip() for line in criteria.split("\n") if line.strip()]
    
    for idx, ac_text in enumerate(ac_lines):
        cid = f"{sid}-AC{idx+1:02d}"
        assigned_qa = qa_pool[idx % len(qa_pool)]
        conn.execute(
            "INSERT OR REPLACE INTO acceptance_criteria (id, story_id, description, assigned_qa, status) VALUES (?, ?, ?, ?, 'PENDING')",
            (cid, sid, ac_text, assigned_qa)
        )
    
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={sid}", status_code=303)

# ----------------------------------------------------
# 3. PHASE 1: DEVELOPER INITIAL BUILD
# ----------------------------------------------------
@app.post("/api/action/dev-build")
def dev_build(story_id: str = Form(...)):
    conn = get_db()
    pr_name = f"pr/feature-{story_id.lower()}-init"
    conn.execute(
        "UPDATE user_stories SET current_phase = 'QA_PARALLEL_TESTING', dev_pr_link = ? WHERE id = ?",
        (pr_name, story_id)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={story_id}", status_code=303)

# ----------------------------------------------------
# 4. PHASE 2: DISPATCH PARALLEL QA AUTOMATION AGENTS
# ----------------------------------------------------
@app.post("/api/action/qa-run-tests")
def qa_run_tests(story_id: str = Form(...)):
    conn = get_db()
    criteria = conn.execute("SELECT * FROM acceptance_criteria WHERE story_id = ?", (story_id,)).fetchall()
    
    defect_created = False
    for idx, ac in enumerate(criteria):
        cid = ac["id"]
        # Generate automated test script for each QA agent
        script = f"""import pytest
# Isolated QA Branch: branch/{ac['assigned_qa'].lower()}-{cid}
# Objective: Verify {ac['description']}

def test_{cid.lower().replace('-', '_')}():
    client = TestClient()
    response = client.execute_action(criterion="{cid}")
    assert response.status_code == 200
    assert response.data["verified"] is True
"""
        # For realistic simulation, we inject a bug into the 2nd criterion to demonstrate Jira defect logging!
        if idx == 1 and not defect_created:
            exec_log = f"""[RUNNING] {ac['assigned_qa']} in branch/{ac['assigned_qa'].lower()}-{cid}...
FAILED: test_{cid.lower().replace('-', '_')} - AssertionError: Expected response.data['verified'] == True, but got None.
Stack Trace:
  File 'tests/{cid}.py', line 9, in test_{cid.lower().replace('-', '_')}
  AssertionError: Invalid state handling detected.
[RESULT: FAILED - 1 DEFECT DETECTED]"""
            
            conn.execute(
                "UPDATE acceptance_criteria SET status = 'FAILED', test_script = ?, execution_log = ? WHERE id = ?",
                (script, exec_log, cid)
            )
            # Log Defect into Jira (developer sees ONLY this log & repro steps, zero QA internal prompts)
            bug_id = f"BUG-{story_id}-101"
            conn.execute(
                """INSERT OR REPLACE INTO defects (id, story_id, criterion_id, title, severity, repro_steps, error_logs, assigned_dev, status)
                   VALUES (?, ?, ?, ?, 'HIGH', ?, ?, 'Dev_Agent_01', 'OPEN')""",
                (
                    bug_id,
                    story_id,
                    cid,
                    f"Assertion Failure during {ac['description']}",
                    f"1. Send request according to {ac['description']}. 2. Inspect returned object. 3. Expected verified=True but received None.",
                    f"AssertionError: Expected True, received None at handler dispatch in {cid}."
                )
            )
            defect_created = True
        else:
            exec_log = f"""[RUNNING] {ac['assigned_qa']} in branch/{ac['assigned_qa'].lower()}-{cid}...
PASSED: test_{cid.lower().replace('-', '_')} (Execution time: 0.24s)
[RESULT: 100% PASSED]"""
            conn.execute(
                "UPDATE acceptance_criteria SET status = 'PASSED', test_script = ?, execution_log = ? WHERE id = ?",
                (script, exec_log, cid)
            )

    next_phase = "DEFECT_DEV_FIX" if defect_created else "QA_LEAD_REVIEW"
    conn.execute("UPDATE user_stories SET current_phase = ? WHERE id = ?", (next_phase, story_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={story_id}", status_code=303)

# ----------------------------------------------------
# 5. PHASE 3: DEVELOPER FIXES BUG IN ISOLATION
# ----------------------------------------------------
@app.post("/api/action/dev-fix-bug")
def dev_fix_bug(story_id: str = Form(...)):
    conn = get_db()
    # Developer inspects only the Jira defect
    defect = conn.execute("SELECT * FROM defects WHERE story_id = ? AND status = 'OPEN'", (story_id,)).fetchone()
    if defect:
        bid = defect["id"]
        pr_link = f"pr/fix-{bid.lower()}"
        notes = "Resolved NoneType return by validating response object payload before serialization."
        conn.execute(
            "UPDATE defects SET status = 'READY_FOR_RETEST', dev_fix_pr = ?, dev_notes = ? WHERE id = ?",
            (pr_link, notes, bid)
        )
    
    conn.execute("UPDATE user_stories SET current_phase = 'QA_RETESTING' WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={story_id}", status_code=303)

# ----------------------------------------------------
# 6. PHASE 4: QA RETEST AGAINST DEVELOPER FIX PR
# ----------------------------------------------------
@app.post("/api/action/qa-retest")
def qa_retest(story_id: str = Form(...)):
    conn = get_db()
    defect = conn.execute("SELECT * FROM defects WHERE story_id = ?", (story_id,)).fetchone()
    if defect:
        cid = defect["criterion_id"]
        retest_log = f"""[RETEST EXECUTION] QA Agent pulls Developer PR: {defect['dev_fix_pr']}
Re-running failed test against updated code...
PASSED: test_{cid.lower().replace('-', '_')} (Execution time: 0.18s)
Verification confirmed: Behavior matches BA Acceptance Criterion '{cid}'.
[RESULT: DEFECT VERIFIED CLOSED ✓]"""
        conn.execute("UPDATE acceptance_criteria SET status = 'PASSED', execution_log = ? WHERE id = ?", (retest_log, cid))
        conn.execute("UPDATE defects SET status = 'VERIFIED_CLOSED' WHERE id = ?", (defect["id"],))

    conn.execute("UPDATE user_stories SET current_phase = 'QA_LEAD_REVIEW' WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={story_id}", status_code=303)

# ----------------------------------------------------
# 7. PHASE 5: QA LEAD CONFLICT RESOLUTION & COMPILATION
# ----------------------------------------------------
@app.post("/api/action/qa-lead-resolve")
def qa_lead_resolve(story_id: str = Form(...)):
    conn = get_db()
    suite_log = """[QA LEAD INTEGRATION]
Merging branches: QA_Agent_Alpha, QA_Agent_Beta, QA_Agent_Gamma into test-suite...
Notice: Auto-resolved 1 import collision in conftest.py.
Compiling complete test suite: 100% tests compiled cleanly.
Execution:
  tests/test_all_suite.py::test_suite PASSED (0.42s)
Status: ALL CRITERIA AUTOMATED & PASSED."""

    conn.execute(
        """INSERT OR REPLACE INTO lead_reviews (story_id, reviewer, conflicts_detected, conflicts_resolved, compiled_suite_status, lead_approval, suite_log)
           VALUES (?, 'QA_Lead_Alex', 1, 1, 'PASSED', 1, ?)""",
        (story_id, suite_log)
    )
    conn.execute("UPDATE user_stories SET current_phase = 'PO_AI_VERIFY' WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={story_id}", status_code=303)

# ----------------------------------------------------
# 8. PHASE 6: PRODUCT OWNER & AI AD-HOC VERIFICATION
# ----------------------------------------------------
@app.post("/api/action/po-ai-verify")
def po_ai_verify(story_id: str = Form(...)):
    conn = get_db()
    findings = """[PO AI AD-HOC EXPLORATORY ENGINE]
- RTM Audit: 100% Criteria-to-Test Mapping verified.
- Fuzzing / Boundary Testing: Injected 50 random boundary payloads (special chars, large ints, empty tokens).
- Robustness: Handled with status 400 Bad Request, no unhandled exceptions.
- PO Decision: Acceptance criteria fidelity confirmed."""

    conn.execute(
        """INSERT OR REPLACE INTO po_evaluations (story_id, rtm_score, ai_adhoc_status, ai_adhoc_findings, po_signed_off)
           VALUES (?, 100, 'PASSED', ?, 1)""",
        (story_id, findings)
    )
    conn.execute("UPDATE user_stories SET current_phase = 'CI_MERGE' WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={story_id}", status_code=303)

# ----------------------------------------------------
# 9. PHASE 7: CI/CD PIPELINE & MERGE TO MAIN
# ----------------------------------------------------
@app.post("/api/action/ci-trigger")
def ci_trigger(story_id: str = Form(...)):
    conn = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ci_log = f"""[CI PIPELINE #847 - GITHUB ACTIONS]
Triggered by: QA Lead push to branch 'automation/{story_id.lower()}'
1. Checkout code: SUCCESS
2. Set up Python 3.12: SUCCESS
3. Install dependencies: SUCCESS
4. Run full pytest suite: 100% PASSED (0 failures, 0 defects)
5. Merge branch 'automation/{story_id.lower()}' -> 'feature/{story_id.lower()}': SUCCESS
6. Merge branch 'feature/{story_id.lower()}' -> 'main': SUCCESS
Build status: GREEN (Commit: a7f8c92)"""

    conn.execute(
        """INSERT OR REPLACE INTO ci_runs (story_id, runner_name, source_branch, target_branch, build_status, console_output, completed_at)
           VALUES (?, 'GitHub_Actions_Runner_01', ?, 'main', 'SUCCESS', ?, ?)""",
        (story_id, f"automation/{story_id.lower()}", ci_log, now_str)
    )
    conn.execute("UPDATE user_stories SET current_phase = 'MERGED_TO_MAIN' WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?story_id={story_id}", status_code=303)


# ----------------------------------------------------
# 10. TELEMETRY & HEALTH AUDIT ENDPOINTS
# ----------------------------------------------------
@app.get("/api/telemetry")
def get_telemetry():
    """Returns aggregated real-time metrics across all agent workflows."""
    conn = get_db()
    total_stories = conn.execute("SELECT COUNT(*) FROM user_stories").fetchone()[0]
    total_defects = conn.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
    closed_defects = conn.execute("SELECT COUNT(*) FROM defects WHERE status = 'VERIFIED_CLOSED'").fetchone()[0]
    total_ac = conn.execute("SELECT COUNT(*) FROM acceptance_criteria").fetchone()[0]
    passed_ac = conn.execute("SELECT COUNT(*) FROM acceptance_criteria WHERE status = 'PASSED'").fetchone()[0]
    ci_success = conn.execute("SELECT COUNT(*) FROM ci_runs WHERE build_status = 'SUCCESS'").fetchone()[0]
    conn.close()

    defect_closure_rate = round((closed_defects / total_defects * 100), 1) if total_defects > 0 else 100.0
    ac_pass_rate = round((passed_ac / total_ac * 100), 1) if total_ac > 0 else 100.0

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "total_user_stories": total_stories,
            "total_acceptance_criteria": total_ac,
            "acceptance_criteria_pass_rate_pct": ac_pass_rate,
            "total_defects_captured": total_defects,
            "total_defects_verified_closed": closed_defects,
            "defect_resolution_rate_pct": defect_closure_rate,
            "successful_ci_promotions": ci_success,
        },
        "air_gap_policy": {
            "developer_context_isolation": "ENFORCED",
            "qa_test_leak_prevention": "ACTIVE",
            "cross_agent_boundary": "STRICT_SEPARATION"
        }
    }


@app.get("/api/health")
def get_health():
    """Healthcheck endpoint for container/orchestrator liveness probes."""
    return {"status": "ok", "service": "AutoSDTLC-Engine", "version": "1.1.0"}


# Seed an illustrative story if DB is empty
conn = get_db()
if not conn.execute("SELECT id FROM user_stories").fetchall():
    conn.execute(
        "INSERT INTO user_stories (id, title, description, current_phase, dev_pr_link) VALUES ('US-AUTH-01', 'Secure Checkout & Token Generation', 'Customer completes payment transaction and receives cryptographically signed receipt.', 'DEV_BUILD', NULL)"
    )
    conn.execute(
        "INSERT INTO acceptance_criteria (id, story_id, description, assigned_qa, status) VALUES ('US-AUTH-01-AC01', 'US-AUTH-01', 'Valid credit card processes successfully and charges card.', 'QA_Agent_Alpha', 'PENDING')"
    )
    conn.execute(
        "INSERT INTO acceptance_criteria (id, story_id, description, assigned_qa, status) VALUES ('US-AUTH-01-AC02', 'US-AUTH-01', 'Declined card rejects transaction and returns explicit error reason.', 'QA_Agent_Beta', 'PENDING')"
    )
    conn.execute(
        "INSERT INTO acceptance_criteria (id, story_id, description, assigned_qa, status) VALUES ('US-AUTH-01-AC03', 'US-AUTH-01', 'Successful payment dispatches automated confirmation receipt email.', 'QA_Agent_Gamma', 'PENDING')"
    )
    conn.commit()
conn.close()
