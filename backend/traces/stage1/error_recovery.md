# Stage 1 — Error Recovery Trace
**Module**: `agents/stage1/`
**Version**: 1.0.0
**Created**: 2026-05-16T04:00:00+05:00

---

## Overview

This document records the errors encountered during the development and testing of the Stage 1 parser agents, alongside the diagnostic steps and final resolutions.

---

## ER-01: Windows Console Unicode Encoding Error

**Symptom**:
The initial execution of `demo_stage1.py` crashed immediately during output generation.
```python
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 48: character maps to <undefined>
```

**Context**:
The `runner.py` formatting logic used the Unicode rightwards arrow (`→`) to display console summaries (e.g., `TechCorp Internal Memo  →  51 words`). On Windows systems using the `cp1252` encoding by default, this character could not be printed.

**Diagnosis**:
The output stream encoding cannot reliably handle special characters without enforcing UTF-8 globally.

**Recovery Action**:
Edited `runner.py` to replace all instances of the Unicode arrow `→` with the ASCII equivalent `->`.

**Result**:
Console output rendered successfully on the next execution.

---

## ER-02: JSON Agent Substring Match Bug

**Symptom**:
The `demo_stage1.py` output showed that the analyst target revisions were failing to calculate.
```text
Goldman Sachs. Rating: SELL. target $180 (was $180 (+0.0%)).
Morgan Stanley. Rating: UNDERWEIGHT. target $175 (was $175 (+0.0%)).
```
The expected output should have shown changes from the `previous_target` to the `new_target` (e.g., was 180, is 120, -33.3%).

**Context**:
The JSON agent's `_find_val` function performed a case-insensitive substring match across keys:
```python
def _find_val(flat: dict, keys: set[str]) -> Any:
    # ...
    for candidate in keys:
        for actual_key in lk:
            if candidate.lower() in actual_key.lower():
                return lk[actual_key]
```
The key constants were defined as:
`TARGET_KEYS = {"price_target", "new_target", "target", "target_price"}`
`PREV_TARGET_KEYS = {"previous_target", "prev_target", "old_target", "prior_target"}`

**Diagnosis**:
When the agent searched for `TARGET_KEYS`, it evaluated the candidate `"target"`. The flattened JSON item contained the key `"previous_target"`. Since `"target" in "previous_target"` evaluates to `True`, the search for `new_target` returned the value for `previous_target` (180). Subsequently, the search for `prev_target` explicitly found `"previous_target"` and returned 180. Thus, `new_target == prev_target == 180`, resulting in a 0% change.

**Recovery Action**:
1. Rewrote `_find_val` to enforce **exact match first**, sorting candidates by length descending.
2. Added an `exclude_keys` parameter to prevent substring collisions. If a candidate key exists in `exclude_keys`, it is skipped.
3. Updated the `_to_prose` function to explicitly pass `PREV_TARGET_KEYS` as the exclusion list when fetching `new_target`.

```python
new_target = _find_val(item, TARGET_KEYS, exclude_keys=PREV_TARGET_KEYS)
```

**Result**:
A standalone validation script confirmed the fix:
```text
Goldman Sachs. Rating: SELL. target $120 (was $180 (-33.3%)).
avg_target_change: -33.3
```

---

## ER-03: `newspaper3k` or `beautifulsoup4` Missing (Theoretical/Handled)

**Symptom**:
Not an active crash, but recognized during implementation that these libraries might not be installed in all environments.

**Context**:
The URL scraping agent heavily relies on `bs4` and `newspaper3k`.

**Recovery Action**:
Implemented graceful degradation using `try/except ImportError` blocks at the top of the file:
```python
try:
    from newspaper import Article
    _NEWSPAPER_OK = True
except ImportError:
    _NEWSPAPER_OK = False
```
If a library is missing, the agent bypasses the specific extraction method. If no extraction method is available, the agent safely returns a noise block rather than crashing the thread.

**Result**:
Guaranteed stability of the ThreadPoolExecutor pipeline.
