# Assumptions

* The domain terminology (e.g. «ножи», «утюги») remains unchanged from the legacy application.
* JWT authentication uses user IDs seeded separately (seed script not provided).
* Service-worker placeholder caches root + manifest only; extend for full offline behaviour.
* Placeholder icons under `webapp/public/icons` should be replaced with real PNG assets before production launch.
* Legacy SQL compatibility endpoint `/legacy/sql` remains temporarily to support the desktop client while REST coverage is expanded.
* Desktop client will be updated to call the new REST API (stub implementation provided; full method coverage requires additional work).
