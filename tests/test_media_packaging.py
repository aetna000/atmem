import importlib.util


def test_base_media_contracts_need_no_optional_sdk() -> None:
    from atmem.media.models import ArtifactReference, MediaKind
    assert ArtifactReference and MediaKind.IMAGE.value == "image"
    assert importlib.util.find_spec("atmem.media") is not None
