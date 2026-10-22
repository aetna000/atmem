from research.retrieval_2310.dolphin_sample import select


def test_fixed_60_and_recurring_18_cover_all_personas_without_score_selection():
    release={name:{'tests':[{'id':str(i)} for i in range(1,201)]}
             for name in ('morgan','alex','riley')}
    result=select(release)
    assert sum(map(len,result['working_60'].values()))==60
    assert sum(map(len,result['recurring_stage_18'].values()))==18
    assert result==select(dict(reversed(list(release.items()))))
    for persona in release:
        assert set(result['recurring_stage_18'][persona]) <= set(result['working_60'][persona])
