#!/usr/bin/env python3
"""
Contact Graph Database
SQLite-based contact relationship manager with graph query capabilities.

Usage:
    python3 contacts_db.py init                    # Initialize/reset database
    python3 contacts_db.py add "Name" --email x    # Add contact
    python3 contacts_db.py find "query"             # Search contacts
    python3 contacts_db.py link "A" "B" --type "introduced_by"  # Add relationship
    python3 contacts_db.py graph "Name"             # Show relationship graph for person
    python3 contacts_db.py chain "A" "B"            # Find connection chain A→B
    python3 contacts_db.py interactions "Name"      # Show interaction history
    python3 contacts_db.py stale [days]             # Contacts with no interaction in N days
    python3 contacts_db.py stats                    # Database statistics
    python3 contacts_db.py export                   # Export as JSON
    python3 contacts_db.py dot                      # Export as DOT graph
    python3 contacts_db.py html                     # Generate interactive HTML graph
    python3 contacts_db.py sql "query"              # Raw SQL query
"""

import sqlite3
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "contacts.db"

SCHEMA = """
-- Core: People
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    full_name TEXT,
    email TEXT,
    email2 TEXT,
    phone TEXT,
    company TEXT,
    role TEXT,
    location TEXT,
    category TEXT,  -- investor, supplier, legal, logistics, design, food, events, corporate, team, personal
    notes TEXT,
    first_seen DATE,
    last_interaction DATE,
    status TEXT DEFAULT 'active',  -- active, dormant, closed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);
CREATE INDEX IF NOT EXISTS idx_contacts_category ON contacts(category);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);

-- Core: Companies / Organizations
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT,  -- supplier, logistics, legal, investor, partner, government, event
    country TEXT,
    city TEXT,
    address TEXT,
    website TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Junction: Contact ↔ Company (many-to-many)
CREATE TABLE IF NOT EXISTS contact_companies (
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    role TEXT,
    since DATE,
    PRIMARY KEY (contact_id, company_id)
);

-- Graph: Relationships between contacts
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    to_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    type TEXT NOT NULL,  -- introduced_by, works_with, reports_to, partner, investor, knows, family, referred_by
    context TEXT,
    strength INTEGER DEFAULT 5,  -- 1-10
    since DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_id, to_id, type)
);

CREATE INDEX IF NOT EXISTS idx_rel_from ON relationships(from_id);
CREATE INDEX IF NOT EXISTS idx_rel_to ON relationships(to_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(type);

-- Interactions log
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    type TEXT NOT NULL,  -- email, call, meeting, whatsapp, telegram, zoom, in_person
    direction TEXT,  -- inbound, outbound, mutual
    subject TEXT,
    summary TEXT,
    source TEXT,  -- gmail, calendar, manual, whatsapp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_int_contact ON interactions(contact_id);
CREATE INDEX IF NOT EXISTS idx_int_date ON interactions(date);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    status TEXT DEFAULT 'active',  -- active, completed, cancelled, on_hold
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Junction: Contact ↔ Project
CREATE TABLE IF NOT EXISTS project_contacts (
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    role TEXT,
    PRIMARY KEY (project_id, contact_id)
);

-- Flexible tags
CREATE TABLE IF NOT EXISTS tags (
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (contact_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

-- View: Full contact with company
CREATE VIEW IF NOT EXISTS v_contacts AS
SELECT
    c.*,
    GROUP_CONCAT(DISTINCT t.tag) as tags,
    GROUP_CONCAT(DISTINCT co.name || ' (' || COALESCE(cc.role, c.role) || ')') as companies_list
FROM contacts c
LEFT JOIN tags t ON t.contact_id = c.id
LEFT JOIN contact_companies cc ON cc.contact_id = c.id
LEFT JOIN companies co ON co.id = cc.company_id
GROUP BY c.id;

-- View: Relationship graph edges
CREATE VIEW IF NOT EXISTS v_graph AS
SELECT
    r.id,
    c1.name as from_name,
    c2.name as to_name,
    r.type,
    r.context,
    r.strength,
    c1.company as from_company,
    c2.company as to_company
FROM relationships r
JOIN contacts c1 ON c1.id = r.from_id
JOIN contacts c2 ON c2.id = r.to_id;
"""


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    return db


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    print(f"Database initialized at {DB_PATH}")
    return db


