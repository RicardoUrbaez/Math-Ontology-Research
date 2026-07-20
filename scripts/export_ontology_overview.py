from __future__ import annotations

import json
from html import escape
from pathlib import Path
from urllib.parse import unquote

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ontologies" / "merged" / "math_accessibility_kg_week3_clean_500.owl"
OUT_DIR = ROOT / "reports" / "ontology_whole_view"
OUT_HTML = OUT_DIR / "math_accessibility_kg_whole_overview.html"

MATHKG = Namespace("http://example.org/mathkg/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def local_name(uri: URIRef) -> str:
    text = str(uri)
    tail = text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return unquote(tail).replace("_", " ")


def first_literal(graph: Graph, subject: URIRef, predicates: list[URIRef]) -> str:
    for predicate in predicates:
        for value in graph.objects(subject, predicate):
            if isinstance(value, Literal):
                return str(value)
    return ""


def first_resource(graph: Graph, subject: URIRef, predicate: URIRef) -> str:
    for value in graph.objects(subject, predicate):
        if isinstance(value, URIRef):
            return local_name(value)
        if isinstance(value, Literal):
            return str(value)
    return ""


def iri_id(uri: URIRef) -> str:
    if str(uri) == str(OWL.Thing):
        return "owl:Thing"
    if str(uri).startswith(str(MATHKG)):
        return "mathkg:" + str(uri)[len(str(MATHKG)) :]
    return str(uri)


def build_data() -> dict:
    graph = Graph()
    graph.parse(SOURCE)

    class_uris = set(graph.subjects(RDF.type, OWL.Class))
    class_uris |= set(graph.subjects(RDFS.subClassOf, None))
    class_uris = {
        uri
        for uri in class_uris
        if isinstance(uri, URIRef)
        and (str(uri).startswith(str(MATHKG)) or str(uri) == str(OWL.Thing))
    }
    class_uris.add(OWL.Thing)

    links = []
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if not isinstance(child, URIRef) or not isinstance(parent, URIRef):
            continue
        if not str(child).startswith(str(MATHKG)):
            continue
        if not (str(parent).startswith(str(MATHKG)) or str(parent) == str(OWL.Thing)):
            continue
        class_uris.add(child)
        class_uris.add(parent)
        links.append({"source": iri_id(parent), "target": iri_id(child)})

    nodes = []
    for uri in sorted(class_uris, key=lambda item: iri_id(item).lower()):
        label = first_literal(graph, uri, [RDFS.label, SKOS.prefLabel]) or local_name(uri)
        definition = first_literal(graph, uri, [SKOS.definition])
        example = first_literal(graph, uri, [SKOS.example])
        kind_role = first_resource(graph, uri, MATHKG.kindRoleType)
        semantic_type = first_resource(graph, uri, MATHKG.semanticType)
        node_id = iri_id(uri)
        if node_id == "owl:Thing":
            kind_role = "root"
            semantic_type = "root"
        elif node_id.endswith("MathematicalConcept"):
            kind_role = "root"
            semantic_type = "root"
        elif node_id.endswith("KindConcept"):
            kind_role = "kind-root"
            semantic_type = "kind"
        elif node_id.endswith("RoleConcept"):
            kind_role = "role-root"
            semantic_type = "role"

        nodes.append(
            {
                "id": node_id,
                "label": label,
                "definition": definition,
                "example": example,
                "kindRole": kind_role or "unclassified",
                "semanticType": semantic_type or "unspecified",
                "iri": str(uri),
            }
        )

    return {
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "nodes": nodes,
        "links": links,
    }


def render_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    node_count = len(data["nodes"])
    link_count = len(data["links"])
    source = escape(data["source"])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Math Accessibility KG Whole Overview</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #0f172a;
      --muted: #64748b;
      --line: #d7dee8;
      --accent: #2563eb;
      --kind: #0f766e;
      --role: #b45309;
      --root: #334155;
      --faint: #e9eef5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
      overflow: hidden;
    }}
    .shell {{
      display: grid;
      grid-template-columns: 320px 1fr 340px;
      height: 100vh;
      min-width: 980px;
    }}
    aside {{
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 18px;
      overflow: auto;
    }}
    .details {{
      border-right: 0;
      border-left: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 20px 0 8px;
      font-size: 13px;
      color: var(--muted);
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin: 16px 0;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfdff;
    }}
    .stat b {{
      display: block;
      font-size: 22px;
    }}
    .stat span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      color: var(--ink);
      font: inherit;
      font-size: 14px;
      padding: 10px 12px;
      outline: none;
    }}
    input:focus, select:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
    }}
    .toggles {{
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }}
    label.check {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
    }}
    label.check input {{
      width: 16px;
      height: 16px;
    }}
    main {{
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(90deg, rgba(15, 23, 42, 0.04) 1px, transparent 1px),
        linear-gradient(rgba(15, 23, 42, 0.04) 1px, transparent 1px);
      background-size: 36px 36px;
    }}
    .toolbar {{
      position: absolute;
      top: 14px;
      left: 14px;
      right: 14px;
      z-index: 2;
      display: flex;
      align-items: center;
      gap: 8px;
      pointer-events: none;
    }}
    button {{
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      border-radius: 8px;
      padding: 8px 11px;
      font: inherit;
      font-size: 13px;
      cursor: pointer;
      pointer-events: auto;
    }}
    button:hover {{ border-color: var(--accent); }}
    .hint {{
      margin-left: auto;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.88);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 12px;
      pointer-events: none;
    }}
    svg {{
      width: 100%;
      height: 100%;
      display: block;
      cursor: grab;
    }}
    svg.dragging {{ cursor: grabbing; }}
    .edge {{
      stroke: #94a3b8;
      stroke-width: 1.15;
      stroke-opacity: 0.42;
      fill: none;
    }}
    .edge.hidden, .node.hidden, .label.hidden {{ display: none; }}
    .node circle {{
      stroke: white;
      stroke-width: 1.5;
      cursor: pointer;
    }}
    .node.root circle {{ fill: var(--root); }}
    .node.kind circle {{ fill: var(--kind); }}
    .node.role circle {{ fill: var(--role); }}
    .node.unclassified circle {{ fill: #64748b; }}
    .node.dim circle {{ opacity: 0.2; }}
    .label {{
      font-size: 10px;
      fill: #1e293b;
      paint-order: stroke;
      stroke: rgba(255,255,255,0.85);
      stroke-width: 3px;
      stroke-linejoin: round;
      pointer-events: none;
    }}
    .label.dim {{ opacity: 0.25; }}
    .selected circle {{
      stroke: #111827;
      stroke-width: 3;
    }}
    .legend {{
      display: grid;
      grid-template-columns: 12px 1fr;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 13px;
      margin: 8px 0;
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }}
    .result-list {{
      display: grid;
      gap: 6px;
      margin-top: 8px;
    }}
    .result {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
      padding: 8px 10px;
      cursor: pointer;
    }}
    .result:hover {{ border-color: var(--accent); }}
    .result b {{
      display: block;
      font-size: 13px;
      line-height: 1.25;
    }}
    .result span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .field {{
      border-top: 1px solid var(--line);
      padding-top: 12px;
      margin-top: 12px;
    }}
    .field .name {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
      text-transform: uppercase;
    }}
    .field .value {{
      font-size: 14px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 1180px) {{
      .shell {{ grid-template-columns: 280px 1fr 300px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Math Accessibility KG</h1>
      <div class="meta">Whole-ontology class overview from <code>{source}</code>.</div>
      <div class="stats">
        <div class="stat"><b>{node_count}</b><span>classes</span></div>
        <div class="stat"><b>{link_count}</b><span>subclass links</span></div>
      </div>

      <h2>Find</h2>
      <input id="search" type="search" placeholder="Search concept label or IRI">

      <h2>Filter</h2>
      <select id="roleFilter">
        <option value="all">All concepts</option>
        <option value="kind">Kind concepts</option>
        <option value="role">Role concepts</option>
        <option value="root">Root classes</option>
      </select>
      <div class="toggles">
        <label class="check"><input id="labels" type="checkbox"> Show all labels</label>
        <label class="check"><input id="matchedLabels" type="checkbox" checked> Show labels for matches</label>
      </div>

      <h2>Legend</h2>
      <div class="legend"><span class="swatch" style="background: var(--root)"></span><span>Root / organizing class</span></div>
      <div class="legend"><span class="swatch" style="background: var(--kind)"></span><span>Kind concept</span></div>
      <div class="legend"><span class="swatch" style="background: var(--role)"></span><span>Role concept</span></div>

      <h2>Matches</h2>
      <div id="results" class="result-list"></div>
    </aside>

    <main>
      <div class="toolbar">
        <button id="zoomIn">Zoom +</button>
        <button id="zoomOut">Zoom -</button>
        <button id="reset">Reset</button>
        <span class="hint">Drag to pan. Click a node for details.</span>
      </div>
      <svg id="canvas" viewBox="0 0 1500 1000" aria-label="Whole ontology graph"></svg>
    </main>

    <aside class="details">
      <h1 id="detailTitle">Select a concept</h1>
      <div class="meta" id="detailSubtitle">Click any node in the graph or a search result.</div>
      <div class="field"><div class="name">Kind / role</div><div class="value" id="detailRole">-</div></div>
      <div class="field"><div class="name">Semantic type</div><div class="value" id="detailType">-</div></div>
      <div class="field"><div class="name">Definition</div><div class="value" id="detailDefinition">-</div></div>
      <div class="field"><div class="name">Example</div><div class="value" id="detailExample">-</div></div>
      <div class="field"><div class="name">IRI</div><div class="value" id="detailIri">-</div></div>
    </aside>
  </div>

  <script>
    const DATA = {payload};
    const svg = document.getElementById("canvas");
    const search = document.getElementById("search");
    const roleFilter = document.getElementById("roleFilter");
    const labelsToggle = document.getElementById("labels");
    const matchedLabelsToggle = document.getElementById("matchedLabels");
    const results = document.getElementById("results");
    const byId = new Map(DATA.nodes.map((node) => [node.id, node]));
    const children = new Map();
    DATA.links.forEach((link) => {{
      if (!children.has(link.source)) children.set(link.source, []);
      children.get(link.source).push(link.target);
    }});

    const positions = new Map();
    function distribute(ids, cx, cy, rx, ry, start, end) {{
      const sorted = ids.slice().sort((a, b) => byId.get(a).label.localeCompare(byId.get(b).label));
      sorted.forEach((id, index) => {{
        const t = sorted.length === 1 ? 0.5 : index / (sorted.length - 1);
        const angle = start + (end - start) * t;
        const wave = 1 + 0.08 * Math.sin(index * 2.21);
        positions.set(id, {{
          x: cx + Math.cos(angle) * rx * wave,
          y: cy + Math.sin(angle) * ry * wave,
        }});
      }});
    }}

    positions.set("owl:Thing", {{ x: 750, y: 120 }});
    positions.set("mathkg:MathematicalConcept", {{ x: 750, y: 250 }});
    positions.set("mathkg:KindConcept", {{ x: 560, y: 455 }});
    positions.set("mathkg:RoleConcept", {{ x: 1040, y: 455 }});
    distribute(children.get("mathkg:KindConcept") || [], 560, 545, 455, 355, -2.85, 2.85);
    distribute(children.get("mathkg:RoleConcept") || [], 1040, 570, 190, 180, -2.25, 2.25);

    DATA.nodes.forEach((node, index) => {{
      if (!positions.has(node.id)) {{
        positions.set(node.id, {{
          x: 200 + (index % 30) * 38,
          y: 860 + Math.floor(index / 30) * 26,
        }});
      }}
    }});

    const viewport = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.appendChild(viewport);
    const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const labelLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    viewport.append(edgeLayer, nodeLayer, labelLayer);

    const edgeElements = [];
    DATA.links.forEach((link) => {{
      const a = positions.get(link.source);
      const b = positions.get(link.target);
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const midY = (a.y + b.y) / 2;
      path.setAttribute("d", `M ${{a.x}} ${{a.y}} C ${{a.x}} ${{midY}}, ${{b.x}} ${{midY}}, ${{b.x}} ${{b.y}}`);
      path.setAttribute("class", "edge");
      path.dataset.source = link.source;
      path.dataset.target = link.target;
      edgeLayer.appendChild(path);
      edgeElements.push(path);
    }});

    const nodeElements = new Map();
    const labelElements = new Map();
    DATA.nodes.forEach((node) => {{
      const pos = positions.get(node.id);
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      const cls = node.kindRole.includes("role") ? "role" : node.kindRole.includes("kind") ? "kind" : node.kindRole.includes("root") ? "root" : "unclassified";
      const radius = cls === "root" ? 10 : node.id.endsWith("Concept") ? 8 : 4.5;
      group.setAttribute("class", `node ${{cls}}`);
      group.setAttribute("transform", `translate(${{pos.x}}, ${{pos.y}})`);
      group.dataset.id = node.id;
      circle.setAttribute("r", radius);
      group.appendChild(circle);
      group.addEventListener("click", () => selectNode(node.id));
      nodeLayer.appendChild(group);
      nodeElements.set(node.id, group);

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.textContent = node.label;
      text.setAttribute("class", "label hidden");
      text.setAttribute("x", pos.x + radius + 4);
      text.setAttribute("y", pos.y + 3);
      labelLayer.appendChild(text);
      labelElements.set(node.id, text);
    }});

    let selectedId = null;
    let scale = 1;
    let panX = 0;
    let panY = 0;
    function applyTransform() {{
      viewport.setAttribute("transform", `translate(${{panX}} ${{panY}}) scale(${{scale}})`);
    }}
    function roleBucket(node) {{
      if (node.kindRole.includes("kind")) return "kind";
      if (node.kindRole.includes("role")) return "role";
      if (node.kindRole.includes("root")) return "root";
      return "other";
    }}
    function matchesNode(node) {{
      const query = search.value.trim().toLowerCase();
      const role = roleFilter.value;
      const roleOk = role === "all" || roleBucket(node) === role;
      const queryOk = !query || [node.label, node.id, node.iri, node.definition].some((value) => value.toLowerCase().includes(query));
      return roleOk && queryOk;
    }}
    function updateFilter() {{
      const matched = new Set(DATA.nodes.filter(matchesNode).map((node) => node.id));
      const hasQuery = search.value.trim().length > 0 || roleFilter.value !== "all";
      DATA.nodes.forEach((node) => {{
        const el = nodeElements.get(node.id);
        const label = labelElements.get(node.id);
        const isMatch = matched.has(node.id);
        el.classList.toggle("dim", hasQuery && !isMatch);
        label.classList.toggle("dim", hasQuery && !isMatch);
        label.classList.toggle("hidden", !(labelsToggle.checked || (matchedLabelsToggle.checked && hasQuery && isMatch) || node.id.endsWith("Concept") || node.id === "owl:Thing"));
      }});
      edgeElements.forEach((edge) => {{
        const visible = matched.has(edge.dataset.source) || matched.has(edge.dataset.target) || !hasQuery;
        edge.classList.toggle("hidden", !visible);
      }});
      renderResults([...matched].slice(0, 40));
    }}
    function renderResults(ids) {{
      results.innerHTML = "";
      ids
        .map((id) => byId.get(id))
        .sort((a, b) => a.label.localeCompare(b.label))
        .forEach((node) => {{
          const item = document.createElement("div");
          item.className = "result";
          item.innerHTML = `<b>${{escapeHtml(node.label)}}</b><span>${{escapeHtml(node.kindRole)}} - ${{escapeHtml(node.semanticType)}}</span>`;
          item.addEventListener("click", () => selectNode(node.id));
          results.appendChild(item);
        }});
    }}
    function escapeHtml(value) {{
      return value.replace(/[&<>"']/g, (ch) => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[ch]));
    }}
    function selectNode(id) {{
      selectedId = id;
      nodeElements.forEach((el, nodeId) => el.classList.toggle("selected", nodeId === id));
      const node = byId.get(id);
      document.getElementById("detailTitle").textContent = node.label;
      document.getElementById("detailSubtitle").textContent = node.id;
      document.getElementById("detailRole").textContent = node.kindRole || "-";
      document.getElementById("detailType").textContent = node.semanticType || "-";
      document.getElementById("detailDefinition").textContent = node.definition || "-";
      document.getElementById("detailExample").textContent = node.example || "-";
      document.getElementById("detailIri").textContent = node.iri || "-";
    }}

    search.addEventListener("input", updateFilter);
    roleFilter.addEventListener("change", updateFilter);
    labelsToggle.addEventListener("change", updateFilter);
    matchedLabelsToggle.addEventListener("change", updateFilter);
    document.getElementById("zoomIn").addEventListener("click", () => {{ scale *= 1.18; applyTransform(); }});
    document.getElementById("zoomOut").addEventListener("click", () => {{ scale /= 1.18; applyTransform(); }});
    document.getElementById("reset").addEventListener("click", () => {{ scale = 1; panX = 0; panY = 0; applyTransform(); }});

    let dragging = false;
    let last = null;
    svg.addEventListener("pointerdown", (event) => {{
      dragging = true;
      last = {{ x: event.clientX, y: event.clientY }};
      svg.classList.add("dragging");
      svg.setPointerCapture(event.pointerId);
    }});
    svg.addEventListener("pointermove", (event) => {{
      if (!dragging) return;
      panX += event.clientX - last.x;
      panY += event.clientY - last.y;
      last = {{ x: event.clientX, y: event.clientY }};
      applyTransform();
    }});
    svg.addEventListener("pointerup", () => {{
      dragging = false;
      svg.classList.remove("dragging");
    }});
    svg.addEventListener("wheel", (event) => {{
      event.preventDefault();
      scale *= event.deltaY < 0 ? 1.08 : 0.92;
      scale = Math.max(0.25, Math.min(4, scale));
      applyTransform();
    }}, {{ passive: false }});

    selectNode("mathkg:MathematicalConcept");
    updateFilter();
    applyTransform();
  </script>
</body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = build_data()
    OUT_HTML.write_text(render_html(data), encoding="utf-8")
    print(f"Wrote {OUT_HTML}")
    print(f"Classes: {len(data['nodes'])}")
    print(f"Subclass links: {len(data['links'])}")


if __name__ == "__main__":
    main()
