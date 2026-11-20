# Coursework source review — 19 November 2026

## Applied changes

- Added readable PDF and actual page-count validation for resource registration and mapping changes.
- Enforced UNIQUE(course_id, file_url) for resources.
- Aligned the database with the existing API policy: a resource with mappings cannot be deleted (RESTRICT). Knowledge-point deletion still cascades aliases and mappings.
- Fixed deletion with already-loaded ORM aliases using passive_deletes="all".
- Escaped LIKE wildcard characters in user search text and replaced per-point location queries with one batch query.
- Added transaction rollback/error responses for database conflicts and resource-row locks around mapping/resource changes.
- Prevented stale frontend search/list responses from replacing newer results. Displayed existing descriptions and mapping notes.
- Added reproducible setup, non-overwriting seed data, pinned requirements, environment example and submission exclusions.
- Replaced obsolete search checks tied to removed demonstration records with isolated PostgreSQL tests.
- Restored the missing TEST002 PDF as a clearly labelled synthetic fixture.

## Verification performed

17 PostgreSQL integration tests passed, including isolated demo initialization and refusal to overwrite populated data. Tests create and remove their own schema; they do not edit the demonstration records.

After migration, all original database rows were compared against the backup: 2 courses, 5 knowledge points, 9 aliases, 3 resources and 8 locations were unchanged. All three registered PDFs exist and match their registered page counts. Existing-data HTTP smoke checks passed for student/admin pages, Natural Join search and the synthetic PDF. Both templates' JavaScript passed Node syntax checks. The synthetic PDF and revised ER image were visually inspected.

A full interactive browser walkthrough and the four-participant usability experiment remain separate verification tasks. No retrieval-time improvements or experimental results have been fabricated.

## Diagram/report implications

Use Case: the existing UC01–UC09 functions and two actors remain accurate; no redraw is required for these fixes.

ER: retain the five entities, cardinalities and shared-course composite foreign keys. Add UNIQUE(course_id, file_url) and document resource deletion RESTRICT and point-related deletion CASCADE. Page-count checking is application logic, not a new entity.

Class/sequence diagrams: derive class names from models.py and calls from app.py, search_service.py and pdf_service.py. Do not claim SearchService or ResourceService classes exist; these modules currently expose functions. Search is implemented with SQLAlchemy expressions, not manually written SQL. Administrator remains a functional role without authentication.

## Remaining boundaries

The existing demo dataset does not contain the same knowledge-point name in both courses. The isolated tests explicitly cover that case; the live demo must not claim to demonstrate same-name disambiguation until suitable clearly labelled sample records are deliberately added.

Upper page bounds are enforced through the application, not by a cross-table CHECK. Direct SQL writes and externally replacing a PDF with different content can bypass the application's assumptions. Browser support determines #page navigation behaviour. Do not describe this local prototype as a production LMO integration.

These changes provide correctness and reproducibility evidence for the marking rubric. They do not guarantee a particular mark; report quality, diagram explanations, research evidence and demonstration still matter.