def upsert_contact(db, name, **kwargs):
    """Insert or update a contact by name."""
    existing = db.execute("SELECT id FROM contacts WHERE name = ?", (name,)).fetchone()
    if existing:
        sets = []
        vals = []
        for k, v in kwargs.items():
            if v is not None:
                sets.append(f"{k} = ?")
                vals.append(v)
        if sets:
            sets.append("updated_at = CURRENT_TIMESTAMP")
            vals.append(existing['id'])
            db.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE id = ?", vals)
        return existing['id']
    else:
        cols = ['name'] + [k for k, v in kwargs.items() if v is not None]
        vals = [name] + [v for v in kwargs.values() if v is not None]
        placeholders = ', '.join(['?'] * len(vals))
        col_names = ', '.join(cols)
        cur = db.execute(f"INSERT INTO contacts ({col_names}) VALUES ({placeholders})", vals)
        return cur.lastrowid


def upsert_company(db, name, **kwargs):
    """Insert or update a company by name."""
    existing = db.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()
    if existing:
        sets = []
        vals = []
        for k, v in kwargs.items():
            if v is not None:
                sets.append(f"{k} = ?")
                vals.append(v)
        if sets:
            vals.append(existing['id'])
            db.execute(f"UPDATE companies SET {', '.join(sets)} WHERE id = ?", vals)
        return existing['id']
    else:
        cols = ['name'] + [k for k, v in kwargs.items() if v is not None]
        vals = [name] + [v for v in kwargs.values() if v is not None]
        placeholders = ', '.join(['?'] * len(vals))
        col_names = ', '.join(cols)
        cur = db.execute(f"INSERT INTO companies ({col_names}) VALUES ({placeholders})", vals)
        return cur.lastrowid


def link_contact_company(db, contact_id, company_id, role=None):
    db.execute(
        "INSERT OR IGNORE INTO contact_companies (contact_id, company_id, role) VALUES (?, ?, ?)",
        (contact_id, company_id, role)
    )


def add_relationship(db, from_name, to_name, rel_type, context=None, strength=5):
    f = db.execute("SELECT id FROM contacts WHERE name = ?", (from_name,)).fetchone()
    t = db.execute("SELECT id FROM contacts WHERE name = ?", (to_name,)).fetchone()
    if not f or not t:
        print(f"Contact not found: {from_name if not f else to_name}")
        return
    db.execute(
        "INSERT OR REPLACE INTO relationships (from_id, to_id, type, context, strength) VALUES (?, ?, ?, ?, ?)",
        (f['id'], t['id'], rel_type, context, strength)
    )


def add_interaction(db, contact_name, date, int_type, direction=None, subject=None, summary=None, source=None):
    c = db.execute("SELECT id FROM contacts WHERE name = ?", (contact_name,)).fetchone()
    if not c:
        print(f"Contact not found: {contact_name}")
        return
    db.execute(
        "INSERT INTO interactions (contact_id, date, type, direction, subject, summary, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (c['id'], date, int_type, direction, subject, summary, source)
    )
    db.execute("UPDATE contacts SET last_interaction = ? WHERE id = ? AND (last_interaction IS NULL OR last_interaction < ?)",
               (date, c['id'], date))


def add_tag(db, contact_name, tag):
    c = db.execute("SELECT id FROM contacts WHERE name = ?", (contact_name,)).fetchone()
    if not c:
        return
    db.execute("INSERT OR IGNORE INTO tags (contact_id, tag) VALUES (?, ?)", (c['id'], tag))


def search_contacts(db, query):
    q = f"%{query}%"
    rows = db.execute("""
        SELECT c.*, GROUP_CONCAT(DISTINCT t.tag) as tags
        FROM contacts c
        LEFT JOIN tags t ON t.contact_id = c.id
        WHERE c.name LIKE ? OR c.full_name LIKE ? OR c.email LIKE ?
            OR c.company LIKE ? OR c.role LIKE ? OR c.notes LIKE ?
            OR c.category LIKE ?
        GROUP BY c.id
        ORDER BY c.last_interaction DESC NULLS LAST
    """, (q, q, q, q, q, q, q)).fetchall()
    return rows


