# Cascade shop stress-test dataflow

Demo break: multi-source rename on `raw_orders` + `raw_customers`, remediated by **DeepSeek v3.2**.

## 1. Original data flow (healthy)

Lineage as ingested into DataHub. Key columns shown on the break-relevant path.

```mermaid
flowchart TB
  subgraph raw [Raw]
    RC["raw_customers<br/>customer_id, email, …"]
    RO["raw_orders<br/>order_id, user_id, amount_cents, …"]
    RI["raw_order_items<br/>…, line_amount_cents"]
    RP[raw_products]
  end

  subgraph stg [Staging]
    SC["stg_customers<br/>email"]
    SO["stg_orders<br/>user_id, amount_cents"]
    SI[stg_order_items]
    SP[stg_products]
  end

  subgraph mid [Intermediate]
    INT["int_orders_enriched<br/>user_id, amount_cents, email"]
  end

  subgraph marts [Marts]
    FO["fct_orders<br/>user_id, amount_cents"]
    FI["fct_order_items<br/>user_id, line_amount_cents"]
    MCR["mart_customer_revenue<br/>user_id, email, revenue"]
  end

  RC --> SC
  RO --> SO
  RI --> SI
  RP --> SP
  RP --> SI
  SO --> INT
  SC --> INT
  INT --> FO
  SI --> FI
  SO --> FI
  FO --> MCR
  SC --> MCR
```

## 2. After the breaking change (before Cascade)

PR-style renames on raw only:

| Source | Renames |
|--------|---------|
| `raw_orders` | `user_id` → `customer_id`, `amount_cents` → `amount_usd_cents` |
| `raw_customers` | `email` → `email_address` |

Downstream SQL still reads the **old** names → broken edges (red).

```mermaid
flowchart TB
  subgraph raw [Raw — changed]
    RC["raw_customers<br/>email_address ✎"]
    RO["raw_orders<br/>customer_id ✎<br/>amount_usd_cents ✎"]
    RI["raw_order_items<br/>line_amount_cents unchanged"]
    RP[raw_products]
  end

  subgraph stg [Staging — still old]
    SC["stg_customers<br/>reads email ✗"]
    SO["stg_orders<br/>reads user_id, amount_cents ✗"]
    SI[stg_order_items]
    SP[stg_products]
  end

  subgraph mid [Intermediate — still old]
    INT["int_orders_enriched<br/>o.user_id, amount_cents ✗"]
  end

  subgraph marts [Marts — still old]
    FO["fct_orders ✗"]
    FI["fct_order_items<br/>o.user_id ✗<br/>i.line_amount_cents OK"]
    MCR["mart_customer_revenue ✗"]
  end

  RC -.->|broken| SC
  RO -.->|broken| SO
  RI --> SI
  RP --> SP
  RP --> SI
  SO --> INT
  SC --> INT
  INT --> FO
  SI --> FI
  SO --> FI
  FO --> MCR
  SC --> MCR

  classDef broken fill:#3b1111,stroke:#f66,color:#fee
  class SC,SO,INT,FO,FI,MCR broken
```

Blast radius Cascade saw (live DataHub):  
`stg_orders`, `stg_customers`, `int_orders_enriched`, `fct_orders`, `fct_order_items`, `mart_customer_revenue`.

## 3. Final flow after DeepSeek fix

Cascade + DeepSeek rewrote the six downstream models. New upstream names are read; `line_amount_cents` on items is left alone.

```mermaid
flowchart TB
  subgraph raw [Raw]
    RC["raw_customers<br/>email_address"]
    RO["raw_orders<br/>customer_id, amount_usd_cents"]
    RI["raw_order_items<br/>line_amount_cents"]
    RP[raw_products]
  end

  subgraph stg [Staging — fixed]
    SC["stg_customers<br/>email_address"]
    SO["stg_orders<br/>customer_id, amount_usd_cents"]
    SI[stg_order_items]
    SP[stg_products]
  end

  subgraph mid [Intermediate — fixed]
    INT["int_orders_enriched<br/>customer_id, amount_usd_cents"]
  end

  subgraph marts [Marts — fixed]
    FO["fct_orders<br/>customer_id, amount_usd_cents"]
    FI["fct_order_items<br/>o.customer_id<br/>i.line_amount_cents"]
    MCR["mart_customer_revenue<br/>customer_id, amount_usd_cents"]
  end

  RC --> SC
  RO --> SO
  RI --> SI
  RP --> SP
  RP --> SI
  SO --> INT
  SC --> INT
  INT --> FO
  SI --> FI
  SO --> FI
  FO --> MCR
  SC --> MCR

  classDef fixed fill:#113b11,stroke:#6f6,color:#efe
  class SC,SO,INT,FO,FI,MCR fixed
```

### Column mapping (stress-test path)

```mermaid
flowchart LR
  subgraph before [Before break]
    B1[user_id]
    B2[amount_cents]
    B3[email]
  end

  subgraph change [Raw rename]
    C1[customer_id]
    C2[amount_usd_cents]
    C3[email_address]
  end

  subgraph after [DeepSeek downstream]
    A1[reads customer_id]
    A2[reads amount_usd_cents]
    A3[reads email_address]
    A4[keeps line_amount_cents]
  end

  B1 -->|FIELD_RENAMED| C1 --> A1
  B2 -->|FIELD_RENAMED| C2 --> A2
  B3 -->|FIELD_RENAMED| C3 --> A3
  A4 -.->|not in Changes — untouched| A4
```

Artifacts from the demo run: `/tmp/cascade-gate-deepseek-v3-2-apply/` (`downstream_pr.diff`, `rewritten/*.sql`).
