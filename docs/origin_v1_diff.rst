Differences between ``work`` and ``origin/v1``
=============================================

The repository copy in this workspace only contains the ``work`` branch.  To
compare the agent's previous changes with the upstream ``origin/v1`` branch, I
used commit ``f4be892`` (the merge base before the compat-layer work) as the
latest ``origin/v1`` snapshot and compared it to the current head ``229e6d0``.

Compat managers that mimic the legacy JSON layer
------------------------------------------------

* ``services/compat/__init__.py`` exposes the compat API surface
  (``UsersManagerCompat``, ``AliasManagerCompat``, and ``CompatContext``).
* ``services/compat/context.py`` adds a reusable ``CompatContext`` that hands
  out SQLModel sessions, caches alias "no response" counters, and stamps UTC
  timestamps via ``now_factory``.
* ``services/compat/users_manager.py`` implements the legacy ``UsersManager``
  read APIs (``get_user``, ``list_users``, ``get_group``, ``list_groups``, and
  JSON exports) on top of SQLModel repositories, including normalization of
  timestamps and default JSON fields.
* ``services/compat/alias_manager.py`` recreates ``AliasManager`` behaviors such
  as alias lookups, search name maintenance, legacy source link hydration, and
  cache-backed ``set_no_response`` counters while persisting through SQLModel.
* ``services/compat/utils.py`` contains helpers to enforce UTC timestamps,
  legacy formatting, and normalization of alias/search-name text.

These shims make it possible to keep the old plugin code that expects JSON blobs
while the data lives in the relational schema.

SQLModel schema adjustments
---------------------------

The compat layer surfaced SQLModel/SQLAlchemy configuration warnings.  To remove
them, the diff updates relationships to use explicit SQLAlchemy ``relationship``
declarations instead of relying on ``SQLModel`` defaults, and it standardizes
JSON columns so the ORM can persist dictionaries reliably.

* ``services/db/models/group.py`` declares ``Group.members`` and
  ``Membership.{user,group}`` with explicit ``relationship`` objects and keeps
  JSON metadata on ``extra_json``.
* ``services/db/models/user.py`` ensures ``User.memberships`` and
  ``User.subscriptions`` use SQLAlchemy relationships and that ``extra_json`` is
  stored via a JSON column.
* ``services/db/models/subscription.py`` applies the same relationship pattern
  to ``Subscription``, ``SubscriptionTarget``, and ``SubscriptionOption``, plus
  ensures JSON flag columns use SQLAlchemy ``Column(JSON)``.
* ``services/db/models/play.py`` declares relationships for aliases, source
  links, and snapshots, and deduplicates JSON column definitions to avoid
  multiple ``SQLModel`` base inheritance.
* ``services/db/models/hlq.py`` adds relationship metadata for events ↔ tickets
  and stores ticket payloads in JSON columns.
* ``services/db/models/observability.py`` normalizes JSON column declarations
  and UTC timestamp defaults in the observability tables.

Tests and support utilities
---------------------------

* ``scripts/__init__.py`` adds a module docstring so pytest/importers can treat
  ``scripts`` as a package.
* ``tests/test_compat.py`` imports the legacy JSON fixtures, runs the importer
  into an in-memory SQLite database, and verifies the compat managers return the
  same structures (including cached alias data) as the old JSON golden files.

These tests exercise both managers end-to-end to catch regressions while the
migration is underway.
