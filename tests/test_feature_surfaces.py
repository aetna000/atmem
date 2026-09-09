import json,sys
from atmem.cli import main
def test_feature_catalog_and_onboarding_cli(monkeypatch,capsys,tmp_path):
    monkeypatch.setattr(sys,"argv",["atmem","features","adapters","--json"]); main(); value=json.loads(capsys.readouterr().out); assert value["features"]["adapters"]["available"]
    state=tmp_path/"setup.json"; monkeypatch.setattr(sys,"argv",["atmem","onboarding","discover","--state",str(state),"--json"]); main(); assert json.loads(capsys.readouterr().out)["phase"]=="discovered"
