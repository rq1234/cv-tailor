# Re-classify Leadership Entries + Domain-Aware Section Selection

## Context

1. **Existing leadership entries are stuck in `work_experiences`** because they were uploaded before the `activities` table existed. Need an endpoint to reclassify them.
2. **Section selection is domain-blind** — the draft selector always includes projects and activities regardless of whether the target role is tech (where projects matter more) or consulting/finance (where leadership/activities matter more).

## Feature 1: Re-classify Work Experiences → Activities

### New endpoint: `POST /api/experiences/reclassify`

**File: `backend/api/routes/experiences.py`**

Add a new route that accepts a list of work experience IDs and moves them to the `activities` table:

```
POST /api/experiences/reclassify
Body: { "experience_ids": ["uuid1", "uuid2", ...] }
```

Logic:
1. For each ID, fetch the `WorkExperience` row
2. Create an `Activity` row with field mapping:
   - `company` → `organization`
   - `company_confidence` → `organization_confidence`
   - All other fields copied directly (including `embedding` — same vector, no re-embed needed)
3. Run `deduplicate_activity(db, activity)` to assign proper `variant_group_id` within the activities namespace
4. Delete the original `WorkExperience` row
5. Update any `CvVersion` rows that reference the old ID in `selected_experiences` — remove it and add the new activity ID to `selected_activities`
6. Return the list of new activity IDs

### Frontend: Add "Move to Activities" button on library page

**File: `frontend/app/library/page.tsx`**

Add a small "Move to Activities" action on each work experience card (or a batch selection mode). When clicked, calls the reclassify endpoint and refreshes the pool.

**File: `frontend/lib/api.ts`** — no changes needed (already has `api.post`)

**File: `frontend/hooks/useExperiencePool.ts`** — no changes needed (already has `fetchPool` to refresh)

## Feature 2: Domain-Aware Section Selection

### Modify: `backend/agents/draft_selector.py`

Add domain-aware logic after the JD embedding is computed and before/during section selection. Use `jd_parsed.get("domain", "")` to determine role type.

**Domain classification** (simple keyword matching):

```python
TECH_DOMAINS = {"technology", "software", "engineering", "data", "quant", "quantitative", "trading", "fintech"}
CONSULTING_DOMAINS = {"consulting", "management consulting", "strategy", "advisory"}
FINANCE_DOMAINS = {"finance", "banking", "investment banking", "private equity", "asset management", "accounting"}
```

**Section selection rules:**

| Domain | Work Exp | Projects | Activities | Notes |
|--------|---------|----------|-----------|-------|
| Tech/Quant/Trading | max 6 | LIMIT 4 | LIMIT 2 | Prioritize projects |
| Consulting/Finance | max 6 | LIMIT 2 | LIMIT 4 | Prioritize activities/leadership |
| Other/Unknown | max 6 | LIMIT 3 | LIMIT 3 | Balanced |

The work experience cap stays at 6-8 (currently 8, could reduce to leave room for projects/activities). The key change is the **relative weighting** of projects vs activities.

**Implementation in `select_experiences()`:**

After line 55 (after `jd_embedding = await embed_text(...)`), add:

```python
domain = (jd_parsed.get("domain") or "").lower()
is_tech = any(kw in domain for kw in ("tech", "software", "engineer", "data", "quant", "trading", "fintech"))
is_consulting = any(kw in domain for kw in ("consult", "strategy", "advisory"))
is_finance = any(kw in domain for kw in ("financ", "bank", "investment", "equity", "asset"))

if is_tech:
    project_limit, activity_limit = 4, 2
elif is_consulting or is_finance:
    project_limit, activity_limit = 2, 4
else:
    project_limit, activity_limit = 3, 3
```

Then use `project_limit` and `activity_limit` in the LIMIT clauses for the project and activity similarity queries (lines 115-148).

### No other files need changes

- `SelectionResult` schema — no changes (empty list naturally means "section excluded")
- `graph.py` — no changes (already passes full `SelectionResult` through)
- `tailor.py` / `cv_tailor.py` — no changes (they operate on whatever IDs are selected)
- `exporter.py` — no changes (renders sections only if items exist)

## Files Modified

1. `backend/api/routes/experiences.py` — add `POST /api/experiences/reclassify` endpoint
2. `backend/agents/draft_selector.py` — add domain-aware limits for projects vs activities
3. `frontend/app/library/page.tsx` — add "Move to Activities" button on work experience cards

## Verification

1. **Reclassify**: Call `POST /api/experiences/reclassify` with IDs of leadership entries. Verify they disappear from Work Experience section and appear in Activities section on the library page.
2. **Domain selection**: Create two applications — one tech role, one consulting role. Run tailoring on both. Verify the tech role's CV has more projects and fewer activities, while the consulting role's CV has more activities and fewer projects.
