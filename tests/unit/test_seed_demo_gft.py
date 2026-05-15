from scripts import seed_demo_gft


def test_seed_demo_gft_exposes_entrypoints():
    assert callable(seed_demo_gft.seed_demo_data)
    assert callable(seed_demo_gft.main)


def test_seed_demo_gft_has_single_public_demo_cn():
    public_items = [
        item
        for item in seed_demo_gft.DEMO_MEDICATIONS
        if item.estado_gft == "incluido" and item.estado_editorial == "publicado"
    ]

    assert [item.cn for item in public_items] == [seed_demo_gft.PUBLIC_CN]
