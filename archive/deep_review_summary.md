 Virtual Graph - Deep Review Summary

     Project Overview

     Virtual Graph enables graph-like queries over enterprise relational data without migrating to a graph database. The system uses an 
     LLM to reason over SQL using a discovered ontology and learned SQL patterns.

     Current Version: 0.8.0 (from pyproject.toml)
     Database: PostgreSQL 14 with supply chain schema (15 tables, ~130K rows)

     ---
     Core Architecture: Traffic Light Routing

     Queries are classified by complexity and routed to appropriate handlers:

     | Complexity | Description         | Handler                              | Example                             |
     |------------|---------------------|--------------------------------------|-------------------------------------|
     | GREEN      | Simple FK joins     | Direct SQL                           | "Get supplier details"              |
     | YELLOW     | Recursive traversal | traverse() with frontier-batched BFS | "Find all tier-3 suppliers"         |
     | RED        | Network algorithms  | NetworkX (Dijkstra, centrality)      | "Shortest route between facilities" |

     ---
     Handler System (src/virt_graph/handlers/)

     Safety Infrastructure (Non-Negotiable Limits)

     MAX_DEPTH = 50        # Absolute traversal depth limit
     MAX_NODES = 10,000    # Max nodes per traversal (configurable)
     MAX_RESULTS = 1,000   # Max rows returned
     QUERY_TIMEOUT = 30s   # Per-query timeout

     Key Handlers

     YELLOW - Traversal (traversal.py):
     - traverse() - Generic BFS with frontier batching (one query per depth, not per node)
     - traverse_collecting() - Convenience wrapper for "find all X reachable from Y"
     - bom_explode() - Specialized for Bill of Materials with quantity aggregation

     RED - Pathfinding (pathfinding.py):
     - shortest_path() - Bidirectional Dijkstra with weighted edges
     - all_shortest_paths() - Multiple equivalent optimal routes

     RED - Network Analysis (network.py):
     - centrality() - Degree/betweenness/closeness/PageRank
     - connected_components() - Find graph clusters
     - neighbors() - Direct neighbor lookup

     Configurable Limits (v0.8.0)

     Handlers now accept:
     - max_nodes: int - Override default 10,000
     - skip_estimation: bool - Bypass size check (caller responsibility)
     - estimation_config: EstimationConfig - Fine-tune estimation parameters

     ---
     Ontology System

     Structure (ontology/supply_chain.yaml)

     LinkML format with Virtual Graph extensions:
     - 8 Entity Classes (TBox): Supplier, Part, Product, Facility, Customer, Order, Shipment, SupplierCertification
     - 13 Relationship Classes (RBox): Organized by complexity (GREEN/YELLOW/RED)

     Key YELLOW Relationships (Recursive)

     | Relationship | Edge Table                         | Use Case                |
     |--------------|------------------------------------|-------------------------|
     | SuppliesTo   | supplier_relationships (817 edges) | Tier network traversal  |
     | ComponentOf  | bill_of_materials (14,283 edges)   | BOM explosion/implosion |

     Key RED Relationship (Weighted)

     | Relationship | Edge Table                   | Weights                                   |
     |--------------|------------------------------|-------------------------------------------|
     | ConnectsTo   | transport_routes (197 edges) | distance_km, cost_usd, transit_time_hours |

     OntologyAccessor API (src/virt_graph/ontology.py)

     ontology = OntologyAccessor()  # Loads and validates
     ontology.get_class_table("Supplier")  # → "suppliers"
     ontology.get_role_keys("SuppliesTo")  # → ("seller_id", "buyer_id")
     ontology.get_role_complexity("ConnectsTo")  # → "RED"

     Two-Layer Validation

     1. Layer 1: LinkML structure (linkml-lint)
     2. Layer 2: VG annotations (OntologyAccessor validates on load)

     ---
     Estimator Module (src/virt_graph/estimator/)

     Components

     1. GraphSampler - Lightweight BFS sampling (default 5 levels)
       - Detects: growth_trend, convergence_ratio, has_cycles, hub_detected, terminated
     2. Estimation Model - Adaptive damping with extrapolation
     damping = base_damping × convergence_multiplier × decreasing_trend_multiplier
       - Reduces over-estimation for DAGs with node sharing
     3. Table Bounds - DDL introspection for hard ceiling
       - Caps all estimates to max distinct nodes in edge table
     4. Runtime Guards - Decision engine
     GuardResult(
         safe_to_proceed: bool,
         recommended_action: "traverse" | "abort" | "warn_and_proceed" | "switch_networkx",
         estimated_nodes: int
     )

     Guard Decision Flow

     1. Hub detected? → ABORT
     2. Junction table? → WARN
     3. Cycles detected? → WARN (consider NetworkX)
     4. Terminated in sampling? → TRAVERSE (exact count)
     5. Estimate > max_nodes? → ABORT or WARN_AND_PROCEED based on table_bound

     ---
     Pattern System (patterns/)

     Template Categories

     | Category          | Templates                                 | Use Case          |
     |-------------------|-------------------------------------------|-------------------|
     | traversal/        | tier_traversal, bom_explosion, where_used | YELLOW handlers   |
     | pathfinding/      | shortest_path, all_paths                  | RED handlers      |
     | aggregation/      | impact_analysis                           | Downstream impact |
     | network-analysis/ | centrality, components                    | Graph metrics     |

     Template Structure

     applicability:
       query_signals: ["keywords", "regex patterns"]
     ontology_bindings:
       node_class: EntityClass
       edge_relationship: RelationshipName
     variants:
       upstream_all: { handler_params: {...} }
       downstream_by_tier: { handler_params: {...} }

     Raw Patterns (patterns/raw/)

     22 discovered patterns with recorded SQL and execution times - used to derive templates.

     ---
     Skills System (.claude/skills/)

     | Skill     | Purpose                          | When to Use                          |
     |-----------|----------------------------------|--------------------------------------|
     | schema/   | Live DDL introspection           | Mapping ontology to SQL              |
     | patterns/ | Pattern template matching        | Query involves traversal/pathfinding |
     | handlers/ | Handler signatures and execution | Need parameter resolution            |

     ---
     Database Schema

     Key Self-Referential Tables (Graph Edges)

     - supplier_relationships - Tier network (YELLOW)
     - bill_of_materials - Part hierarchy (YELLOW)
     - transport_routes - Facility network with weights (RED)

     Named Test Entities

     - Suppliers: Acme Corp (SUP00001), GlobalTech Industries, Pacific Components
     - Products: Turbo Encabulator (TURBO-001), Flux Capacitor (FLUX-001)
     - Facilities: Chicago Warehouse (FAC-CHI), LA Distribution Center (FAC-LA)

     ---
     Testing Strategy

     Gate-based validation:
     - Gate 1: Database connection, core handlers
     - Gate 2: Ontology loading, traversal basics
     - Gate 3: Pattern matching (36KB of tests)
     - Gate 4: Pathfinding and network algorithms
     - Gate 5: Benchmark infrastructure
     - Estimator: Sampling, estimation, guards

     Preference for integration tests over unit tests.

     ---
     Critical Implementation Rules

     1. Frontier batching mandatory: One SQL query per depth level, never per node
     2. Size guards: Check before NetworkX load; >5K nodes must warn or fail
     3. Hybrid SQL/Python: Python orchestrates, SQL filters; never bulk load tables
     4. BOM direction: ComponentOf is child→parent; for explosion swap from/to columns
     5. Supply chain direction: inbound=upstream, outbound=downstream

     ---
     Key Files Reference

     | Area      | Files                                                                    |
     |-----------|--------------------------------------------------------------------------|
     | Handlers  | src/virt_graph/handlers/{base,traversal,pathfinding,network}.py          |
     | Ontology  | ontology/supply_chain.yaml, src/virt_graph/ontology.py                   |
     | Estimator | src/virt_graph/estimator/{sampler,models,bounds,guards}.py               |
     | Patterns  | patterns/templates/{traversal,pathfinding,aggregation,network-analysis}/ |
     | Skills    | .claude/skills/{schema,patterns,handlers}/SKILL.md                       |
     | Tests     | tests/test_gate*.py, tests/test_estimator.py                             |

     ---
     Next Steps

     This deep review provides context for any implementation work. The system is at v0.8.0 with:
     - Core handlers working
     - Ontology loaded and validated
     - Estimator with adaptive damping
     - Pattern templates defined
     - Skills for Claude Code integration

     Ready to discuss specific implementation tasks or questions about the architecture.


⏺ The deep review is complete. I now have a rich understanding of the Virtual Graph project:

  Key Insights:

  1. Three-Layer Safety Model - Frontier batching (SQL), estimation (sampling), and runtime guards work together to prevent runaway
  queries
  2. Schema-Parameterized Handlers - All handlers are domain-agnostic; they work with any table/FK configuration resolved via ontology
  3. Adaptive Estimation - The estimator uses damping factors tuned for DAGs with node sharing, preventing dangerous over-estimation
  4. LinkML + VG Extensions - The ontology bridges semantic concepts (SuppliesTo, ComponentOf) to physical SQL (tables, FK columns)
  5. Pattern-Based Query Routing - Templates match queries to handlers with variants for different use cases (upstream vs downstream,
  weighted vs unweighted)

  The system is at v0.8.0 with core functionality working. Let me know what you'd like to work on next - whether it's implementing new
  features, fixing issues, or exploring specific areas in more depth.