# Domain Model

The GEMCODEX platform orchestrates spare part logistics, service tasks, and equipment maintenance. The legacy schema has been ported to PostgreSQL via SQLAlchemy models.

## Entities

### Part Categories & Parts
* **part_categories** – dictionary of categories (e.g. «ножи», «утюги»).
* **parts** – inventory items with stock levels, pricing, optional analog group, and links to equipment.
* **part_analog_groups** – groups of mutually compatible parts.

### Equipment
* **equipment_categories** – dictionary for grouping equipment.
* **equipment** – hierarchical equipment tree (parent/child).
* **equipment_parts** – mapping of parts installed in specific equipment, including custom comments, overrides, and replacement indicators.
* **complex_components** – one-to-one mapping to model assemblies made from equipment parts.

### Counterparties & Orders
* **counterparties** – customers and destinations with contact data and multiple delivery addresses (`counterparty_addresses`).
* **orders** – purchase/delivery documents linked to counterparties and delivery addresses.
* **order_items** – line items referencing parts.

### Maintenance History
* **replacements** – records of parts replaced on equipment.
* **tasks** – work orders assigned to colleagues with optional equipment association.
* **task_parts** – join table of parts required to fulfil tasks.
* **periodic_tasks** – scheduled service jobs based on period (in days).
* **colleagues** – assignees for tasks.

### Knife tracking
* **knife_tracking** – per-part operational state (installed, sharpened, dull) with counters and timestamps.
* **knife_status_log** – historical changes of status.
* **knife_sharpen_log** – sharpening operations.

### Settings
* **app_settings** – key/value application configuration.

## Relationships Overview

```
part_categories 1─* parts *─* equipment_parts *─1 equipment
parts 1─0..1 knife_tracking
knife_tracking 1─* knife_status_log / knife_sharpen_log
counterparties 1─* orders 1─* order_items
orders 1─* replacements (via equipment)
tasks 1─* task_parts ─* parts / equipment_parts
```

All tables include auditing fields (`created_at`, `updated_at`). Soft deletes are handled via application-level flags rather than explicit columns.
