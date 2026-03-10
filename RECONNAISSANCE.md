
# RECONNAISSANCE.md

## 1. Primary Data Ingestion Path

Raw data is ingested via seed CSV files:
- [raw_customers.csv](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/seeds/raw_customers.csv)
- [raw_orders.csv](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/seeds/raw_orders.csv)
- [raw_payments.csv](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/seeds/raw_payments.csv)

These are referenced in the staging models:
- [stg_customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_customers.sql): `select * from {{ ref('raw_customers') }}`
- [stg_orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_orders.sql): `select * from {{ ref('raw_orders') }}`
- [stg_payments.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_payments.sql): `select * from {{ ref('raw_payments') }}`

The staging models transform and rename columns from the raw data, preparing them for downstream models.

## 2. Model Relationships and Transformation Flow

- Staging models load and clean raw data from seeds.
- Core models ([customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql), [orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql)) reference staging models using `{{ ref('stg_*') }}`.
- [customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql): Aggregates orders and payments by customer.
- [orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql): Aggregates payments by order.

## 3. Critical Output Datasets

The most critical output datasets produced by this dbt project are:

- **customers** ([customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql))
	- Aggregates customer-level metrics, such as first/most recent order, number of orders, and total order amount.
	- Serves as a key output for downstream analytics and reporting.

- **orders** ([orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql))
	- Aggregates order and payment data, including payment method breakdowns and total amounts.
	- Used as a core output for dashboards and business analysis.

These tables are the main outputs of the dbt project and are typically consumed by downstream dashboards, analytics tools, or reporting systems. The staging models ([stg_customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_customers.sql), [stg_orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_orders.sql), [stg_payments.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_payments.sql)) are intermediate steps and not considered final outputs.

**Evidence:**
- [customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql): Builds the customers table from staging models and aggregates key customer metrics.
- [orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql): Builds the orders table from staging models and aggregates payment data.

## 4. Blast Radius of Critical Modules

Changing a critical module in this dbt project can impact multiple downstream models. For example:

- **Changing [`stg_payments.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_payments.sql)** would break:
	- [`orders.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql): Directly references `stg_payments` for payment aggregation.
	- [`customers.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql): References `stg_payments` via downstream joins and aggregations.

- **Changing [`stg_orders.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_orders.sql)** would break:
	- [`orders.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql): Directly references `stg_orders`.
	- [`customers.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql): Aggregates order data for customer metrics.

These dependencies mean that changes to staging models can have a cascading effect on all downstream analytics and reporting built on the core models.

**References:**
- [stg_payments.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_payments.sql)
- [orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql)
- [customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql)

## 5. Blast Radius of Critical Modules

Changing a critical module in this dbt project can impact multiple downstream models. For example:

- **Changing [`models/staging/stg_payments.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_payments.sql)** would break:
	- [`models/orders.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql): Directly references `stg_payments` for payment aggregation.
	- [`models/customers.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql): References `stg_payments` via downstream joins and aggregations.

- **Changing [`models/staging/stg_orders.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_orders.sql)** would break:
	- [`models/orders.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql): Directly references `stg_orders`.
	- [`models/customers.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql): Aggregates order data for customer metrics.

These dependencies mean that changes to staging models can have a cascading effect on all downstream analytics and reporting built on the core models.

**References:**
- [jaffle-shop-classic/models/staging/stg_payments.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/staging/stg_payments.sql)
- [jaffle-shop-classic/models/orders.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql)
- [jaffle-shop-classic/models/customers.sql](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql)

## 6. Business Logic Location

The core business logic for this dbt project is implemented in the main model SQL files, where key metrics and aggregations are calculated:

- **Customer metrics** are calculated in [`customers.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql):
	- First and most recent order dates, number of orders, and total order amount are computed using CTEs and joins (see lines [26](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql#L26), [37](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql#L37), [41](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql#L41), [57](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/customers.sql#L57)).

- **Order and payment aggregations** are implemented in [`orders.sql`](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql):
	- Payment method breakdowns and total amounts are calculated using CTEs and aggregation logic (see lines [21](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql#L21), [24](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql#L24), [51](https://github.com/dbt-labs/jaffle-shop-classic/blob/main/models/orders.sql#L51)).

There are no custom macros or advanced business logic in separate macro files in this project; all key calculations are performed directly in the model SQL files.

## 7. Recent Changes (Git Velocity)

There have been no file changes (commits) in the last 90 or 180 days in this repository. As a result, there is no recent git velocity to report for any file or model.

If the repository is updated in the future, this section should be revisited to identify files with the highest change frequency.

## 8. Difficulty Analysis

The most challenging aspects of manually analyzing and documenting this dbt project were:

- **Tracing data lineage through model dependencies:** While the project is relatively small, understanding how data flows from the raw seed files through the staging models and into the final outputs required careful reading of multiple SQL files. The use of `ref()` helps, but it still took time to map the full dependency chain, especially since there are no visual lineage diagrams in the repo itself.

- **Identifying where business logic is implemented:** All business logic is embedded directly in the model SQL files, with no macros or separate logic layers. This meant reading through lengthy SQL files to find where key metrics and aggregations are calculated, which could be more difficult in a larger or more complex project.

- **Lack of recent change history:** With no recent git commits, it was not possible to analyze change velocity or identify high-velocity files, which is often a key signal for onboarding and risk assessment.

Overall, the absence of explicit documentation connecting the stages of the pipeline and the lack of recent activity made some aspects of the analysis more time-consuming than expected, even in a well-structured example project.