def get_graph(db, name, depth=2):
    """Get relationship subgraph around a person, up to N hops."""
    contact = db.execute("SELECT id FROM contacts WHERE name = ?", (name,)).fetchone()
    if not contact:
        return []

    # Two-step: first get reachable nodes via recursive CTE, then enrich
    reachable = db.execute("""
        WITH RECURSIVE graph(id, name, depth, path, visited) AS (
            SELECT id, name, 0, name, ',' || CAST(id AS TEXT) || ','
            FROM contacts WHERE id = ?
            UNION ALL
            SELECT c.id, c.name, g.depth + 1, g.path || ' -> ' || c.name,
                   g.visited || CAST(c.id AS TEXT) || ','
            FROM graph g
            JOIN relationships r ON (r.from_id = g.id OR r.to_id = g.id)
            JOIN contacts c ON c.id = CASE WHEN r.from_id = g.id THEN r.to_id ELSE r.from_id END
            WHERE g.depth < ? AND g.visited NOT LIKE '%,' || CAST(c.id AS TEXT) || ',%'
        )
        SELECT DISTINCT id, name, MIN(depth) as depth, path
        FROM graph
        GROUP BY id
        ORDER BY depth, name
    """, (contact['id'], depth)).fetchall()

    # Enrich with relationship info
    results = []
    for row in reachable:
        outgoing = db.execute("""
            SELECT r.type, c.name FROM relationships r
            JOIN contacts c ON c.id = r.to_id
            WHERE r.from_id = ?
        """, (row['id'],)).fetchall()
        incoming = db.execute("""
            SELECT c.name, r.type FROM relationships r
            JOIN contacts c ON c.id = r.from_id
            WHERE r.to_id = ?
        """, (row['id'],)).fetchall()
        out_str = ', '.join(f"{r['type']} -> {r['name']}" for r in outgoing) if outgoing else ''
        in_str = ', '.join(f"{r['name']} -> {r['type']}" for r in incoming) if incoming else ''
        results.append({
            'name': row['name'], 'depth': row['depth'], 'path': row['path'],
            'outgoing': out_str, 'incoming': in_str
        })
    return results


def find_chain(db, name_a, name_b):
    """Find shortest connection path between two people."""
    a = db.execute("SELECT id FROM contacts WHERE name = ?", (name_a,)).fetchone()
    b = db.execute("SELECT id FROM contacts WHERE name = ?", (name_b,)).fetchone()
    if not a or not b:
        return None

    rows = db.execute("""
        WITH RECURSIVE chain(id, path, depth) AS (
            SELECT id, name, 0 FROM contacts WHERE id = ?
            UNION ALL
            SELECT c.id, chain.path || ' → [' || r.type || '] → ' || c.name, chain.depth + 1
            FROM chain
            JOIN relationships r ON (r.from_id = chain.id OR r.to_id = chain.id)
            JOIN contacts c ON c.id = CASE WHEN r.from_id = chain.id THEN r.to_id ELSE r.from_id END
            WHERE chain.depth < 6 AND INSTR(chain.path, c.name) = 0
        )
        SELECT path, depth FROM chain WHERE id = ?
        ORDER BY depth LIMIT 1
    """, (a['id'], b['id'])).fetchone()
    return rows


def stale_contacts(db, days=14):
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    rows = db.execute("""
        SELECT name, company, role, category, last_interaction,
            CAST(julianday('now') - julianday(COALESCE(last_interaction, first_seen, created_at)) AS INTEGER) as days_silent
        FROM contacts
        WHERE status = 'active'
            AND (last_interaction IS NULL OR last_interaction < ?)
        ORDER BY days_silent DESC
    """, (cutoff,)).fetchall()
    return rows


def get_stats(db):
    stats = {}
    stats['contacts'] = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    stats['active'] = db.execute("SELECT COUNT(*) FROM contacts WHERE status='active'").fetchone()[0]
    stats['companies'] = db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    stats['relationships'] = db.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    stats['interactions'] = db.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    stats['projects'] = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

    stats['by_category'] = dict(db.execute(
        "SELECT COALESCE(category, 'uncategorized'), COUNT(*) FROM contacts GROUP BY category ORDER BY COUNT(*) DESC"
    ).fetchall())

    stats['by_status'] = dict(db.execute(
        "SELECT status, COUNT(*) FROM contacts GROUP BY status"
    ).fetchall())

    stats['top_connected'] = db.execute("""
        SELECT c.name, COUNT(DISTINCT r.id) as connections
        FROM contacts c
        JOIN relationships r ON r.from_id = c.id OR r.to_id = c.id
        GROUP BY c.id
        ORDER BY connections DESC
        LIMIT 10
    """).fetchall()

    return stats


def export_json(db):
    contacts = db.execute("SELECT * FROM contacts ORDER BY name").fetchall()
    companies = db.execute("SELECT * FROM companies ORDER BY name").fetchall()
    relationships = db.execute("SELECT * FROM v_graph").fetchall()

    data = {
        'exported_at': datetime.now().isoformat(),
        'contacts': [dict(r) for r in contacts],
        'companies': [dict(r) for r in companies],
        'relationships': [dict(r) for r in relationships],
    }
    return json.dumps(data, indent=2, default=str)


