# ERROR RECOVERY — Stage 2: Flag Agent
# File: traces/stage2_flag_agent/07_error_recovery.md
# ============================================================
# Details any runtime errors encountered during implementation
# and the systematic steps taken to recover and fix them.
# ============================================================

## Incident: ER-001 — UnicodeEncodeError on Windows Terminal

### Date & Time
2026-05-16T04:14:21+05:00

### Environment
OS: Windows
Terminal Encoding: `cp1252`
Python Version: 3.14

### The Error
During the first execution of `python demo_stage2.py`, the script crashed in Phase 3 (Correctness Scoring).

```python
Traceback (most recent call last):
  File "C:\Users\Wahaj\Desktop\New folder\demo_stage2.py", line 31, in <module>
    main()
  File "C:\Users\Wahaj\Desktop\New folder\demo_stage2.py", line 23, in main
    stage2_results = run_stage2(content_blocks)
  File "C:\Users\Wahaj\Desktop\New folder\agents\agent2_flag.py", line 226, in run
    print(f"  {block['id']} \u2192 {block['trust_score']:.3f}{penalty_str} = {score:.3f} \u2192 {label} {icon}")
  File "C:\Users\Wahaj\AppData\Local\Programs\Python\Python314\Lib\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 9: character maps to <undefined>
```

### Root Cause Analysis
The spec (`agent2_flag.md`) included styling elements like arrows (`→`), em-dashes (`—`), and emojis (`🔴`, `🟡`, `🟢`) for console output readability. 
While Python 3 handles Unicode internally, writing to `sys.stdout` on a standard Windows PowerShell/CMD terminal attempts to encode the string using the system default codepage (`cp1252`), which lacks mappings for these specific Unicode characters.

### Recovery Strategy
Rather than forcing the user to change their console codepage (`chcp 65001`) or overriding the `sys.stdout` encoding via environment variables (which might affect other parts of their workflow), the safest architectural fix was to downgrade the console output to standard ASCII characters.

### Remediation Steps
1. Used `multi_replace_file_content` to execute an atomic, 8-chunk search-and-replace on `agents/agent2_flag.py`.
2. Replaced `\u2192` (→) with `->`.
3. Replaced `\u2014` (—) with `-`.
4. Replaced `\u00d7` (×) with `x`.
5. Replaced `🟢` with `(TRUE)`.
6. Replaced `🟡` with `(UNCERTAIN)`.
7. Replaced `🔴` with `(FALSE)`.

### Verification
Ran `python demo_stage2.py` again.
The script executed flawlessly (Exit code: 0) and the terminal output cleanly printed the ASCII-safe equivalents without crashing.

### Prevention for Future Stages
For Stages 3 through 7, all CLI-facing `print()` statements must strictly adhere to the ASCII character set unless UTF-8 output is explicitly enabled or handled via a dedicated logging wrapper that ignores/replaces un-encodable characters.
