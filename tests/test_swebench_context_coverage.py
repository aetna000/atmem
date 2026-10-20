from tools.analyze_swebench_context_coverage import compare


def test_omitted_source_is_not_counted_as_delivered_line_coverage():
    pack = '[AtMem structure src/a.py:1-50; name; partial source]\n1: def f():\n[source lines omitted]\n50:     return value\n'
    patch = 'diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -20,1 +20,1 @@\n-    value = False\n+    value = True\n'
    result = compare(pack, patch)
    assert result['agent_replaced_old_lines'] == 1
    assert result['exact_replaced_old_lines_supplied'] == 0
    assert compare(pack.replace('1: def f():', '20:     value = False'), patch)['exact_replaced_old_lines_supplied'] == 1


def test_coverage_requires_same_file_line_and_exact_old_text():
    pack = '[AtMem structure src/a.py:2-2; f; complete definition]\n2: old\n'
    patch = 'diff --git a/src/b.py b/src/b.py\n--- a/src/b.py\n+++ b/src/b.py\n@@ -2,1 +2,1 @@\n-old\n+new\n'
    assert compare(pack, patch)['exact_replaced_old_lines_supplied'] == 0
    assert compare(pack, patch.replace('src/b.py', 'src/a.py'))['exact_replaced_old_lines_supplied'] == 1