def export_dot(db):
    """Export as Graphviz DOT format."""
    lines = ['digraph ContactGraph {', '  rankdir=LR;', '  node [shape=record, style=filled];', '']

    # Color by category
    colors = {
        'team': '#4CAF50', 'investor': '#FF9800', 'supplier': '#2196F3',
        'legal': '#9C27B0', 'logistics': '#00BCD4', 'events': '#E91E63',
        'food': '#8BC34A', 'corporate': '#607D8B', 'personal': '#FFC107',
        'design': '#FF5722', 'partner': '#3F51B5'
    }

    contacts = db.execute("SELECT id, name, company, category FROM contacts WHERE status='active'").fetchall()
    for c in contacts:
        color = colors.get(c['category'], '#EEEEEE')
        label = c['name']
        if c['company']:
            label += f"\\n{c['company']}"
        lines.append(f'  n{c["id"]} [label="{label}", fillcolor="{color}"];')

    lines.append('')

    rels = db.execute("SELECT from_id, to_id, type FROM relationships").fetchall()
    for r in rels:
        lines.append(f'  n{r["from_id"]} -> n{r["to_id"]} [label="{r["type"]}"];')

    lines.append('}')
    return '\n'.join(lines)


def generate_html(db):
    """Generate interactive D3.js force-directed graph."""
    contacts = db.execute("SELECT id, name, company, category, status FROM contacts WHERE status='active'").fetchall()
    rels = db.execute("""
        SELECT r.from_id, r.to_id, r.type, r.strength,
            c1.name as source_name, c2.name as target_name
        FROM relationships r
        JOIN contacts c1 ON c1.id = r.from_id
        JOIN contacts c2 ON c2.id = r.to_id
        WHERE c1.status = 'active' AND c2.status = 'active'
    """).fetchall()

    nodes = [{"id": c['id'], "name": c['name'], "company": c['company'] or '', "category": c['category'] or 'other'} for c in contacts]
    links = [{"source": r['from_id'], "target": r['to_id'], "type": r['type'], "strength": r['strength']} for r in rels]

    # Only include nodes that have at least one relationship
    connected_ids = set()
    for l in links:
        connected_ids.add(l['source'])
        connected_ids.add(l['target'])
    nodes = [n for n in nodes if n['id'] in connected_ids]

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Contact Graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
body {{ margin: 0; background: #1a1a2e; font-family: -apple-system, sans-serif; color: #fff; }}
svg {{ width: 100vw; height: 100vh; }}
.link {{ stroke-opacity: 0.4; }}
.node circle {{ stroke: #fff; stroke-width: 1.5px; cursor: pointer; }}
.node text {{ font-size: 11px; fill: #eee; pointer-events: none; }}
.tooltip {{ position: absolute; background: #16213e; border: 1px solid #0f3460; border-radius: 6px;
    padding: 8px 12px; font-size: 12px; pointer-events: none; opacity: 0; }}
h1 {{ position: fixed; top: 10px; left: 20px; font-size: 18px; opacity: 0.7; }}
.legend {{ position: fixed; bottom: 20px; left: 20px; font-size: 12px; opacity: 0.7; }}
.legend div {{ margin: 3px 0; }}
.legend span {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }}
</style></head><body>
<h1>Contact Graph</h1>
<div class="legend">
    <div><span style="background:#4CAF50"></span>Team</div>
    <div><span style="background:#FF9800"></span>Investor</div>
    <div><span style="background:#2196F3"></span>Supplier</div>
    <div><span style="background:#9C27B0"></span>Legal</div>
    <div><span style="background:#00BCD4"></span>Logistics</div>
    <div><span style="background:#3F51B5"></span>Partner</div>
    <div><span style="background:#E91E63"></span>Events</div>
    <div><span style="background:#607D8B"></span>Other</div>
</div>
<div class="tooltip" id="tooltip"></div>
<svg></svg>
<script>
const nodes = {json.dumps(nodes)};
const links = {json.dumps(links)};
const colors = {{team:'#4CAF50',investor:'#FF9800',supplier:'#2196F3',legal:'#9C27B0',
    logistics:'#00BCD4',events:'#E91E63',food:'#8BC34A',corporate:'#607D8B',
    personal:'#FFC107',design:'#FF5722',partner:'#3F51B5',other:'#607D8B'}};

const svg = d3.select('svg');
const width = window.innerWidth, height = window.innerHeight;
svg.attr('viewBox', [0, 0, width, height]);

const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d=>d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width/2, height/2))
    .force('collision', d3.forceCollide(30));

const link = svg.append('g').selectAll('line').data(links).join('line')
    .attr('class','link').attr('stroke','#444').attr('stroke-width', d=>Math.max(1,d.strength/3));

const node = svg.append('g').selectAll('g').data(nodes).join('g').attr('class','node')
    .call(d3.drag().on('start',(e,d)=>{{sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}})
        .on('drag',(e,d)=>{{d.fx=e.x;d.fy=e.y;}}).on('end',(e,d)=>{{sim.alphaTarget(0);d.fx=null;d.fy=null;}}));

node.append('circle').attr('r',10).attr('fill',d=>colors[d.category]||colors.other);
node.append('text').attr('dx',14).attr('dy',4).text(d=>d.name);

const tooltip = d3.select('#tooltip');
node.on('mouseover',(e,d)=>{{
    tooltip.style('opacity',1).html(`<b>${{d.name}}</b><br>${{d.company}}<br><i>${{d.category}}</i>`)
        .style('left',(e.pageX+10)+'px').style('top',(e.pageY-10)+'px');
}}).on('mouseout',()=>tooltip.style('opacity',0));

sim.on('tick',()=>{{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform',d=>`translate(${{d.x}},${{d.y}})`);
}});
</script></body></html>"""
    return html


def _rget(row, key, default=None):
    """Safe getter for sqlite3.Row objects (which don't support .get())."""
    try:
        val = row[key]
        return val if val is not None else default
    except (IndexError, KeyError):
        return default


def print_contacts(rows):
    if not rows:
        print("  (none)")
        return
    for r in rows:
        tags_v = _rget(r, 'tags')
        company_v = _rget(r, 'company')
        email_v = _rget(r, 'email')
        status_v = _rget(r, 'status')
        last_v = _rget(r, 'last_interaction')
        role_v = _rget(r, 'role', '')
        tags = f" [{tags_v}]" if tags_v else ""
        company = f" @ {company_v}" if company_v else ""
        email = f" <{email_v}>" if email_v else ""
        status = f" [{status_v}]" if status_v and status_v != 'active' else ""
        last = f" (last: {last_v})" if last_v else ""
        print(f"  {r['name']}{company}{email} — {role_v}{status}{last}{tags}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == 'init':
        init_db()
        return

    db = get_db()

    if cmd == 'find':
        query = sys.argv[2] if len(sys.argv) > 2 else ''
        rows = search_contacts(db, query)
        print(f"Found {len(rows)} contacts:")
        print_contacts(rows)

    elif cmd == 'graph':
        name = sys.argv[2]
        depth = int(sys.argv[3]) if len(sys.argv) > 3 else 2
        rows = get_graph(db, name, depth)
        if not rows:
            print(f"No graph found for '{name}'")
        else:
            for r in rows:
                indent = "  " * r['depth']
                out = r['outgoing'] or ''
                print(f"{indent}[{r['depth']}] {r['name']}: {out}")

    elif cmd == 'chain':
        if len(sys.argv) < 4:
            print("Usage: chain 'Name A' 'Name B'")
            return
        result = find_chain(db, sys.argv[2], sys.argv[3])
        if result:
            print(f"Chain (depth {result['depth']}): {result['path']}")
        else:
            print("No connection found")

    elif cmd == 'stale':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 14
        rows = stale_contacts(db, days)
        print(f"Contacts with no interaction in {days}+ days:")
        for r in rows:
            print(f"  {r['name']} ({r['company'] or 'no company'}) — {r['days_silent']} days silent")

    elif cmd == 'stats':
        s = get_stats(db)
        print(f"Contacts: {s['contacts']} (active: {s['active']})")
        print(f"Companies: {s['companies']}")
        print(f"Relationships: {s['relationships']}")
        print(f"Interactions: {s['interactions']}")
        print(f"Projects: {s['projects']}")
        print("\nBy category:")
        for cat, count in s['by_category'].items():
            print(f"  {cat}: {count}")
        if s['top_connected']:
            print("\nTop connected:")
            for r in s['top_connected']:
                print(f"  {r['name']}: {r['connections']} connections")

    elif cmd == 'export':
        print(export_json(db))

    elif cmd == 'dot':
        print(export_dot(db))

    elif cmd == 'html':
        output = Path(__file__).parent.parent / "outputs" / "contact_graph.html"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(generate_html(db))
        print(f"HTML graph written to {output}")

    elif cmd == 'sql':
        if len(sys.argv) < 3:
            print("Usage: sql 'SELECT ...'")
            return
        query = sys.argv[2]
        cur = db.execute(query)
        # Detect write queries and commit
        q_upper = query.strip().upper()
        if q_upper.startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'DROP', 'ALTER')):
            db.commit()
            print(f"OK ({cur.rowcount} rows affected)")
        else:
            for r in cur.fetchall():
                print(dict(r))

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == '__main__':
    main()
