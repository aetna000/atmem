from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from atmem.benchmark.memory_adaptation import grade_answer, read_only_query, _training_excerpt


@pytest.fixture
def db(tmp_path):
    path=tmp_path/"fixture.db"
    con=sqlite3.connect(path);con.execute('CREATE TABLE facts(value INTEGER)');con.execute('INSERT INTO facts VALUES (7)');con.commit();con.close()
    return path


def test_real_sql_read_and_schema_but_no_write_attach_or_unsafe_pragma(db,tmp_path):
    assert read_only_query(db,'SELECT value FROM facts')["rows"]==[(7,)]
    assert read_only_query(db,'.schema facts')["rows"]
    assert read_only_query(db,'PRAGMA table_info(facts)')["rows"]
    for sql in ('DELETE FROM facts','WITH x AS (SELECT 1) DELETE FROM facts',"ATTACH DATABASE ':memory:' AS other",'PRAGMA journal_mode=WAL',"SELECT load_extension('bad')",'CREATE TABLE bad(x)', 'SELECT 1; DELETE FROM facts'):
        assert 'error' in read_only_query(db,sql)
    assert read_only_query(db,'SELECT value FROM facts')["rows"]==[(7,)]


def test_sql_result_size_rows_and_execution_are_bounded(db):
    result=read_only_query(db,'WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<100) SELECT x FROM n')
    assert len(result["rows"])==50 and result["truncated"]
    assert 'error' in read_only_query(db,'WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n',seconds=.001)


def test_strict_grader_does_not_accept_prose_or_nonfinite_and_records_upstream_difference():
    target={"answer":7,"answer_type":"integer","tolerance":0,"oracle_verified":True}
    assert grade_answer({"answer":"7","queries":2},target).correct
    grade=grade_answer({"answer":"7 or 8","queries":2},target)
    assert not grade.correct and grade.evidence["grader_disagreement"]
    assert not grade_answer({"answer":True,"queries":0},target).correct
    target.update(answer_type="float",answer=7.)
    assert not grade_answer({"answer":"nan","queries":0},target).correct
    with pytest.raises(ValueError):grade_answer({"answer":7,"queries":0},{**target,"oracle_verified":False})


def test_evidence_excerpt_is_bounded_and_contains_no_grades():
    text=_training_excerpt([{"case_id":str(i),"question":"kept question", "observations":[{"query":"SELECT value FROM facts","result":{"columns":["value"],"rows":[[7]]}} for _ in range(30)]} for i in range(10)])
    assert len(text.encode())<=12000 and 'kept question' in text and '"omissions":true' in text


def test_cli_requires_explicit_egress_and_paid_opt_in(tmp_path):
    result=subprocess.run([sys.executable,'-m','atmem.benchmark.memory_adaptation','--data',str(tmp_path),'--home',str(tmp_path/'home')],capture_output=True,text=True)
    assert result.returncode!=0 and 'explicit --allow-paid-public-benchmark' in result.stderr
    assert not (tmp_path/'home').exists()
